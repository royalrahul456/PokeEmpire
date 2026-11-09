"use client";

import React, { useEffect, useRef } from "react";

interface LiquidGlassSceneProps {
  children: React.ReactNode;
  className?: string;
}

export const LiquidGlassScene: React.FC<LiquidGlassSceneProps> = ({
  children,
  className = "",
}) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (typeof window === "undefined" || !containerRef.current) return;
    let liquidInstance: any = null;
    let isMounted = true;

    const initLiquid = async () => {
      try {
        const { LiquidGlass } = await import("@ybouane/liquidglass");
        if (!isMounted || !containerRef.current) return;

        const glassNodes = containerRef.current.querySelectorAll<HTMLElement>('[data-glass="true"]');
        if (glassNodes.length === 0) return;

        liquidInstance = await LiquidGlass.init({
          root: containerRef.current,
          glassElements: Array.from(glassNodes),
          defaults: {
            blurAmount: 0.32,
            refraction: 0.50,
            chromAberration: 0.05,
            edgeHighlight: 0.15,
            specular: 0.12,
            fresnel: 0.90,
            cornerRadius: 28,
            zRadius: 22,
            shadowOpacity: 0.25,
            shadowSpread: 18,
            shadowOffsetY: 4,
          },
        });
      } catch (err) {
        // Graceful fallback to CSS LiquidGlass physical refraction styling
        console.warn("LiquidGlass WebGL notice:", err);
      }
    };

    // Small delay to ensure child DOM elements are rendered
    const timer = setTimeout(initLiquid, 150);

    return () => {
      isMounted = false;
      clearTimeout(timer);
      if (liquidInstance && typeof liquidInstance.destroy === "function") {
        try {
          liquidInstance.destroy();
        } catch (e) {}
      }
    };
  }, []);

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      {children}
    </div>
  );
};

interface LiquidGlassCardProps {
  children: React.ReactNode;
  className?: string;
  config?: Record<string, any>;
  onClick?: () => void;
  style?: React.CSSProperties;
}

export const LiquidGlassCard: React.FC<LiquidGlassCardProps> = ({
  children,
  className = "",
  config,
  onClick,
  style,
}) => {
  return (
    <div
      data-glass="true"
      data-config={config ? JSON.stringify(config) : undefined}
      onClick={onClick}
      style={style}
      className={`liquid-glass rounded-3xl ${className}`}
    >
      {children}
    </div>
  );
};
