import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'LangGraph ReAct Agent Chat',
  description: 'Chat interface for LangGraph ReAct Agent with tool calling capabilities',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="antialiased bg-gray-50">
        {children}
      </body>
    </html>
  )
}