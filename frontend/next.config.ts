import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    const backendUrl = process.env.BACKEND_URL;
    if (backendUrl) {
      return [
        {
          source: "/api/v1/:path*",
          destination: `${backendUrl.replace(/\/+$/, "")}/api/v1/:path*`,
        },
      ];
    }
    return [];
  },
};

export default nextConfig;
