'use client'

import { Message, ArtifactData } from '@/types/chat'
import MessageBubble from './MessageBubble'
import TypingIndicator from './TypingIndicator'

interface MessageListProps {
  messages: Message[]
  isTyping: boolean
  onArtifactOpen?: (artifactData: ArtifactData) => void
}

export default function MessageList({ messages, isTyping, onArtifactOpen }: MessageListProps) {
  return (
    <>
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} onArtifactOpen={onArtifactOpen} />
      ))}
      {isTyping && <TypingIndicator />}
    </>
  )
}