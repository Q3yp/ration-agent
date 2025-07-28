'use client'

import { Message } from '@/types/chat'
import {
  CogIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  InformationCircleIcon
} from '@heroicons/react/24/outline'
import { formatTimestamp } from '@/utils/formatTime'
import MarkdownMessage from './MarkdownMessage'
import { useState } from 'react'
import { ChevronRightIcon } from '@heroicons/react/24/outline'


interface MessageBubbleProps {
  message: Message
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const renderToolCall = () => (
    <div className="message-bubble tool-call">
      {/* Clickable Header */}
      <div
        className="flex items-center justify-between cursor-pointer"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center">
          <ChevronRightIcon className={`h-4 w-4 mr-1 transition-transform ${isExpanded ? 'rotate-90' : ''}`} />
          <CogIcon className="h-4 w-4 mr-2" />
          <span className="font-semibold">Tool Call: {message.toolName}</span>
        </div>
        <div className="text-xs text-blue-600">
          {formatTimestamp(message.timestamp)}
        </div>
      </div>

      {/* Expandable Content */}
      {isExpanded && message.toolArgs && Object.keys(message.toolArgs).length > 0 && (
        <div className="mt-2 bg-blue-100 p-2 rounded text-xs max-h-64 overflow-y-auto"> {/* ✨ Changes Here */}
          <strong>Arguments:</strong>
          <pre className="mt-1 whitespace-pre-wrap">
            {JSON.stringify(message.toolArgs, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )

  const renderToolResult = () => (
    <div className="message-bubble tool-result">
      {/* Clickable Header */}
      <div
        className="flex items-center justify-between cursor-pointer"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center">
          <ChevronRightIcon className={`h-4 w-4 mr-1 transition-transform ${isExpanded ? 'rotate-90' : ''}`} />
          <CheckCircleIcon className="h-4 w-4 mr-2" />
          <span className="font-semibold">Tool Result</span>
        </div>
        <div className="text-xs text-green-600">
          {formatTimestamp(message.timestamp)}
        </div>
      </div>

      {/* Expandable Content */}
      {isExpanded && (
        <div className="mt-2 bg-green-100 p-2 rounded text-sm max-h-64 overflow-y-auto"> {/* ✨ Changes Here */}
          {/* For code-like output, wrapping in a <pre> tag is best */}
          <pre className="whitespace-pre-wrap">
            {message.content}
          </pre>
        </div>
      )}
    </div>
  )

  const renderSystemMessage = () => (
    <div className="message-bubble system-message">
      <div className="flex items-center justify-center">
        <InformationCircleIcon className="h-4 w-4 mr-2" />
        {message.content}
      </div>
      <div className="text-xs mt-1">
        {formatTimestamp(message.timestamp)}
      </div>
    </div>
  )

  const renderErrorMessage = () => (
    <div className="message-bubble error-message">
      <div className="flex items-center mb-2">
        <ExclamationCircleIcon className="h-4 w-4 mr-2" />
        <span className="font-semibold">Error</span>
      </div>
      <div className="text-sm">
        {message.content}
      </div>
      <div className="text-xs text-red-600 mt-2">
        {formatTimestamp(message.timestamp)}
      </div>
    </div>
  )

  const renderUserMessage = () => (
    <div className="flex justify-end">
      <div className="message-bubble user-message">
        <div className="whitespace-pre-wrap">{message.content}</div>
        <div className="text-xs text-blue-100 mt-2">
          {formatTimestamp(message.timestamp)}
        </div>
      </div>
    </div>
  )

  const renderAgentMessage = () => (
    <div className="flex justify-start">
      <div className="message-bubble agent-message">
        <MarkdownMessage
          content={message.content}
          isStreaming={message.isStreaming || false}
        />
        <div className="text-xs text-gray-500 mt-2">
          {formatTimestamp(message.timestamp)}
        </div>
      </div>
    </div>
  )

  const renderThinkingMessage = () => (
    <div className="message-bubble thinking-indicator">
      <div className="flex items-center">
        <div className="animate-pulse flex space-x-1 mr-2">
          <div className="w-2 h-2 bg-gray-400 rounded-full"></div>
          <div className="w-2 h-2 bg-gray-400 rounded-full"></div>
          <div className="w-2 h-2 bg-gray-400 rounded-full"></div>
        </div>
        {message.content}
      </div>
    </div>
  )

  // Don't render agent_complete messages
  if (message.type === 'agent_complete') {
    return null
  }

  switch (message.type) {
    case 'user':
      return renderUserMessage()
    case 'agent':
      return renderAgentMessage()
    case 'tool_call':
      return renderToolCall()
    case 'tool_result':
      return renderToolResult()
    case 'system':
      return renderSystemMessage()
    case 'error':
      return renderErrorMessage()
    case 'agent_thinking':
      return renderThinkingMessage()
    default:
      return (
        <div className="message-bubble system-message">
          <div className="text-xs">Unknown message type: {message.type}</div>
        </div>
      )
  }
}