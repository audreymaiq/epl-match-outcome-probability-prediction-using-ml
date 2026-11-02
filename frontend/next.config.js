/** @type {import('next').NextConfig} */
const nextConfig = {
  // Required for Docker multi-stage build (stage 3: runner)
  output: 'standalone',

  // Browser requests stay same-origin; Next.js proxies privately to the API.
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.API_INTERNAL_URL || 'http://localhost:8000'}/api/:path*`,
      },
    ]
  },
}
module.exports = nextConfig
