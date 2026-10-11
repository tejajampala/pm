import type { NextConfig } from "next";

const backendUrl = process.env.BACKEND_API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  // Rewrites only apply under `next dev` (Next warns they are ignored by the static export);
  // in Docker, FastAPI serves both the static site and /api on the same origin.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
