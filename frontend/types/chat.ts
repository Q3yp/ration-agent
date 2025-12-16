export type MessageType =
  | 'user'           // User input message
  | 'agent'          // Agent response content (streamable)
  | 'thinking'       // DeepSeek reasoning content (streamable, collapsible)
  | 'tool_call'      // Tool execution indicator
  | 'tool_result'    // Tool execution result
  | 'role_transition' // Agent handoff/routing (single expandable bubble)
  | 'artifact'       // HTML artifacts for visualization (clickable)
  | 'file_export'    // File export with download capability
  | 'analysis_start' // Start of Excel analysis block
  | 'analysis_update' // Live update to Excel analysis
  | 'analysis_complete' // Final Excel analysis summary
  | 'formulation_start' // Start of feed formulation block
  | 'formulation_update' // Live update to feed formulation
  | 'formulation_complete' // Final feed formulation summary
  | 'calculation'    // Calculator tool result (formula -> result)

export type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'error'

export type MessageSource = 'history' | 'sse_stream' | 'user_input'

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

export interface FileExportData {
  filename: string
  file_type: string
  filepath: string
  description?: string
}

// Simplified message interface matching backend ParsedMessage
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
  } | undefined
}

export function getRoleTransitionMetadata(message: Message) {
  return message.metadata as {
    to_role?: string
  } | undefined
}

export function getArtifactMetadata(message: Message) {
  return message.metadata as {
    title?: string
    description?: string
    html_content?: string
  } | undefined
}

export function getFileExportMetadata(message: Message) {
  return message.metadata as {
    filename?: string
    file_type?: string
    filepath?: string
    description?: string
  } | undefined
}

export function getAnalysisMetadata(message: Message) {
  return message.metadata as {
    analysis_type?: string
    operation?: string
    operations_count?: number
    operations?: string[]
    completed?: boolean
  } | undefined
}

export function getFormulationMetadata(message: Message) {
  return message.metadata as {
    formulation_type?: string
    operation?: string
    operation_data?: any
    operations_count?: number
    operations?: string[]
    formulation_results?: any
    completed?: boolean
  } | undefined
}

export function getCalculationMetadata(message: Message) {
  return message.metadata as {
    expression?: string
    result?: string
    preferred_language?: string
    all_results?: string[]
  } | undefined
}

export type AnimalType = 'dairy_cow' | 'beef_cow' | 'cat' | 'dog'

export interface AnimalTypeOption {
  value: AnimalType
  label: string
}

export interface TokenUsage {
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
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
  animal_type?: AnimalType
  token_usage?: TokenUsage
}

