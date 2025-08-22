export function formatTimestamp(timestamp: number): string {
  // Convert to milliseconds if timestamp is in seconds
  const date = new Date(timestamp > 1e10 ? timestamp : timestamp * 1000)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const messageDate = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  
  // If message is from today, show only time
  if (messageDate.getTime() === today.getTime()) {
    return date.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    })
  }
  
  // If message is from yesterday
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)
  if (messageDate.getTime() === yesterday.getTime()) {
    return `昨天 ${date.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    })}`
  }
  
  // If message is from this year, show month/day and time
  if (date.getFullYear() === now.getFullYear()) {
    return `${date.getMonth() + 1}-${date.getDate()} ${date.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    })}`
  }
  
  // For older messages, show full date and time
  return `${date.getFullYear()}-${date.getMonth() + 1}-${date.getDate()} ${date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  })}`
}