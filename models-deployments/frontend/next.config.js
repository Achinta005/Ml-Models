/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  eslint: {
    ignoreDuringBuilds: true
  },
  experimental: {
    serverActions: false,
    ppr: false
  }
};

module.exports = nextConfig;
