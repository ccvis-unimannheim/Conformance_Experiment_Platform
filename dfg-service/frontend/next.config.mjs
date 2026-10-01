/** @type {import('next').NextConfig} */
const nextConfig = {
  devIndicators: false,
  skipTrailingSlashRedirect: true,
  // This app is served under /dfg/ behind nginx. basePath makes Next.js
  // itself aware of that, so every auto-generated asset URL (CSS/JS chunks,
  // fonts, next/image, next/link hrefs) is correctly prefixed with /dfg —
  // without it, those links resolve to the domain root and get routed to the
  // MAIN app's nginx block instead of this one. nginx's /dfg/ location must
  // NOT strip the prefix for this to work (see provibackend/nginx/nginx.conf).
  basePath: "/dfg",
  async rewrites() {
    // basePath auto-prefixes this source with /dfg, so the incoming request
    // nginx forwards (/dfg/api/...) matches here without repeating it. Only
    // matters for local dev (`next dev` without nginx in front) — in
    // production nginx's `location /dfg/api/` proxies straight to dfgbackend.
    const backend = process.env.BACKEND_INTERNAL_URL || "http://dfgbackend:80";
    return [
      {
        source: "/api/:path*",
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
