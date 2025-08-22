'use client'

import { useState, useEffect, useCallback } from 'react'
import { Message } from '@/types/chat'

interface UseSessionHistoryProps {
  sessionId: string | null
  endpoint?: string
}

interface SessionHistoryResponse {
  session_id: string
  messages: Message[]  // Already in unified ParsedMessage format from backend
  summary: {
    session_id: string
    total_messages: number
    human_messages: number
    ai_messages: number
    system_messages: number
    has_history: boolean
  }
}

interface UseSessionHistoryReturn {
  messages: Message[]
  isLoading: boolean
  error: string | null
  loadSessionHistory: () => Promise<void>
}

export function useSessionHistory({ 
  sessionId, 
  endpoint = 'http://localhost:8000' 
}: UseSessionHistoryProps): UseSessionHistoryReturn {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadSessionHistory = useCallback(async () => {
    if (!sessionId) {
      setMessages([])
      setError(null)
      return
    }

    try {
      setIsLoading(true)
      setError(null)
      
      const response = await fetch(`${endpoint}/sessions/${sessionId}/history`)
      
      if (!response.ok) {
        throw new Error(`Failed to load session history: ${response.statusText}`)
      }
      
      const data: SessionHistoryResponse = await response.json()
      
      // Backend now returns ParsedMessage format directly with proper metadata
      setMessages(data.messages || [])
    } catch (error) {
      console.error('Error loading session history:', error)
      setError(error instanceof Error ? error.message : 'Failed to load session history')
      setMessages([])
    } finally {
      setIsLoading(false)
    }
  }, [sessionId, endpoint])

  useEffect(() => {
    loadSessionHistory()
  }, [loadSessionHistory])

  return {
    messages,
    isLoading,
    error,
    loadSessionHistory
  }
}