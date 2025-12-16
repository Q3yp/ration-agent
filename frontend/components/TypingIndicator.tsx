'use client'

import { useState, useEffect, useRef } from 'react'
import { Bot, ChevronDown, ChevronUp, Calculator, Brain, Sparkles } from 'lucide-react'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Card, CardContent } from '@/components/ui/card'
import { useI18n } from '@/contexts/I18nContext'

interface AnalysisState {
  isActive: boolean
  content: string
  isComplete: boolean
  operationsCount?: number
  operations?: string[]  // Track all operations for rotary effect
}

interface FormulationState {
  isActive: boolean
  content: string
  isComplete: boolean
  operationsCount?: number
  operations?: string[]
  operationData?: unknown[]
}

interface ThinkingState {
  isActive: boolean
  content: string
  isComplete: boolean
}

interface TypingIndicatorProps {
  analysisState?: AnalysisState
  formulationState?: FormulationState
  thinkingState?: ThinkingState
  isTyping?: boolean
}

export default function TypingIndicator({ analysisState, formulationState, thinkingState, isTyping }: TypingIndicatorProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [thinkingExpanded, setThinkingExpanded] = useState(true) // Auto-expand while streaming
  const contentRef = useRef<HTMLDivElement>(null)
  const { t } = useI18n()

  const isAnalyzing = analysisState?.isActive || analysisState?.isComplete
  const isFormulating = formulationState?.isActive || formulationState?.isComplete
  const isThinking = thinkingState?.isActive

  // Auto-expand while thinking, collapse when done
  useEffect(() => {
    if (isThinking) {
      setThinkingExpanded(true)
    }
  }, [isThinking])

  // Track if user is at bottom of thinking content
  const isThinkingContentAtBottom = useRef(true)

  const checkThinkingContentAtBottom = () => {
    const el = contentRef.current
    if (!el) return true
    const threshold = 30 // pixels from bottom
    return el.scrollHeight - el.scrollTop - el.clientHeight < threshold
  }

  const handleThinkingScroll = () => {
    isThinkingContentAtBottom.current = checkThinkingContentAtBottom()
  }

  // Auto-scroll to bottom of thinking content while streaming, only if user is at bottom
  useEffect(() => {
    if (contentRef.current && isThinking && thinkingExpanded && isThinkingContentAtBottom.current) {
      contentRef.current.scrollTop = contentRef.current.scrollHeight
    }
  }, [thinkingState?.content, isThinking, thinkingExpanded])

  // Get operations for formulation/analysis
  const operations = (isFormulating ? formulationState?.operations : analysisState?.operations) || []
  const lastThreeOps = operations.slice(-3)

  // Render thinking block - shown independently alongside other states
  const renderThinkingBlock = () => {
    if (!isThinking) return null

    const thinkingContent = thinkingState?.content || ''
    const hasContent = thinkingContent.length > 0

    return (
      <div className="flex justify-start items-start gap-2 mb-2">
        <div className="w-8 h-8 flex items-center justify-center">
          <Brain className="h-5 w-5 text-purple-500 animate-pulse" />
        </div>

        <Card className="min-w-[200px] sm:min-w-[400px] max-w-[600px] bg-purple-50 border-purple-200">
          <CardContent className="p-3">
            <div className="space-y-2">
              <div
                className="flex items-center justify-between cursor-pointer"
                onClick={() => setThinkingExpanded(!thinkingExpanded)}
              >
                <div className="flex items-center space-x-2">
                  <div className="flex space-x-1">
                    <div className="w-2 h-2 bg-purple-400 rounded-full animate-pulse"></div>
                    <Sparkles className="w-4 h-4 text-purple-500 animate-pulse" />
                  </div>
                  <span className="text-purple-700 text-sm font-medium">
                    {t('chat.thinking') || '思考中...'}
                  </span>
                </div>
                {hasContent && (
                  <div className="flex items-center text-purple-500">
                    {thinkingExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                  </div>
                )}
              </div>

              {/* Expandable reasoning content */}
              {thinkingExpanded && hasContent && (
                <div
                  ref={contentRef}
                  onScroll={handleThinkingScroll}
                  className="mt-2 p-3 bg-purple-50 rounded-lg border border-purple-100 max-h-48 overflow-y-auto text-sm text-purple-900 font-mono leading-relaxed whitespace-pre-wrap"
                >
                  {thinkingContent}
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  // Render operations block (formulation/analysis/typing)
  const renderOperationsBlock = () => {
    // Determine which operational state to show: formulation > analysis > typing
    const operationalState = isFormulating ? 'formulation' : isAnalyzing ? 'analysis' : (isTyping ? 'typing' : 'idle')

    if (operationalState === 'idle') return null

    return (
      <div className="flex justify-start items-start gap-2">
        <div className="w-8 h-8 flex items-center justify-center">
          {(isAnalyzing || isFormulating) ? (
            <div className={`w-2 h-2 rounded-full animate-pulse ${isFormulating ? 'bg-green-400' : 'bg-blue-400'
              }`}></div>
          ) : (
            <Avatar className="w-8 h-8">
              <AvatarFallback>
                {operationalState === 'formulation' ? <Calculator className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
              </AvatarFallback>
            </Avatar>
          )}
        </div>

        <Card className={`min-w-[200px] sm:min-w-[400px] max-w-[600px] ${isFormulating ? 'bg-green-50 border-green-200' :
          isAnalyzing ? 'bg-blue-50 border-blue-200' : 'bg-muted'
          }`}>
          <CardContent className="p-3">
            {operationalState === 'formulation' ? (
              formulationState?.isComplete ? (
                // Completed formulation state
                <div className="space-y-2">
                  <div
                    className="flex items-center justify-between cursor-pointer"
                    onClick={() => setIsExpanded(!isExpanded)}
                  >
                    <div className="flex items-center space-x-1">
                      <div className="w-2 h-2 bg-green-400 rounded-full"></div>
                      <span className="text-muted-foreground text-sm ml-2">
                        {formulationState?.content}
                        {formulationState?.operationsCount &&
                          ` (${formulationState.operationsCount}项操作)`
                        }
                      </span>
                    </div>
                    {operations.length > 0 && (
                      <div className="flex items-center">
                        {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                      </div>
                    )}
                  </div>

                  {isExpanded && operations.length > 0 && (
                    <div className="mt-2 space-y-1 max-h-40 overflow-y-auto">
                      {operations.map((operation, index) => (
                        <div
                          key={`${operation}-${index}`}
                          className="flex items-center space-x-1 text-xs text-gray-500"
                        >
                          <div className="w-1 h-1 bg-gray-400 rounded-full"></div>
                          <span className="ml-2">{operation}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                // Active formulation state - show rotary operations
                <div className="space-y-1">
                  {lastThreeOps.map((operation, index) => {
                    const isNewest = index === lastThreeOps.length - 1
                    const isOldest = index === 0 && lastThreeOps.length === 3

                    return (
                      <div
                        key={`${operation}-${index}`}
                        className={`flex items-center space-x-1 transition-all duration-300 ${isOldest ? 'opacity-30 scale-95' :
                          index === 1 ? 'opacity-60 scale-97' :
                            'opacity-100 scale-100'
                          }`}
                      >
                        <div className="flex space-x-1">
                          {isNewest ? (
                            <>
                              <div className="w-2 h-2 bg-green-400 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                              <div className="w-2 h-2 bg-green-400 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                              <div className="w-2 h-2 bg-green-400 rounded-full animate-bounce"></div>
                            </>
                          ) : (
                            <div className="w-2 h-2 bg-gray-300 rounded-full"></div>
                          )}
                        </div>
                        <span className={`text-sm ml-2 ${isNewest ? 'text-muted-foreground' : 'text-gray-400'
                          }`}>
                          {operation}
                        </span>
                      </div>
                    )
                  })}
                </div>
              )
            ) : operationalState === 'analysis' ? (
              analysisState?.isComplete ? (
                // Completed analysis state
                <div className="space-y-2">
                  <div
                    className="flex items-center justify-between cursor-pointer"
                    onClick={() => setIsExpanded(!isExpanded)}
                  >
                    <div className="flex items-center space-x-1">
                      <div className="w-2 h-2 bg-blue-400 rounded-full"></div>
                      <span className="text-muted-foreground text-sm ml-2">
                        {analysisState?.content}
                        {analysisState?.operationsCount &&
                          ` (${analysisState.operationsCount}项操作)`
                        }
                      </span>
                    </div>
                    {operations.length > 0 && (
                      <div className="flex items-center">
                        {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                      </div>
                    )}
                  </div>

                  {isExpanded && operations.length > 0 && (
                    <div className="mt-2 space-y-1 max-h-40 overflow-y-auto">
                      {operations.map((operation, index) => (
                        <div
                          key={`${operation}-${index}`}
                          className="flex items-center space-x-1 text-xs text-gray-500"
                        >
                          <div className="w-1 h-1 bg-gray-400 rounded-full"></div>
                          <span className="ml-2">{operation}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                // Active analysis state - show rotary operations
                <div className="space-y-1">
                  {lastThreeOps.map((operation, index) => {
                    const isNewest = index === lastThreeOps.length - 1
                    const isOldest = index === 0 && lastThreeOps.length === 3

                    return (
                      <div
                        key={`${operation}-${index}`}
                        className={`flex items-center space-x-1 transition-all duration-300 ${isOldest ? 'opacity-30 scale-95' :
                          index === 1 ? 'opacity-60 scale-97' :
                            'opacity-100 scale-100'
                          }`}
                      >
                        <div className="flex space-x-1">
                          {isNewest ? (
                            <>
                              <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                              <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                              <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce"></div>
                            </>
                          ) : (
                            <div className="w-2 h-2 bg-gray-300 rounded-full"></div>
                          )}
                        </div>
                        <span className={`text-sm ml-2 ${isNewest ? 'text-muted-foreground' : 'text-gray-400'
                          }`}>
                          {operation}
                        </span>
                      </div>
                    )
                  })}
                </div>
              )
            ) : (
              // Regular typing state
              <div className="flex items-center space-x-1">
                <div className="flex space-x-1">
                  <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                  <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                  <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce"></div>
                </div>
                <span className="text-muted-foreground text-sm ml-2">{t('chat.responding') || '正在输入...'}</span>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {/* Thinking block - shown independently */}
      {renderThinkingBlock()}

      {/* Operations block (formulation/analysis/typing) - shown alongside thinking */}
      {renderOperationsBlock()}
    </div>
  )
}