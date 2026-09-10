/** @type {import('next').NextConfig} */
const nextConfig = {
  devIndicators: false,
  skipTrailingSlashRedirect: true,
  async rewrites() {
    // In production, nginx's `location /dfg/api/` already strips the prefix and
    // proxies straight to dfgbackend, so this rewrite only matters for local dev
    // (`next dev` without nginx in front). Kept symmetric with the main app's
    // next.config.mjs pattern.
    const backend = process.env.BACKEND_INTERNAL_URL || "http://dfgbackend:80";
    return [
      {
        source: "/dfg/api/:path*",
        destination: `${backend}/:path*`,
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
