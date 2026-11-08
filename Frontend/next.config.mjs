const apiBaseUrl = process.env.API_BASE_URL?.replace(/\/+$/, '')

/** @type {import('next').NextConfig} */
const nextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  env: {
    NEXT_PUBLIC_API_CONFIGURED: apiBaseUrl ? 'true' : '',
  },
  async rewrites() {
    if (!apiBaseUrl) return []
    return [{ source: '/api/:path*', destination: `${apiBaseUrl}/api/:path*` }]
  },
}

export default nextConfig
