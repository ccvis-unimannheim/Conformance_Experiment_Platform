/** @type {import('next').NextConfig} */
const nextConfig = {
  devIndicators: false,
  skipTrailingSlashRedirect: true,
  async rewrites() {
    const backend = process.env.BACKEND_INTERNAL_URL || "http://provibackend:80";
    return [
      {
        source: "/api/:path*",
        destination: `${backend}/api/:path*`,
      },
    ];
  },
  webpack(config) {
    config.module.rules.push({
      test: /\.svg$/,
      use: ["@svgr/webpack"],
    });

    return config;
  },
};

export default nextConfig;
