import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Disable ESLint during production builds (for faster deployment)
  eslint: {
    ignoreDuringBuilds: true,
  },
  
  // Disable TypeScript errors during production builds (for faster deployment)
  typescript: {
    ignoreBuildErrors: true,
  },
  
  // Enable webpack polling for hot reload in Docker (especially on Windows)
  webpack: (config, { dev }) => {
    if (dev) {
      config.watchOptions = {
        poll: 1000, // Check for changes every second
        aggregateTimeout: 300, // Delay before rebuilding
      };
    }
    return config;
  },
};

export default nextConfig;
