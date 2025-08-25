/**
 * Utility to get authentication headers for API calls
 */

export function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem('auth_token')
  return token ? { 'Authorization': `Bearer ${token}` } : {}
}

export function getAuthHeadersWithDefaults(defaultHeaders: Record<string, string> = {}): Record<string, string> {
  return {
    ...defaultHeaders,
    ...getAuthHeaders()
  }
}