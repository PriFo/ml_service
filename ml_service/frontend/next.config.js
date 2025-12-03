/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  async rewrites() {
    // Use environment variable or default
    let backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8085';
    
    // If backend URL is relative or doesn't have protocol, keep as is
    // The frontend API client will handle protocol detection
    
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/:path*`,
      },
    ];
  },
}

module.exports = nextConfig

