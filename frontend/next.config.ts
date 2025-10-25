import type { NextConfig } from "next";

const nextConfig: NextConfig = {
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
