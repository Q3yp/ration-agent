/**
 * HTTP Client with automatic 401 handling and authentication
 */

import { getAuthHeadersWithDefaults } from './authHeaders'

interface HttpClientOptions {
  baseUrl?: string
  timeout?: number
  onUnauthorized?: () => void
}

interface RequestOptions extends RequestInit {
  headers?: Record<string, string>
  timeout?: number
}

class HttpClient {
  private baseUrl: string
  private timeout: number
  private onUnauthorized: (() => void) | null

  constructor(options: HttpClientOptions = {}) {
    this.baseUrl = options.baseUrl || ''
    this.timeout = options.timeout || 30000
    this.onUnauthorized = options.onUnauthorized || this.defaultUnauthorizedHandler
  }

  private defaultUnauthorizedHandler = () => {
    // Clear auth token and redirect to login
    localStorage.removeItem('auth_token')
    if (typeof window !== 'undefined') {
      window.location.href = '/login'
    }
  }

  private async makeRequest(url: string, options: RequestOptions = {}): Promise<Response> {
    const fullUrl = url.startsWith('http') ? url : `${this.baseUrl}${url}`
    
    // Add authentication headers
    const headers = getAuthHeadersWithDefaults(options.headers || {})
    
    // Setup timeout
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), options.timeout || this.timeout)
    
    try {
      const response = await fetch(fullUrl, {
        ...options,
        headers,
        signal: options.signal || controller.signal
      })
      
      clearTimeout(timeoutId)
      
      // Handle 401 unauthorized
      if (response.status === 401) {
        this.onUnauthorized?.()
        throw new Error('Unauthorized: Please log in again')
      }
      
      return response
    } catch (error) {
      clearTimeout(timeoutId)
      
      // Handle AbortError from timeout
      if (error instanceof Error && error.name === 'AbortError') {
        throw new Error('Request timeout')
      }
      
      throw error
    }
  }

  async get(url: string, options: RequestOptions = {}): Promise<Response> {
    return this.makeRequest(url, { ...options, method: 'GET' })
  }

  async post(url: string, data?: any, options: RequestOptions = {}): Promise<Response> {
    const body = data ? JSON.stringify(data) : undefined
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers
    }
    
    return this.makeRequest(url, {
      ...options,
      method: 'POST',
      headers,
      body
    })
  }

  async put(url: string, data?: any, options: RequestOptions = {}): Promise<Response> {
    const body = data ? JSON.stringify(data) : undefined
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers
    }
    
    return this.makeRequest(url, {
      ...options,
      method: 'PUT',
      headers,
      body
    })
  }

  async patch(url: string, data?: any, options: RequestOptions = {}): Promise<Response> {
    const body = data ? JSON.stringify(data) : undefined
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers
    }
    
    return this.makeRequest(url, {
      ...options,
      method: 'PATCH',
      headers,
      body
    })
  }

  async delete(url: string, options: RequestOptions = {}): Promise<Response> {
    return this.makeRequest(url, { ...options, method: 'DELETE' })
  }

  // Convenience methods that handle JSON parsing and error responses
  async getJson<T = any>(url: string, options: RequestOptions = {}): Promise<T> {
    const response = await this.get(url, options)
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }
    return response.json()
  }

  async postJson<T = any>(url: string, data?: any, options: RequestOptions = {}): Promise<T> {
    const response = await this.post(url, data, options)
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }
    return response.json()
  }

  async putJson<T = any>(url: string, data?: any, options: RequestOptions = {}): Promise<T> {
    const response = await this.put(url, data, options)
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }
    return response.json()
  }

  async patchJson<T = any>(url: string, data?: any, options: RequestOptions = {}): Promise<T> {
    const response = await this.patch(url, data, options)
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }
    return response.json()
  }

  async deleteJson<T = any>(url: string, options: RequestOptions = {}): Promise<T> {
    const response = await this.delete(url, options)
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }
    return response.json()
  }

  // Special method for streaming responses (like SSE)
  async stream(url: string, options: RequestOptions = {}): Promise<Response> {
    const headers = {
      'Accept': 'text/event-stream',
      ...options.headers
    }
    
    const response = await this.makeRequest(url, {
      ...options,
      headers
    })
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }
    
    return response
  }
}

const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || '/api'
const backendBaseUrl = process.env.NEXT_PUBLIC_BACKEND_URL || apiBaseUrl

// Create default instance for API routes (handled by Next.js)
const httpClient = new HttpClient({
  baseUrl: apiBaseUrl
})

// Create instance for external backend – falls back to API proxy when explicit URL not provided
const backendClient = new HttpClient({
  baseUrl: backendBaseUrl
})

export { HttpClient, httpClient, backendClient }
export default httpClient
