import { NextResponse } from 'next/server'

/**
 * Public config endpoint — exposes non-secret runtime env vars to the client.
 * This allows GOOGLE_CLIENT_ID to be set at deploy time via docker-compose
 * instead of being baked in at build time via NEXT_PUBLIC_*.
 */
export async function GET() {
  return NextResponse.json({
    googleClientId: process.env.GOOGLE_CLIENT_ID || process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || '',
  })
}
