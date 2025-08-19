export type MessageType = 
  | 'user' 
  | 'agent'
  | 'tool_call' 
  | 'tool_result' 
  | 'role_transition'
  | 'artifact'
  | 'error' 
  | 'system'

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

// Unified message interface matching backend ParsedMessage
export interface Message {
  id: string
  type: MessageType
  content: string
  timestamp: number
  metadata?: Record<string, any>
}

// Helper functions to access metadata fields with type safety
export function getToolMetadata(message: Message) {
  return message.metadata as {
    tool_name?: string
    tool_args?: Record<string, any>
    tool_id?: string
    tool_call_id?: string
  } | undefined
}

export function getRoleTransitionMetadata(message: Message) {
  return message.metadata as {
    to_role?: string
    task_description?: string
  } | undefined
}

export function getArtifactMetadata(message: Message) {
  return message.metadata as {
    title?: string
    description?: string
    html_content?: string
  } | undefined
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

