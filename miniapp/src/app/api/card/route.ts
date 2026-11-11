import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const title = searchParams.get("title") || "PokéEmpire 🐾";
  const site = searchParams.get("site") || "PokéEmpire";
  const video = searchParams.get("video") || "";
  const image = searchParams.get("image") || "";
  const desc = searchParams.get("desc") || "Catch, Battle & Conquer the PokéEmpire!";

  const videoMeta = video
    ? `
  <meta property="og:type" content="video.other" />
  <meta property="og:video" content="${video}" />
  <meta property="og:video:secure_url" content="${video}" />
  <meta property="og:video:type" content="video/mp4" />
  <meta property="og:video:width" content="1280" />
  <meta property="og:video:height" content="720" />
  <meta name="twitter:card" content="player" />
  <meta name="twitter:player" content="${video}" />
  <meta name="twitter:player:width" content="1280" />
  <meta name="twitter:player:height" content="720" />`
    : `
  <meta property="og:type" content="website" />
  <meta name="twitter:card" content="summary_large_image" />`;

  const imageMeta = image
    ? `
  <meta property="og:image" content="${image}" />
  <meta name="twitter:image" content="${image}" />`
    : "";

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>${title}</title>
  <meta property="og:site_name" content="${site}" />
  <meta property="og:title" content="${title}" />
  <meta property="og:description" content="${desc}" />
  ${videoMeta}
  ${imageMeta}
</head>
<body style="background:#0b0f19;color:#fff;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <div style="text-align:center;padding:20px;">
    <h2>${title}</h2>
    <p style="color:#888;">PokéEmpire Video & Artwork Preview</p>
  </div>
</body>
</html>`;

  return new NextResponse(html, {
    status: 200,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "public, max-age=86400, s-maxage=86400",
    },
  });
}
