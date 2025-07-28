export type MessageType = 
  | 'user' 
  | 'agent' 
  | 'agent_chunk'
  | 'system' 
  | 'tool_call' 
  | 'tool_result' 
  | 'error' 
  | 'agent_thinking'
  | 'agent_complete'

export interface Message {
  id: number | string
  type: MessageType
  content: string
  timestamp: number
  toolName?: string
  toolArgs?: Record<string, any>
  toolCallId?: string
  messageId?: string
  fullContent?: string
  isStreaming?: boolean
}