import type { Metadata } from 'next'
import './globals.css'
import { AuthProvider } from '@/contexts/AuthContext'

export const metadata: Metadata = {
  title: '辉途智能配方助手 - AI驱动的动物营养配方专家',
  description: '基于 LangGraph 和 Claude 3.5 Sonnet 的智能动物营养配方系统，支持奶牛、肉牛、猫、狗等多种动物类型，专业营养标准，智能优化算法',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="zh-CN">
      <body className="antialiased">
        <AuthProvider>
          {children}
        </AuthProvider>
      </body>
    </html>
  )
}