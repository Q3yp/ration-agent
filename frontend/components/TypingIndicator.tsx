'use client'

import { useState } from 'react'
import { Bot, ChevronDown, ChevronUp, Calculator } from 'lucide-react'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Card, CardContent } from '@/components/ui/card'

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

interface TypingIndicatorProps {
  analysisState?: AnalysisState
  formulationState?: FormulationState
  isTyping?: boolean
}

export default function TypingIndicator({ analysisState, formulationState, isTyping }: TypingIndicatorProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const isAnalyzing = analysisState?.isActive || analysisState?.isComplete
  const isFormulating = formulationState?.isActive || formulationState?.isComplete

  // Determine which state takes priority: formulation > analysis > typing (when isTyping is true)
  const currentState = isFormulating ? 'formulation' : isAnalyzing ? 'analysis' : (isTyping ? 'typing' : 'idle')

  // Get operations for current state
  const operations = (currentState === 'formulation' ? formulationState?.operations : analysisState?.operations) || []
  const lastThreeOps = operations.slice(-3)

  return (
    <div className="flex justify-start items-start gap-2">
      <div className="w-8 h-8 flex items-center justify-center">
        {(isAnalyzing || isFormulating) ? (
          <div className={`w-2 h-2 rounded-full animate-pulse ${
            isFormulating ? 'bg-green-400' : 'bg-blue-400'
          }`}></div>
        ) : (
          <Avatar className="w-8 h-8">
            <AvatarFallback>
              {currentState === 'formulation' ? <Calculator className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
            </AvatarFallback>
          </Avatar>
        )}
      </div>
      
      <Card className={`min-w-[200px] sm:min-w-[400px] max-w-[600px] ${
        isFormulating ? 'bg-green-50 border-green-200' :
        isAnalyzing ? 'bg-blue-50 border-blue-200' : 'bg-muted'
      }`}>
        <CardContent className="p-3">
          {currentState === 'formulation' ? (
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
                      className={`flex items-center space-x-1 transition-all duration-300 ${
                        isOldest ? 'opacity-30 scale-95' : 
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
                      <span className={`text-sm ml-2 ${
                        isNewest ? 'text-muted-foreground' : 'text-gray-400'
                      }`}>
                        {operation}
                      </span>
                    </div>
                  )
                })}
              </div>
            )
          ) : currentState === 'analysis' ? (
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
                      className={`flex items-center space-x-1 transition-all duration-300 ${
                        isOldest ? 'opacity-30 scale-95' : 
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
                      <span className={`text-sm ml-2 ${
                        isNewest ? 'text-muted-foreground' : 'text-gray-400'
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
              <span className="text-muted-foreground text-sm ml-2">正在输入...</span>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}