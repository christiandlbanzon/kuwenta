/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    typedRoutes: false,
  },
  // The frontend talks to the backend through Next.js route handlers (see app/api/proxy)
  // so the JWT lives in an httpOnly cookie and never reaches the browser bundle.
};

export default nextConfig;
