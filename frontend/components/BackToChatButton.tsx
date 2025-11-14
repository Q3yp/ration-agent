'use client'

import Link from 'next/link'
import { ArrowLeft } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface BackToChatButtonProps {
  href?: string
  label: string
  className?: string
}

export default function BackToChatButton({
  href = '/chat',
  label,
  className,
}: BackToChatButtonProps) {
  return (
    <Button
      asChild
      variant="outline"
      size="sm"
      className={cn('inline-flex items-center gap-2 h-9 px-3 font-medium', className)}
    >
      <Link href={href}>
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        <span className="text-sm">{label}</span>
      </Link>
    </Button>
  )
}
