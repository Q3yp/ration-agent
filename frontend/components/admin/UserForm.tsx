'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { AlertTriangle, ArrowLeft } from 'lucide-react'
import { useAuthContext } from '@/contexts/AuthContext'

interface User {
  id: string
  email?: string | null
  username: string
  full_name?: string
  role: string
  is_active: boolean
  is_superuser: boolean
  is_verified: boolean
}

interface UserFormProps {
  user?: User | null
  onSuccess: () => void
  onCancel: () => void
}

export default function UserForm({ user, onSuccess, onCancel }: UserFormProps) {
  const { token } = useAuthContext()
  const [formData, setFormData] = useState({
    email: '',
    username: '',
    password: '',
    full_name: '',
    role: 'user',
    is_active: true,
    is_superuser: false,
    is_verified: true
  })
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const isEditing = !!user

  useEffect(() => {
    if (user) {
      setFormData({
        email: user.email || '',
        username: user.username,
        password: '', // Don't populate password for editing
        full_name: user.full_name || '',
        role: user.role,
        is_active: user.is_active,
        is_superuser: user.is_superuser,
        is_verified: user.is_verified
      })
    }
  }, [user])

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? (e.target as HTMLInputElement).checked : value
    }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setError(null)

    try {
      const url = isEditing ? `/admin/users/${user.id}` : '/admin/users'
      const method = isEditing ? 'PUT' : 'POST'
      
      // Don't send empty password for updates
      const payload: Record<string, unknown> = { ...formData }
      payload.email = formData.email.trim() || null
      if (isEditing && !payload.password) {
        delete payload.password
      }

      const response = await fetch(url, {
        method,
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      })

      if (response.ok) {
        onSuccess()
      } else {
        const errorData = await response.json()
        setError(errorData.detail || 'Failed to save user')
      }
    } catch {
      setError('Network error while saving user')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="container mx-auto p-6">
      <div className="flex items-center gap-2 mb-6">
        <Button variant="outline" size="sm" onClick={onCancel}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <h1 className="text-2xl font-bold">
          {isEditing ? '编辑用户' : '添加用户'}
        </h1>
      </div>

      <Card className="max-w-md mx-auto">
        <CardHeader>
          <CardTitle>
            {isEditing ? `编辑 ${user.username}` : '创建新用户'}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">账号邮箱（可选）</label>
              <Input
                type="text"
                name="email"
                value={formData.email}
                onChange={handleInputChange}
                disabled={isLoading}
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">用户名</label>
              <Input
                type="text"
                name="username"
                value={formData.username}
                onChange={handleInputChange}
                disabled={isLoading}
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">
                密码 {isEditing && '(留空保持原密码)'}
              </label>
              <Input
                type="password"
                name="password"
                value={formData.password}
                onChange={handleInputChange}
                disabled={isLoading}
                required={!isEditing}
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">姓名</label>
              <Input
                type="text"
                name="full_name"
                value={formData.full_name}
                onChange={handleInputChange}
                disabled={isLoading}
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">角色</label>
              <select
                name="role"
                value={formData.role}
                onChange={handleInputChange}
                disabled={isLoading}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="user">普通用户</option>
                <option value="admin">管理员</option>
              </select>
            </div>

            <div className="space-y-2">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  name="is_active"
                  checked={formData.is_active}
                  onChange={handleInputChange}
                  disabled={isLoading}
                />
                <span className="text-sm">激活</span>
              </label>

              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  name="is_superuser"
                  checked={formData.is_superuser}
                  onChange={handleInputChange}
                  disabled={isLoading}
                />
                <span className="text-sm">超级管理员</span>
              </label>

              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  name="is_verified"
                  checked={formData.is_verified}
                  onChange={handleInputChange}
                  disabled={isLoading}
                />
                <span className="text-sm">已验证</span>
              </label>
            </div>

            {error && (
              <div className="flex items-center gap-2 text-red-600 text-sm">
                <AlertTriangle size={16} />
                {error}
              </div>
            )}

            <div className="flex gap-2">
              <Button 
                type="submit" 
                disabled={isLoading}
                className="flex-1"
              >
                {isLoading ? '保存中...' : (isEditing ? '更新用户' : '创建用户')}
              </Button>
              <Button 
                type="button" 
                variant="outline" 
                onClick={onCancel}
                disabled={isLoading}
              >
                取消
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
