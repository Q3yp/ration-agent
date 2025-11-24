'use client'

import { useState, useEffect, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { MessageSquare, Eye, Loader2 } from 'lucide-react'
import { useAuthContext } from '@/contexts/AuthContext'
import { useI18n } from '@/contexts/I18nContext'
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog"
import ChatInterface from '@/components/ChatInterface'

interface Feedback {
    id: string
    user_id: string
    session_id: string
    content: string
    created_at: string
    username?: string
}

export default function FeedbackManagement() {
    const { t } = useI18n()
    const { token } = useAuthContext()
    const [feedbacks, setFeedbacks] = useState<Feedback[]>([])
    const [isLoading, setIsLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [selectedFeedback, setSelectedFeedback] = useState<Feedback | null>(null)

    const fetchFeedbacks = useCallback(async () => {
        try {
            setIsLoading(true)
            const response = await fetch('/api/admin/feedbacks', {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            })

            if (response.ok) {
                const data = await response.json()
                setFeedbacks(data)
            } else {
                setError(t('admin.errorFetch'))
            }
        } catch {
            setError(t('admin.errorNetwork'))
        } finally {
            setIsLoading(false)
        }
    }, [token, t])

    useEffect(() => {
        fetchFeedbacks()
    }, [fetchFeedbacks])

    const handleViewSession = (feedback: Feedback) => {
        setSelectedFeedback(feedback)
    }

    return (
        <div className="container mx-auto p-6">
            <div className="flex justify-between items-center mb-6">
                <div className="flex items-center gap-2">
                    <MessageSquare className="h-6 w-6" />
                    <h1 className="text-2xl font-bold">{t('admin.feedbackTitle')}</h1>
                </div>
            </div>

            {error && (
                <div className="bg-red-50 border border-red-200 rounded-md p-4 mb-6">
                    <p className="text-red-800">{error}</p>
                    <Button
                        variant="outline"
                        size="sm"
                        className="mt-2"
                        onClick={() => setError(null)}
                    >
                        {t('admin.close')}
                    </Button>
                </div>
            )}

            {isLoading ? (
                <div className="flex justify-center">
                    <Loader2 className="h-8 w-8 animate-spin" />
                </div>
            ) : (
                <div className="grid gap-4">
                    {feedbacks.map((feedback) => (
                        <Card key={feedback.id}>
                            <CardContent className="p-4">
                                <div className="flex justify-between items-start">
                                    <div className="flex-1">
                                        <div className="flex items-center gap-2 mb-2">
                                            <h3 className="font-semibold">{feedback.username || t('admin.unknownUser')}</h3>
                                            <Badge variant="outline">
                                                {new Date(feedback.created_at).toLocaleDateString()}
                                            </Badge>
                                        </div>
                                        <p className="text-sm text-gray-800 mb-2 whitespace-pre-wrap">{feedback.content}</p>
                                        <p className="text-xs text-gray-500">
                                            {t('admin.sessionId', { id: feedback.session_id })}
                                        </p>
                                    </div>
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => handleViewSession(feedback)}
                                    >
                                        <Eye className="h-4 w-4 mr-2" />
                                        {t('admin.viewSession')}
                                    </Button>
                                </div>
                            </CardContent>
                        </Card>
                    ))}

                    {feedbacks.length === 0 && (
                        <Card>
                            <CardContent className="p-8 text-center">
                                <MessageSquare className="h-12 w-12 mx-auto text-gray-400 mb-4" />
                                <p className="text-gray-600">{t('admin.noFeedbacks')}</p>
                            </CardContent>
                        </Card>
                    )}
                </div>
            )}

            <Dialog open={!!selectedFeedback} onOpenChange={(open) => !open && setSelectedFeedback(null)}>
                <DialogContent className="max-w-4xl h-[90vh] flex flex-col p-0 gap-0">
                    <DialogHeader className="p-4 border-b">
                        <DialogTitle>{t('admin.sessionHistory')}</DialogTitle>
                    </DialogHeader>
                    <div className="flex-1 overflow-hidden">
                        {selectedFeedback && (
                            <ChatInterface
                                sessionId={selectedFeedback.session_id}
                                readOnly={true}
                            />
                        )}
                    </div>
                </DialogContent>
            </Dialog>
        </div>
    )
}
