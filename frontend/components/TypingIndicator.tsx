'use client'

import { Bot } from 'lucide-react'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Card, CardContent } from '@/components/ui/card'

export default function TypingIndicator() {
  return (
    <div className="flex justify-start items-start gap-2">
      <Avatar className="w-8 h-8">
        <AvatarFallback>
          <Bot className="h-4 w-4" />
        </AvatarFallback>
      </Avatar>
      <Card className="max-w-[80%] bg-muted">
        <CardContent className="p-3">
          <div className="flex items-center space-x-1">
            <div className="flex space-x-1">
              <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce [animation-delay:-0.3s]"></div>
              <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce [animation-delay:-0.15s]"></div>
              <div className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce"></div>
            </div>
            <span className="text-muted-foreground text-sm ml-2">正在输入...</span>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}