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

interface ThinkingState {
  isActive: boolean
  content: string
  isComplete: boolean
}

interface MessageListProps {
  messages: Message[]
  isTyping: boolean
  analysisState?: AnalysisState
  formulationState?: FormulationState
  thinkingState?: ThinkingState
  onArtifactOpen?: (artifactData: ArtifactData) => void
  onFileDownload?: (filename: string, sessionId: string) => void
  sessionId?: string
}

export default function MessageList({ messages, isTyping, analysisState, formulationState, thinkingState, onArtifactOpen, onFileDownload, sessionId }: MessageListProps) {
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
      {(isTyping || analysisState?.isActive || analysisState?.isComplete || formulationState?.isActive || formulationState?.isComplete || thinkingState?.isActive || thinkingState?.isComplete) && (
        <TypingIndicator
          analysisState={analysisState}
          formulationState={formulationState}
          thinkingState={thinkingState}
          isTyping={isTyping}
        />
      )}
    </>
  )
}