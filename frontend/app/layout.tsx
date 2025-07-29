import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: '辉途智能配方助手 - AI助手',
  description: '基于 LangGraph 的现代化 AI 助手，具有高级推理能力',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="zh-CN">
      <body className="antialiased">
        {children}
      </body>
    </html>
  )
}