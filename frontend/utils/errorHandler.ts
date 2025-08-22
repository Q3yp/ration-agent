/**
 * Comprehensive Error Handling and Recovery System
 * 
 * Provides centralized error classification, recovery strategies, and user-friendly messaging.
 */

export type ErrorCategory = 
  | 'network'        // Network connectivity issues
  | 'server'         // Backend server errors
  | 'validation'     // Input validation errors
  | 'session'        // Session-related errors
  | 'streaming'      // SSE streaming errors
  | 'permission'     // Authorization/permission errors
  | 'unknown'        // Unclassified errors

export interface ClassifiedError {
  category: ErrorCategory
  message: string
  userMessage: string
  isRetryable: boolean
  suggestedAction?: string
  originalError?: any
}

export interface ErrorRecoveryOptions {
  maxRetries?: number
  retryDelay?: number
  exponentialBackoff?: boolean
  onRetry?: () => void
  onMaxRetriesReached?: () => void
}

export class ErrorHandler {
  
  /**
   * Classify an error into categories for appropriate handling
   */
  static classify(error: any): ClassifiedError {
    const errorMessage = error?.message || error?.toString() || 'Unknown error'
    const lowerMessage = errorMessage.toLowerCase()

    // Network errors
    if (
      error?.name === 'TypeError' && lowerMessage.includes('fetch') ||
      lowerMessage.includes('network') ||
      lowerMessage.includes('connection refused') ||
      lowerMessage.includes('timeout') ||
      error?.name === 'AbortError'
    ) {
      return {
        category: 'network',
        message: errorMessage,
        userMessage: '网络连接出现问题，请检查网络连接后重试',
        isRetryable: true,
        suggestedAction: '检查网络连接',
        originalError: error
      }
    }

    // Server errors (HTTP status codes)
    if (lowerMessage.includes('http 5') || lowerMessage.includes('server error')) {
      return {
        category: 'server',
        message: errorMessage,
        userMessage: '服务器暂时不可用，请稍后重试',
        isRetryable: true,
        suggestedAction: '稍后重试',
        originalError: error
      }
    }

    // Session errors
    if (
      lowerMessage.includes('session not found') ||
      lowerMessage.includes('session expired') ||
      lowerMessage.includes('invalid session')
    ) {
      return {
        category: 'session',
        message: errorMessage,
        userMessage: '会话已过期，请刷新页面重新开始',
        isRetryable: false,
        suggestedAction: '刷新页面',
        originalError: error
      }
    }

    // Validation errors
    if (
      lowerMessage.includes('validation') ||
      lowerMessage.includes('invalid input') ||
      lowerMessage.includes('bad request') ||
      lowerMessage.includes('http 400')
    ) {
      return {
        category: 'validation',
        message: errorMessage,
        userMessage: '输入内容有误，请检查后重新提交',
        isRetryable: false,
        suggestedAction: '检查输入内容',
        originalError: error
      }
    }

    // Permission errors
    if (
      lowerMessage.includes('unauthorized') ||
      lowerMessage.includes('forbidden') ||
      lowerMessage.includes('http 401') ||
      lowerMessage.includes('http 403')
    ) {
      return {
        category: 'permission',
        message: errorMessage,
        userMessage: '没有权限执行此操作',
        isRetryable: false,
        suggestedAction: '联系管理员',
        originalError: error
      }
    }

    // Streaming specific errors
    if (
      lowerMessage.includes('stream') ||
      lowerMessage.includes('sse') ||
      lowerMessage.includes('event-stream')
    ) {
      return {
        category: 'streaming',
        message: errorMessage,
        userMessage: '实时连接中断，正在尝试重新连接',
        isRetryable: true,
        suggestedAction: '自动重连中',
        originalError: error
      }
    }

    // Unknown errors
    return {
      category: 'unknown',
      message: errorMessage,
      userMessage: '发生未知错误，请刷新页面重试',
      isRetryable: true,
      suggestedAction: '刷新页面或联系技术支持',
      originalError: error
    }
  }

  /**
   * Create a retry function with exponential backoff
   */
  static createRetryFunction(
    fn: () => Promise<any>,
    options: ErrorRecoveryOptions = {}
  ): () => Promise<any> {
    const {
      maxRetries = 3,
      retryDelay = 1000,
      exponentialBackoff = true,
      onRetry,
      onMaxRetriesReached
    } = options

    let retryCount = 0

    const retryFn = async (): Promise<any> => {
      try {
        const result = await fn()
        retryCount = 0 // Reset on success
        return result
      } catch (error) {
        const classified = ErrorHandler.classify(error)
        
        if (!classified.isRetryable || retryCount >= maxRetries) {
          if (retryCount >= maxRetries) {
            onMaxRetriesReached?.()
          }
          throw error
        }

        retryCount++
        const delay = exponentialBackoff 
          ? retryDelay * Math.pow(2, retryCount - 1)
          : retryDelay

        console.log(`Retry ${retryCount}/${maxRetries} after ${delay}ms:`, classified.message)
        
        onRetry?.()
        
        await new Promise(resolve => setTimeout(resolve, delay))
        return retryFn()
      }
    }

    return retryFn
  }

  /**
   * Handle file upload errors specifically
   */
  static handleFileUploadError(error: any): ClassifiedError {
    const classified = ErrorHandler.classify(error)
    
    if (classified.category === 'validation') {
      return {
        ...classified,
        userMessage: '文件格式不支持或文件过大，请检查文件类型和大小',
        suggestedAction: '选择其他文件'
      }
    }

    if (classified.category === 'server') {
      return {
        ...classified,
        userMessage: '文件上传失败，服务器暂时不可用',
        suggestedAction: '稍后重试上传'
      }
    }

    return classified
  }

  /**
   * Handle streaming connection errors
   */
  static handleStreamingError(error: any): ClassifiedError {
    const classified = ErrorHandler.classify(error)
    
    if (classified.category === 'network') {
      return {
        ...classified,
        userMessage: '实时连接中断，请检查网络连接',
        suggestedAction: '点击重试按钮重新连接'
      }
    }

    return classified
  }

  /**
   * Generate user-friendly error message for display
   */
  static formatErrorMessage(error: any): string {
    const classified = ErrorHandler.classify(error)
    
    let message = classified.userMessage
    
    if (classified.suggestedAction) {
      message += ` (建议: ${classified.suggestedAction})`
    }
    
    return message
  }

  /**
   * Check if an error should trigger automatic retry
   */
  static shouldAutoRetry(error: any): boolean {
    const classified = ErrorHandler.classify(error)
    return classified.isRetryable && 
           (classified.category === 'network' || classified.category === 'streaming')
  }

  /**
   * Get appropriate recovery action for an error
   */
  static getRecoveryAction(error: any): 'retry' | 'refresh' | 'manual' | 'none' {
    const classified = ErrorHandler.classify(error)
    
    switch (classified.category) {
      case 'network':
      case 'streaming':
        return 'retry'
      
      case 'session':
        return 'refresh'
      
      case 'server':
        return classified.isRetryable ? 'retry' : 'manual'
      
      case 'validation':
      case 'permission':
        return 'manual'
      
      default:
        return 'refresh'
    }
  }

  /**
   * Log error for debugging (development mode)
   */
  static logError(error: any, context?: string) {
    if (process.env.NODE_ENV === 'development') {
      const classified = ErrorHandler.classify(error)
      console.group(`🚨 Error ${context ? `in ${context}` : ''}`)
      console.log('Category:', classified.category)
      console.log('Message:', classified.message)
      console.log('User Message:', classified.userMessage)
      console.log('Retryable:', classified.isRetryable)
      console.log('Original Error:', classified.originalError)
      console.groupEnd()
    }
  }
}