import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
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

const backendUrl = process.env.BACKEND_API_URL ?? "http://127.0.0.1:8000";
export default nextConfig;
