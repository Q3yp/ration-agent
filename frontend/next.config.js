const path = require('path');

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enable standalone output for Docker deployment
  output: 'standalone',
  
  webpack: (config) => {
    config.resolve.fallback = {
      ...config.resolve.fallback,
      fs: false,
    };
    
    // Add alias for @ path
    config.resolve.alias = {
      ...config.resolve.alias,
      '@': path.resolve(__dirname),
    };
    
    return config;
  },
  
  async rewrites() {
    // Use different backend URL for Docker vs development
    const backendUrl = process.env.NODE_ENV === 'production' 
      ? 'http://backend:8000'  // Docker container name
      : 'http://localhost:8000';  // Development
      
    return [
      {
        source: '/auth/:path*',
        destination: `${backendUrl}/auth/:path*`,
      },
      {
        source: '/admin/:path*',
        destination: `${backendUrl}/admin/:path*`,
      },
      {
        source: '/api/:path*',
        destination: `${backendUrl}/:path*`,
      },
    ];
  },
  async headers() {
    return [
      {
        source: '/api/:path*',
        headers: [
          { key: 'Cache-Control', value: 'no-store' },
          { key: 'Connection', value: 'keep-alive' },
          { key: 'X-Accel-Buffering', value: 'no' },
        ]
      }
    ]
  }
};

module.exports = nextConfig;