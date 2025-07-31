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
  CornerDownRight
} from 'lucide-react'
import { formatTimestamp } from '@/utils/formatTime'
import { getRoleInfo } from '@/utils/roleMapping'
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
  
  // Parse file upload tags from message content
  const parseFileUploads = (content: string) => {
    const fileUploadRegex = /\[FILE_UPLOAD\](.*?)\[\/FILE_UPLOAD\]/g;
    const fileUploads: string[] = [];
    let match;
    
    while ((match = fileUploadRegex.exec(content)) !== null) {
      fileUploads.push(match[1]);
    }
    
    // Remove file upload tags from content
    const cleanContent = content.replace(fileUploadRegex, '').trim();
    
    return { fileUploads, cleanContent };
  };
  const renderToolCall = () => (
    <Card className="max-w-[80%] min-w-0 overflow-hidden">
      <CardContent className="p-3">
        <div
          className="flex items-center justify-between cursor-pointer"
          onClick={() => setIsExpanded(!isExpanded)}
        >
          <div className="flex items-center min-w-0">
            <ChevronRight className={cn(
              "h-4 w-4 mr-1 transition-transform flex-shrink-0",
              isExpanded && "rotate-90"
            )} />
            <Settings className="h-4 w-4 mr-2 flex-shrink-0" />
            <span className="font-semibold truncate">工具调用: {message.toolName}</span>
          </div>
          <Badge variant="secondary" className="text-xs flex-shrink-0 ml-2">
            {formatTimestamp(message.timestamp)}
          </Badge>
        </div>

        {/* Expandable Content */}
        {isExpanded && message.toolArgs && Object.keys(message.toolArgs).length > 0 && (
          <div className="mt-3 bg-muted p-3 rounded-md text-xs max-h-64 overflow-auto w-full min-w-0">
            <strong>参数:</strong>
            <pre className="mt-1 whitespace-pre-wrap font-mono break-all word-break-all overflow-wrap-anywhere min-w-0">
              {JSON.stringify(message.toolArgs, null, 2)}
            </pre>
          </div>
        )}
      </CardContent>
    </Card>
  )

  const renderToolResult = () => (
    <Card className="max-w-[80%] min-w-0 overflow-hidden border-green-200 bg-green-50">
      <CardContent className="p-3">
        <div
          className="flex items-center justify-between cursor-pointer"
          onClick={() => setIsExpanded(!isExpanded)}
        >
          <div className="flex items-center min-w-0">
            <ChevronRight className={cn(
              "h-4 w-4 mr-1 transition-transform flex-shrink-0",
              isExpanded && "rotate-90"
            )} />
            <CheckCircle className="h-4 w-4 mr-2 text-green-600 flex-shrink-0" />
            <span className="font-semibold truncate">工具结果</span>
          </div>
          <Badge variant="outline" className="text-xs text-green-600 flex-shrink-0 ml-2">
            {formatTimestamp(message.timestamp)}
          </Badge>
        </div>

        {/* Expandable Content */}
        {isExpanded && (
          <div className="mt-3 bg-green-100 p-3 rounded-md text-sm max-h-64 overflow-auto w-full min-w-0">
            <pre className="whitespace-pre-wrap font-mono break-all word-break-all overflow-wrap-anywhere min-w-0">
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
    <Card className="max-w-[80%] min-w-0 overflow-hidden border-red-200 bg-red-50">
      <CardContent className="p-3">
        <div className="flex items-center mb-2">
          <AlertCircle className="h-4 w-4 mr-2 text-red-600" />
          <span className="font-semibold text-red-600">错误</span>
        </div>
        <div className="text-sm text-red-800 break-words overflow-wrap-anywhere">
          {message.content}
        </div>
        <div className="text-xs text-red-600 mt-2">
          {formatTimestamp(message.timestamp)}
        </div>
      </CardContent>
    </Card>
  )

  const renderUserMessage = () => {
    const { fileUploads, cleanContent } = parseFileUploads(message.content);
    
    return (
      <div className="flex justify-end items-start gap-2">
        <div className="max-w-[80%] space-y-2">
          {/* File Uploads from message content */}
          {fileUploads.length > 0 && (
            <div className="flex justify-end">
              <Card className="bg-blue-50 border-blue-200">
                <CardContent className="p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <File className="h-4 w-4 text-blue-600" />
                    <span className="text-sm font-medium text-blue-600">
                      文件上传 ({fileUploads.length} 个)
                    </span>
                  </div>
                  <div className="space-y-1">
                    {fileUploads.map((fileName, index) => (
                      <div key={`${fileName}-${index}`} className="flex items-center gap-2 text-sm text-blue-700">
                        <File className="h-3 w-3" />
                        <span className="truncate max-w-[200px]">{fileName}</span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
          
          {/* Message Content (cleaned of file upload tags) */}
          {cleanContent && (
            <Card className="bg-primary text-primary-foreground">
              <CardContent className="p-3">
                <div className="whitespace-pre-wrap">{cleanContent}</div>
                <div className="text-xs opacity-70 mt-2">
                  {formatTimestamp(message.timestamp)}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
        <Avatar className="w-8 h-8">
          <AvatarFallback>
            <User className="h-4 w-4" />
          </AvatarFallback>
        </Avatar>
      </div>
    )
  }

  const renderAgentMessage = () => (
    <div className="flex justify-start items-start gap-2">
      <Avatar className="w-8 h-8">
        <AvatarFallback>
          <Bot className="h-4 w-4" />
        </AvatarFallback>
      </Avatar>
      <Card className="max-w-[80%] min-w-0 overflow-hidden bg-card">
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
      <Card className="max-w-[80%] min-w-0 overflow-hidden bg-muted border-dashed">
        <CardContent className="p-3">
          <div className="flex items-center">
            <div className="animate-pulse flex space-x-1 mr-2">
              <div className="w-2 h-2 bg-muted-foreground rounded-full"></div>
              <div className="w-2 h-2 bg-muted-foreground rounded-full"></div>
              <div className="w-2 h-2 bg-muted-foreground rounded-full"></div>
            </div>
            <span className="text-muted-foreground italic break-words overflow-wrap-anywhere">{message.content}</span>
          </div>
        </CardContent>
      </Card>
    </div>
  )

  const renderRoleTransition = () => {
    const roleInfo = getRoleInfo(message.toRole || '')
    const RoleIcon = roleInfo.icon
    
    return (
      <div className="flex justify-start items-start gap-2">
        <div className="w-8 h-8 flex items-center justify-center">
          <CornerDownRight className="h-4 w-4 text-gray-500" />
        </div>
        <Card
          className={cn("max-w-[80%] min-w-0 overflow-hidden", !roleInfo.customStyles && roleInfo.bgColor)}
          style={roleInfo.customStyles ? {
            backgroundColor: roleInfo.customStyles.backgroundColor,
            borderColor: roleInfo.customStyles.borderColor,
            borderWidth: '1px'
          } : undefined}
        >
          <CardContent className="p-3">
            <div className="flex items-center gap-2">
              <RoleIcon 
                className={cn("h-4 w-4", !roleInfo.customStyles && roleInfo.color)} 
                style={roleInfo.customStyles ? { color: roleInfo.customStyles.color } : undefined}
              />
              <span 
                className={cn("font-medium", !roleInfo.customStyles && roleInfo.color)}
                style={roleInfo.customStyles ? { color: roleInfo.customStyles.color } : undefined}
              >
                {roleInfo.transitionMessage}
              </span>
            </div>
            <div 
              className={cn("text-xs mt-1", !roleInfo.customStyles && roleInfo.color.replace('700', '600'))}
              style={roleInfo.customStyles ? { color: roleInfo.customStyles.color, opacity: 0.7 } : undefined}
            >
              {formatTimestamp(message.timestamp)}
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

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
    case 'role_transition':
      return renderRoleTransition()
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