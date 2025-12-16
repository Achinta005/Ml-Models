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

export default nextConfig;
