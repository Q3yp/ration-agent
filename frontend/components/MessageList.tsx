'use client'

import { Message, ArtifactData } from '@/types/chat'
import MessageBubble from './MessageBubble'
import TypingIndicator from './TypingIndicator'

interface AnalysisState {
  isActive: boolean
  content: string
  isComplete: boolean
  operationsCount?: number
}

interface FormulationState {
  isActive: boolean
  content: string
  isComplete: boolean
  operationsCount?: number
  operations?: string[]
  operationData?: unknown[]
}

interface MessageListProps {
  messages: Message[]
  isTyping: boolean
  analysisState?: AnalysisState
  formulationState?: FormulationState
  onArtifactOpen?: (artifactData: ArtifactData) => void
  onFileDownload?: (filename: string, sessionId: string) => void
  sessionId?: string
}

export default function MessageList({ messages, isTyping, analysisState, formulationState, onArtifactOpen, onFileDownload, sessionId }: MessageListProps) {
  return (
    <>
      {messages.map((message) => (
        <MessageBubble 
          key={message.id} 
          message={message} 
          onArtifactOpen={onArtifactOpen}
          onFileDownload={onFileDownload}
          sessionId={sessionId}
        />
      ))}
      {(isTyping || analysisState?.isActive || analysisState?.isComplete || formulationState?.isActive || formulationState?.isComplete) && (
        <TypingIndicator 
          analysisState={analysisState} 
          formulationState={formulationState}
          isTyping={isTyping}
        />
      )}
    </>
  )
}