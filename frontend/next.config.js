/** @type {import('next').NextConfig} */
const nextConfig = {
  // Required for Docker multi-stage build (stage 3: runner)
  output: 'standalone',

  // API proxy to backend in development
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/:path*`,
      },
    ]
  },
}
module.exports = nextConfig
