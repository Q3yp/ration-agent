import { NextResponse } from 'next/server'

/**
 * Health check endpoint for Docker containers and monitoring
 * GET /api/health
 */
export async function GET() {
  try {
    // Basic health check - could be extended to check database connectivity, etc.
    return NextResponse.json({
      status: 'healthy',
      timestamp: new Date().toISOString(),
      uptime: process.uptime(),
      version: process.env.npm_package_version || '0.1.0'
    }, { status: 200 })
  } catch (error) {
    return NextResponse.json({
      status: 'unhealthy',
      timestamp: new Date().toISOString(),
      error: 'Health check failed'
    }, { status: 503 })
  }
}
