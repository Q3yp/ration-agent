'use client'

import { useI18n } from '@/contexts/I18nContext'

interface TokenUsageProps {
  tokenUsage?: {
    prompt_tokens: number
  }
}

export function TokenUsage({ tokenUsage }: TokenUsageProps) {
  const { t } = useI18n()
  if (!tokenUsage || tokenUsage.prompt_tokens === 0) {
    return null
  }

  const formatNumber = (num: number) => {
    if (num >= 1000000) {
      return `${(num / 1000000).toFixed(1)}M`
    } else if (num >= 1000) {
      return `${(num / 1000).toFixed(1)}K`
    }
    return num.toLocaleString()
  }

  return (
    <div className="flex items-center gap-1 text-xs text-muted-foreground">
      <span className="font-mono">{formatNumber(tokenUsage.prompt_tokens)}</span>
      <span>{t('chat.tokenUsageLabel')}</span>
    </div>
  )
}
