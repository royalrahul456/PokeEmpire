import crypto from "crypto";

export interface TelegramUserData {
  id: number;
  first_name?: string;
  last_name?: string;
  username?: string;
  language_code?: string;
  photo_url?: string;
}

/**
 * Validates Telegram WebApp initData on the server side using HMAC-SHA256.
 * Adheres strictly to Telegram's official cryptographic authentication specification.
 */
export function verifyTelegramInitData(
  initData: string,
  botToken: string
): { isValid: boolean; user?: TelegramUserData } {
  if (!initData || !botToken) {
    return { isValid: false };
  }

  try {
    const params = new URLSearchParams(initData);
    const hash = params.get("hash");
    if (!hash) {
      return { isValid: false };
    }

    params.delete("hash");

    // Sort parameters alphabetically
    const entries: string[] = [];
    params.forEach((val, key) => {
      entries.push(`${key}=${val}`);
    });
    entries.sort();
    const dataCheckString = entries.join("\n");

    // Secret key = HMAC_SHA256("WebAppData", botToken)
    const secretKey = crypto
      .createHmac("sha256", "WebAppData")
      .update(botToken)
      .digest();

    // Calculated hash = HMAC_SHA256(secretKey, dataCheckString)
    const calculatedHash = crypto
      .createHmac("sha256", secretKey)
      .update(dataCheckString)
      .digest("hex");

    if (calculatedHash.toLowerCase() === hash.toLowerCase()) {
      const userRaw = params.get("user");
      let user: TelegramUserData | undefined;
      if (userRaw) {
        user = JSON.parse(userRaw);
      }
      return { isValid: true, user };
    }

    return { isValid: false };
  } catch (err) {
    console.error("Error verifying Telegram initData:", err);
    return { isValid: false };
  }
}

/**
 * Client-side helper for Telegram WebApp SDK.
 */
export function getTelegramWebApp(): any {
  if (typeof window !== "undefined" && (window as any).Telegram?.WebApp) {
    return (window as any).Telegram.WebApp;
  }
  return null;
}

export function triggerTelegramHaptic(
  type: "light" | "medium" | "heavy" | "rigid" | "soft" | "error" | "success" | "warning"
) {
  const tg = getTelegramWebApp();
  if (tg?.HapticFeedback) {
    try {
      if (type === "error" || type === "success" || type === "warning") {
        tg.HapticFeedback.notificationOccurred(type);
      } else {
        tg.HapticFeedback.impactOccurred(type);
      }
    } catch (e) {
      // Haptics not supported on device
    }
  }
}
