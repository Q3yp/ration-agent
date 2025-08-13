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
  | 'role_transition'
  | 'stop'

export interface AttachedFile {
  name: string
  size: number
  path: string
}

export interface ArtifactData {
  title: string
  description: string
  html_content: string
  isLoading?: boolean
}

export interface Message {
  id: string
  type: MessageType
  content: string
  timestamp: number
  toolName?: string
  toolArgs?: Record<string, any>
  toolCallId?: string
  messageId?: string
  fullContent?: string
  isStreaming?: boolean
  attachedFiles?: AttachedFile[]
  toRole?: string
  artifactData?: ArtifactData
  actionData?: Record<string, string>
}

export interface Session {
  session_id: string
  workspace_path?: string
  created_at: string
  last_accessed?: string
  active_connections?: number
  agent_ready?: boolean
  exists?: boolean
  title?: string
}

export interface SessionHistoryMessage {
  type: string
  content: string
  full_content?: string
  action_data?: Record<string, string>
  tool_calls?: Array<{
    id: string
    name: string
    args: Record<string, any>
  }>
  tool_call_id?: string  // For tool result messages
  timestamp?: string
}

export interface SessionHistory {
  session_id: string
  messages: SessionHistoryMessage[]
  summary: {
    session_id: string
    total_messages: number
    human_messages: number
    ai_messages: number
    system_messages: number
    has_history: boolean
  }
}