import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/v1/:path*", destination: `${process.env.BACKEND_URL || "http://localhost:5000"}/v1/:path*` }];
  },
  experimental: {
    serverActions: {
      bodySizeLimit: "100mb",
    },
  },
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "assets.watermelon.sh",
      },
    ],
  },
};

export default nextConfig;
