'use client'

import { Message } from '@/types/chat'
import {
  Settings,
  CheckCircle,
  AlertCircle,
  Info,
  ChevronRight,
  User,
  Bot,
  File,
  Paperclip
} from 'lucide-react'
import { formatTimestamp } from '@/utils/formatTime'
import MarkdownMessage from './MarkdownMessage'
import { useState } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { cn } from '@/lib/utils'


interface MessageBubbleProps {
  message: Message
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const renderToolCall = () => (
    <Card className="max-w-[80%]">
      <CardContent className="p-3">
        <div
          className="flex items-center justify-between cursor-pointer"
          onClick={() => setIsExpanded(!isExpanded)}
        >
          <div className="flex items-center">
            <ChevronRight className={cn(
              "h-4 w-4 mr-1 transition-transform",
              isExpanded && "rotate-90"
            )} />
            <Settings className="h-4 w-4 mr-2" />
            <span className="font-semibold">工具调用: {message.toolName}</span>
          </div>
          <Badge variant="secondary" className="text-xs">
            {formatTimestamp(message.timestamp)}
          </Badge>
        </div>

        {/* Expandable Content */}
        {isExpanded && message.toolArgs && Object.keys(message.toolArgs).length > 0 && (
          <div className="mt-3 bg-muted p-3 rounded-md text-xs max-h-64 overflow-y-auto">
            <strong>参数:</strong>
            <pre className="mt-1 whitespace-pre-wrap font-mono">
              {JSON.stringify(message.toolArgs, null, 2)}
            </pre>
          </div>
        )}
      </CardContent>
    </Card>
  )

  const renderToolResult = () => (
    <Card className="max-w-[80%] border-green-200 bg-green-50">
      <CardContent className="p-3">
        <div
          className="flex items-center justify-between cursor-pointer"
          onClick={() => setIsExpanded(!isExpanded)}
        >
          <div className="flex items-center">
            <ChevronRight className={cn(
              "h-4 w-4 mr-1 transition-transform",
              isExpanded && "rotate-90"
            )} />
            <CheckCircle className="h-4 w-4 mr-2 text-green-600" />
            <span className="font-semibold">工具结果</span>
          </div>
          <Badge variant="outline" className="text-xs text-green-600">
            {formatTimestamp(message.timestamp)}
          </Badge>
        </div>

        {/* Expandable Content */}
        {isExpanded && (
          <div className="mt-3 bg-green-100 p-3 rounded-md text-sm max-h-64 overflow-y-auto">
            <pre className="whitespace-pre-wrap font-mono">
              {message.content}
            </pre>
          </div>
        )}
      </CardContent>
    </Card>
  )

  const renderSystemMessage = () => (
    <div className="flex justify-center">
      <Card className="max-w-md bg-muted">
        <CardContent className="p-3 text-center">
          <div className="flex items-center justify-center">
            <Info className="h-4 w-4 mr-2" />
            {message.content}
          </div>
          <div className="text-xs text-muted-foreground mt-1">
            {formatTimestamp(message.timestamp)}
          </div>
        </CardContent>
      </Card>
    </div>
  )

  const renderErrorMessage = () => (
    <Card className="max-w-[80%] border-red-200 bg-red-50">
      <CardContent className="p-3">
        <div className="flex items-center mb-2">
          <AlertCircle className="h-4 w-4 mr-2 text-red-600" />
          <span className="font-semibold text-red-600">错误</span>
        </div>
        <div className="text-sm text-red-800">
          {message.content}
        </div>
        <div className="text-xs text-red-600 mt-2">
          {formatTimestamp(message.timestamp)}
        </div>
      </CardContent>
    </Card>
  )

  const renderUserMessage = () => (
    <div className="flex justify-end items-start gap-2">
      <div className="max-w-[80%] space-y-2">
        {/* Attached Files */}
        {message.attachedFiles && message.attachedFiles.length > 0 && (
          <div className="flex justify-end">
            <Card className="bg-primary/10 border-primary/20">
              <CardContent className="p-3">
                <div className="flex items-center gap-2 mb-2">
                  <Paperclip className="h-4 w-4 text-primary" />
                  <span className="text-sm font-medium text-primary">
                    已附加 {message.attachedFiles.length} 个文件
                  </span>
                </div>
                <div className="space-y-1">
                  {message.attachedFiles.map((file, index) => (
                    <div key={index} className="flex items-center gap-2 text-sm text-muted-foreground">
                      <File className="h-3 w-3" />
                      <span className="truncate max-w-[200px]">{file.name}</span>
                      <span className="text-xs">({Math.round(file.size / 1024)}KB)</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        )}
        
        {/* Message Content */}
        <Card className="bg-primary text-primary-foreground">
          <CardContent className="p-3">
            <div className="whitespace-pre-wrap">{message.content}</div>
            <div className="text-xs opacity-70 mt-2">
              {formatTimestamp(message.timestamp)}
            </div>
          </CardContent>
        </Card>
      </div>
      <Avatar className="w-8 h-8">
        <AvatarFallback>
          <User className="h-4 w-4" />
        </AvatarFallback>
      </Avatar>
    </div>
  )

  const renderAgentMessage = () => (
    <div className="flex justify-start items-start gap-2">
      <Avatar className="w-8 h-8">
        <AvatarFallback>
          <Bot className="h-4 w-4" />
        </AvatarFallback>
      </Avatar>
      <Card className="max-w-[80%] bg-card">
        <CardContent className="p-3">
          <MarkdownMessage
            content={message.content}
            isStreaming={message.isStreaming || false}
          />
          <div className="text-xs text-muted-foreground mt-2">
            {formatTimestamp(message.timestamp)}
          </div>
        </CardContent>
      </Card>
    </div>
  )

  const renderThinkingMessage = () => (
    <div className="flex justify-start items-start gap-2">
      <Avatar className="w-8 h-8">
        <AvatarFallback>
          <Bot className="h-4 w-4" />
        </AvatarFallback>
      </Avatar>
      <Card className="max-w-[80%] bg-muted border-dashed">
        <CardContent className="p-3">
          <div className="flex items-center">
            <div className="animate-pulse flex space-x-1 mr-2">
              <div className="w-2 h-2 bg-muted-foreground rounded-full"></div>
              <div className="w-2 h-2 bg-muted-foreground rounded-full"></div>
              <div className="w-2 h-2 bg-muted-foreground rounded-full"></div>
            </div>
            <span className="text-muted-foreground italic">{message.content}</span>
          </div>
        </CardContent>
      </Card>
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
        <div className="flex justify-center">
          <Card className="max-w-md bg-muted">
            <CardContent className="p-3 text-center">
              <div className="text-xs">未知消息类型: {message.type}</div>
            </CardContent>
          </Card>
        </div>
      )
  }
}