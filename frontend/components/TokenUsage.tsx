interface TokenUsageProps {
  tokenUsage?: {
    prompt_tokens: number
  }
}

export function TokenUsage({ tokenUsage }: TokenUsageProps) {
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
      <span>对话长度</span>
    </div>
  )
}
