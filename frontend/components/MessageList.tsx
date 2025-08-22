'use client'

import { Message, ArtifactData } from '@/types/chat'
import MessageBubble from './MessageBubble'
import TypingIndicator from './TypingIndicator'

interface MessageListProps {
  messages: Message[]
  isTyping: boolean
  onArtifactOpen?: (artifactData: ArtifactData) => void
  onFileDownload?: (filename: string, sessionId: string) => void
  sessionId?: string
}

export default function MessageList({ messages, isTyping, onArtifactOpen, onFileDownload, sessionId }: MessageListProps) {
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
      {isTyping && <TypingIndicator />}
    </>
  )
}