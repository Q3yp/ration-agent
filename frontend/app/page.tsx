'use client'

import { useState, useEffect } from 'react'
import { v4 as uuidv4 } from 'uuid'
import ChatInterface from '@/components/ChatInterface'

export default function Home() {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [sessionError, setSessionError] = useState<string | null>(null)
  const [isCreatingSession, setIsCreatingSession] = useState(true)

  useEffect(() => {
    const createSession = async () => {
      const generatedSessionId = uuidv4()
      
      try {
        const response = await fetch('http://localhost:8000/sessions/create', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ session_id: generatedSessionId }),
        })
        
        if (!response.ok) {
          throw new Error(`Failed to create session: ${response.statusText}`)
        }
        
        const data = await response.json()
        setSessionId(data.session_id)
        setSessionError(null)
      } catch (error) {
        console.error('Session creation error:', error)
        setSessionError(error instanceof Error ? error.message : 'Failed to create session')
      } finally {
        setIsCreatingSession(false)
      }
    }
    
    createSession()
  }, [])

  return (
    <main className="h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="container mx-auto h-full max-w-4xl">
        <div className="flex flex-col h-full">
          <header className="py-6 px-4">
            <h1 className="text-3xl font-bold text-gray-800 text-center">
              LangGraph ReAct 智能体
            </h1>
            <p className="text-gray-600 text-center mt-2">
              与基于 LangGraph 的 AI 智能体聊天，支持实时流式传输
            </p>
          </header>
          
          <div className="flex-1 px-4 pb-4">
            {isCreatingSession ? (
              <div className="flex items-center justify-center h-full">
                <div className="text-center">
                  <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900 mx-auto"></div>
                  <p className="text-gray-600 mt-4">创建会话中...</p>
                </div>
              </div>
            ) : sessionError ? (
              <div className="flex items-center justify-center h-full">
                <div className="text-center">
                  <div className="text-red-600 text-xl mb-4">⚠️</div>
                  <p className="text-red-600 mb-4">{sessionError}</p>
                  <button 
                    onClick={() => window.location.reload()}
                    className="bg-red-500 text-white px-4 py-2 rounded hover:bg-red-600"
                  >
                    重试
                  </button>
                </div>
              </div>
            ) : sessionId ? (
              <ChatInterface sessionId={sessionId} />
            ) : null}
          </div>
        </div>
      </div>
    </main>
  )
}