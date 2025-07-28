'use client'

import { Message } from '@/types/chat'
import MessageBubble from './MessageBubble'
import TypingIndicator from './TypingIndicator'

interface MessageListProps {
  messages: Message[]
  isTyping: boolean
}

export default function MessageList({ messages, isTyping }: MessageListProps) {
  return (
    <>
      {messages.map((message) => (
        <MessageBubble key={message.messageId || message.id} message={message} />
      ))}
      {isTyping && <TypingIndicator />}
    </>
  )
}