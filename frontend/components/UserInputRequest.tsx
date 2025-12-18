'use client'

import { useState } from 'react'
import { MessageSquare, Send, ChevronDown, ChevronUp } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { useI18n } from '@/contexts/I18nContext'

interface UserInputRequestProps {
    description?: string | null
    questions: string[]
    onSubmit: (response: string) => void
    disabled?: boolean
}

export default function UserInputRequest({ description, questions, onSubmit, disabled }: UserInputRequestProps) {
    const [answers, setAnswers] = useState<string[]>(questions.map(() => ''))
    const [isCollapsed, setIsCollapsed] = useState(false)
    const [isSubmitted, setIsSubmitted] = useState(false)
    const { locale } = useI18n()

    const headerText = locale === 'en-US' ? 'Info Request' : '请求更多信息'
    const submitText = locale === 'en-US' ? 'Submit' : '提交'

    // For collapsed header, show truncated description if available
    const getHeaderDisplay = () => {
        if (isCollapsed && description) {
            const truncated = description.length > 40 ? `${description.slice(0, 40)}...` : description
            return `${headerText}: ${truncated}`
        }
        return headerText
    }

    const handleAnswerChange = (index: number, value: string) => {
        setAnswers(prev => {
            const updated = [...prev]
            updated[index] = value
            return updated
        })
    }

    const handleSubmit = () => {
        // Combine all answers into a single response
        const nonEmptyAnswers = answers.filter(a => a.trim())
        if (nonEmptyAnswers.length > 0 && !disabled) {
            setIsSubmitted(true)
            setIsCollapsed(true)
            // Format: "Q1: answer1\nQ2: answer2" or just the answers if single question
            const response = questions.length === 1
                ? answers[0].trim()
                : questions.map((q, i) => `${q}: ${answers[i].trim()}`).join('\n')
            onSubmit(response)
        }
    }

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            handleSubmit()
        }
    }

    const hasValidAnswers = answers.some(a => a.trim())

    return (
        <div className="flex justify-start items-start gap-2">
            <div className="w-8 h-8 flex items-center justify-center">
                <MessageSquare className="h-4 w-4 text-amber-600" />
            </div>

            <Card className="min-w-[200px] sm:min-w-[400px] max-w-[600px] bg-amber-50 border-amber-200">
                <CardContent className="p-3">
                    <div className="space-y-2">
                        {/* Header - clickable to expand/collapse */}
                        <div
                            className="flex items-center justify-between cursor-pointer"
                            onClick={() => setIsCollapsed(!isCollapsed)}
                        >
                            <div className="flex items-center space-x-2">
                                <div className={`w-2 h-2 rounded-full ${isSubmitted ? 'bg-green-400' : 'bg-amber-400 animate-pulse'}`} />
                                <span className="text-amber-700 text-sm font-medium">
                                    {getHeaderDisplay()}
                                </span>
                            </div>
                            <div className="flex items-center text-amber-500">
                                {isCollapsed ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
                            </div>
                        </div>

                        {/* Expandable content */}
                        {!isCollapsed && (
                            <div className="space-y-3">
                                {/* Description text above questions */}
                                {description && !isSubmitted && (
                                    <div className="text-sm text-gray-700 leading-snug whitespace-pre-wrap pb-1">
                                        {description}
                                    </div>
                                )}

                                {/* Question + Input pairs */}
                                {!isSubmitted && (
                                    <div className="grid grid-cols-1 sm:grid-cols-[1fr_220px] gap-x-6 gap-y-4 items-start">
                                        {questions.map((question, index) => (
                                            <div key={index} className="contents">
                                                <div className="text-sm text-gray-700 pt-1 leading-snug whitespace-pre-wrap">
                                                    {question}
                                                </div>
                                                <Input
                                                    value={answers[index]}
                                                    onChange={(e) => handleAnswerChange(index, e.target.value)}
                                                    disabled={disabled}
                                                    onKeyDown={handleKeyDown}
                                                    className="w-full h-8 text-sm bg-white border-amber-200 focus:border-amber-400"
                                                />
                                            </div>
                                        ))}
                                    </div>
                                )}

                                {/* Submit button */}
                                {!isSubmitted && (
                                    <div className="flex justify-end pt-1">
                                        <Button
                                            onClick={handleSubmit}
                                            disabled={disabled || !hasValidAnswers}
                                            size="sm"
                                            className="bg-amber-500 hover:bg-amber-600 text-white"
                                        >
                                            <Send className="h-3 w-3 mr-1" />
                                            {submitText}
                                        </Button>
                                    </div>
                                )}

                                {/* Submitted indicator */}
                                {isSubmitted && (
                                    <div className="text-xs text-green-600 flex items-center gap-1">
                                        <span>✓</span>
                                        <span>{locale === 'en-US' ? 'Response submitted' : '已提交回复'}</span>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                </CardContent>
            </Card>
        </div>
    )
}

