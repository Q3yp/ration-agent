'use client'

import { useState, useRef, useEffect } from 'react'
import { PaperAirplaneIcon, ExclamationTriangleIcon, DocumentArrowUpIcon } from '@heroicons/react/24/outline'
import MessageList from './MessageList'
import FileUpload from './FileUpload'
import { useSSEChat } from '@/hooks/useSSEChat'

interface ChatInterfaceProps {
  sessionId: string
  endpoint?: string
}

export default function ChatInterface({ sessionId, endpoint }: ChatInterfaceProps) {
  const [inputValue, setInputValue] = useState('')
  const [showFileUpload, setShowFileUpload] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const {
    messages,
    isConnected,
    isTyping,
    connectionError,
    sendMessage,
    retryConnection,
  } = useSSEChat({ sessionId, endpoint })

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSendMessage = async () => {
    if (!inputValue.trim()) return

    const messageToSend = inputValue.trim()
    setInputValue('')
    
    try {
      await sendMessage(messageToSend)
    } catch (error) {
      console.error('Failed to send message:', error)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  return (
    <div className="flex flex-col h-full bg-white rounded-lg shadow-lg overflow-hidden">
      {/* Connection Status */}
      <div className={`px-4 py-2 text-sm ${
        isConnected 
          ? 'bg-green-100 text-green-800' 
          : 'bg-red-100 text-red-800'
      }`}>
        <div className="flex items-center justify-between">
          <span>
            {isConnected ? '🟢 SSE 已连接' : '🔴 SSE 连接错误'}
          </span>
          {connectionError && (
            <button
              onClick={retryConnection}
              className="text-sm underline hover:no-underline"
            >
              重试
            </button>
          )}
        </div>
        {connectionError && (
          <div className="mt-1 flex items-center">
            <ExclamationTriangleIcon className="h-4 w-4 mr-1" />
            {connectionError}
          </div>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <MessageList 
          messages={messages} 
          isTyping={isTyping} 
        />
        <div ref={messagesEndRef} />
      </div>

      {/* File Upload Section */}
      {showFileUpload && (
        <div className="border-t border-gray-200 p-4">
          <FileUpload 
            sessionId={sessionId} 
            endpoint={endpoint}
          />
        </div>
      )}

      {/* Input */}
      <div className="border-t border-gray-200 p-4">
        <div className="flex space-x-2">
          <button
            onClick={() => setShowFileUpload(!showFileUpload)}
            disabled={!isConnected}
            className={`px-3 py-2 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 disabled:cursor-not-allowed transition-colors ${
              showFileUpload 
                ? 'bg-primary-500 text-white hover:bg-primary-600' 
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
            title="Toggle file upload"
          >
            <DocumentArrowUpIcon className="h-5 w-5" />
          </button>
          <input
            ref={inputRef}
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="输入您的消息..."
            disabled={!isConnected || isTyping}
            className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
          />
          <button
            onClick={handleSendMessage}
            disabled={!inputValue.trim() || !isConnected || isTyping}
            className="px-4 py-2 bg-primary-500 text-white rounded-md hover:bg-primary-600 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
          >
            <PaperAirplaneIcon className="h-5 w-5" />
          </button>
        </div>
        <div className="mt-2 text-xs text-gray-500">
          按回车键发送 • Shift+回车键换行 • {showFileUpload ? '文件上传已启用' : '点击 📁 上传文件'} • 使用服务器推送事件
        </div>
      </div>
    </div>
  )
}