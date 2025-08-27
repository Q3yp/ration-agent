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
};

module.exports = nextConfig;