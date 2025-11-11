'use client'

import { useState, useEffect, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Plus, Edit, Trash2, Users } from 'lucide-react'
import UserForm from './UserForm'
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
  allowed_animal_types?: string[] | null
  tier: 'free' | 'paid'
  created_at: string
  updated_at: string
}

export default function UserManagement() {
  const { token } = useAuthContext()
  const [users, setUsers] = useState<User[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [editingUser, setEditingUser] = useState<User | null>(null)
  const [isDeleting, setIsDeleting] = useState<string | null>(null)
  const [editingPermissions, setEditingPermissions] = useState<string | null>(null)
  const [updatingTier, setUpdatingTier] = useState<string | null>(null)

  const animalTypeOptions = [
    { value: 'dairy_cow', label: '奶牛 Dairy Cow' },
    { value: 'beef_cow', label: '肉牛 Beef Cow' },
    { value: 'cat', label: '猫 Cat' },
    { value: 'dog', label: '狗 Dog' }
  ]

  const fetchUsers = useCallback(async () => {
    try {
      setIsLoading(true)
      const response = await fetch('/admin/users', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      if (response.ok) {
        const data = await response.json()
        setUsers(data.users)
      } else {
        setError('获取用户失败')
      }
    } catch {
      setError('获取用户列表时网络错误')
    } finally {
      setIsLoading(false)
    }
  }, [token])

  useEffect(() => {
    fetchUsers()
  }, [fetchUsers])

  const handleCreateUser = () => {
    setEditingUser(null)
    setShowForm(true)
  }

  const handleEditUser = (user: User) => {
    setEditingUser(user)
    setShowForm(true)
  }

  const handleDeleteUser = async (userId: string) => {
    if (!confirm('您确定要删除这个用户吗？')) return
    
    try {
      setIsDeleting(userId)
      const response = await fetch(`/admin/users/${userId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      if (response.ok) {
        await fetchUsers() // Refresh the list
      } else {
        const error = await response.json()
        setError(error.detail || '删除用户失败')
      }
    } catch {
      setError('删除用户时网络错误')
    } finally {
      setIsDeleting(null)
    }
  }

  const handleFormSuccess = () => {
    setShowForm(false)
    setEditingUser(null)
    fetchUsers()
  }

  const handleFormCancel = () => {
    setShowForm(false)
    setEditingUser(null)
  }

  const handleUpdateAnimalTypes = async (userId: string, selectedTypes: string[]) => {
    try {
      const response = await fetch(`/admin/users/${userId}/animal-types`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          allowed_animal_types: selectedTypes.length > 0 ? selectedTypes : null
        })
      })

      if (response.ok) {
        await fetchUsers() // Refresh the list
        setEditingPermissions(null)
      } else {
        const error = await response.json()
        setError(error.detail || '更新权限失败')
      }
    } catch {
      setError('更新权限时网络错误')
    }
  }

  const handleTierChange = async (userId: string, tier: 'free' | 'paid') => {
    try {
      setUpdatingTier(userId)
      const response = await fetch(`/admin/users/${userId}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ tier })
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || '更新账号等级失败')
      }

      setUsers(prev =>
        prev.map(user =>
          user.id === userId ? { ...user, tier } : user
        )
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : '更新账号等级失败')
    } finally {
      setUpdatingTier(null)
    }
  }

  const toggleTier = (currentTier: 'free' | 'paid') =>
    currentTier === 'paid' ? 'free' : 'paid'

  const toggleAnimalType = (user: User, animalType: string) => {
    const currentTypes = user.allowed_animal_types || []
    const newTypes = currentTypes.includes(animalType)
      ? currentTypes.filter(t => t !== animalType)
      : [...currentTypes, animalType]

    handleUpdateAnimalTypes(user.id, newTypes)
  }

  const getAnimalTypeLabel = (value: string) => {
    return animalTypeOptions.find(opt => opt.value === value)?.label || value
  }

  if (showForm) {
    return (
      <UserForm
        user={editingUser}
        onSuccess={handleFormSuccess}
        onCancel={handleFormCancel}
      />
    )
  }

  return (
    <div className="container mx-auto p-6">
      <div className="flex justify-between items-center mb-6">
        <div className="flex items-center gap-2">
          <Users className="h-6 w-6" />
          <h1 className="text-2xl font-bold">用户管理</h1>
        </div>
        <Button onClick={handleCreateUser}>
          <Plus className="h-4 w-4 mr-2" />
          添加用户
        </Button>
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
            关闭
          </Button>
        </div>
      )}

      {isLoading ? (
        <div className="flex justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
        </div>
      ) : (
        <div className="grid gap-4">
          {users.map((user) => (
            <Card key={user.id}>
              <CardContent className="p-4">
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <h3 className="font-semibold">{user.username}</h3>
                      <Badge variant={user.is_active ? 'default' : 'secondary'}>
                        {user.is_active ? '活跃' : '未激活'}
                      </Badge>
                      <button
                        type="button"
                        onClick={() => handleTierChange(user.id, toggleTier(user.tier))}
                        disabled={updatingTier === user.id}
                        className="focus:outline-none"
                        title="点击切换账号等级"
                        aria-label="切换账号等级"
                      >
                        <Badge variant={user.tier === 'paid' ? 'default' : 'secondary'}>
                          {updatingTier === user.id
                            ? '更新中...'
                            : user.tier === 'paid'
                              ? '付费'
                              : '免费'}
                        </Badge>
                      </button>
                      {user.is_superuser && (
                        <Badge variant="destructive">管理员</Badge>
                      )}
                      {user.is_verified && (
                        <Badge variant="outline">已验证</Badge>
                      )}
                    </div>
                    {user.email && (
                      <p className="text-sm text-gray-600 mb-1">{user.email}</p>
                    )}
                    {user.full_name && (
                      <p className="text-sm text-gray-600 mb-1">{user.full_name}</p>
                    )}
                    <p className="text-xs text-gray-500 mb-2">
                      创建时间: {new Date(user.created_at).toLocaleDateString('zh-CN')}
                    </p>

                    {/* Animal Type Permissions */}
                    <div className="mt-2">
                      <p className="text-xs text-gray-500 mb-1">动物类型权限:</p>
                      {editingPermissions === user.id ? (
                        <div className="flex flex-wrap gap-2">
                          {animalTypeOptions.map((option) => {
                            const isSelected = user.allowed_animal_types?.includes(option.value) || false
                            return (
                              <label
                                key={option.value}
                                className="flex items-center gap-1 cursor-pointer"
                              >
                                <input
                                  type="checkbox"
                                  checked={isSelected}
                                  onChange={() => toggleAnimalType(user, option.value)}
                                  className="rounded"
                                />
                                <span className="text-xs">{option.label}</span>
                              </label>
                            )
                          })}
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setEditingPermissions(null)}
                            className="h-6 text-xs"
                          >
                            完成
                          </Button>
                        </div>
                      ) : (
                        <div className="flex flex-wrap gap-1">
                          {!user.allowed_animal_types || user.allowed_animal_types.length === 0 ? (
                            <Badge variant="secondary" className="text-xs">
                              全部权限
                            </Badge>
                          ) : (
                            user.allowed_animal_types.map((type) => (
                              <Badge key={type} variant="outline" className="text-xs">
                                {getAnimalTypeLabel(type)}
                              </Badge>
                            ))
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setEditingPermissions(user.id)}
                            className="h-6 text-xs"
                          >
                            编辑
                          </Button>
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleEditUser(user)}
                    >
                      <Edit className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleDeleteUser(user.id)}
                      disabled={isDeleting === user.id}
                    >
                      {isDeleting === user.id ? (
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-gray-900"></div>
                      ) : (
                        <Trash2 className="h-4 w-4" />
                      )}
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
          
          {users.length === 0 && (
            <Card>
              <CardContent className="p-8 text-center">
                <Users className="h-12 w-12 mx-auto text-gray-400 mb-4" />
                <p className="text-gray-600">未找到用户</p>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}
