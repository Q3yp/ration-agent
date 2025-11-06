'use client'

import { useState, useEffect, useMemo } from 'react'
import { Plus, AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import FeedbaseList from './FeedbaseList'
import FeedbaseEditor from './FeedbaseEditor'
import { useAuthContext } from '@/contexts/AuthContext'
import { useI18n } from '@/contexts/I18nContext'
import { getFeedbaseCopy } from './feedbaseCopy'

export interface FeedData {
  dm_percent: number
  nutrients: Record<string, number>
  cost_per_kg: number
}

export interface FeedbaseData {
  animal_type?: string
  feeds: Record<string, FeedData>
}

export interface Feedbase {
  name: string
  data: FeedbaseData
}

const PLACEHOLDER_NAMES = ['新饲料库', 'New Feedbase']

export default function FeedbaseManager() {
  const { token } = useAuthContext()
  const { locale } = useI18n()
  const copy = useMemo(() => getFeedbaseCopy(locale), [locale])
  const [feedbases, setFeedbases] = useState<string[]>([])
  const [feedbasesData, setFeedbasesData] = useState<Record<string, FeedbaseData>>({})
  const [selectedFeedbase, setSelectedFeedbase] = useState<Feedbase | null>(null)
  const [isEditing, setIsEditing] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [animalTypeFilter, setAnimalTypeFilter] = useState<string>('all')
  const placeholderNames = useMemo(() => new Set([...PLACEHOLDER_NAMES, copy.manager.newFeedbaseName]), [copy.manager.newFeedbaseName])

  // Helper function to get auth headers
  const getAuthHeaders = () => ({
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  })

  // Load feedbases list
  const loadFeedbases = async () => {
    try {
      setLoading(true)
      const response = await fetch('/api/feedbases/list', {
        headers: getAuthHeaders()
      })

      if (!response.ok) {
        throw new Error('Failed to load feedbases')
      }

      const data = await response.json()
      const feedbaseNames = data.feedbases || []
      setFeedbases(feedbaseNames)

      // Load data for each feedbase to get animal_type
      const feedbasesDataMap: Record<string, FeedbaseData> = {}
      for (const name of feedbaseNames) {
        try {
          const fbResponse = await fetch(`/api/feedbases/${encodeURIComponent(name)}`, {
            headers: getAuthHeaders()
          })
          if (fbResponse.ok) {
            const fbData = await fbResponse.json()
            feedbasesDataMap[name] = fbData.data
          }
        } catch {
          // Skip if individual feedbase fails to load
        }
      }
      setFeedbasesData(feedbasesDataMap)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  // Load specific feedbase
  const loadFeedbase = async (name: string) => {
    try {
      const response = await fetch(`/api/feedbases/${encodeURIComponent(name)}`, {
        headers: getAuthHeaders()
      })
      
      if (!response.ok) {
        throw new Error(`Failed to load feedbase: ${name}`)
      }
      
      const feedbase = await response.json()
      setSelectedFeedbase(feedbase)
      setIsEditing(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    }
  }

  // Save feedbase
  const saveFeedbase = async (originalName: string, newName: string, data: FeedbaseData) => {
    try {
      // If name changed, we need to delete the old one and create a new one
      if (originalName !== newName) {
        // Delete the old feedbase if it exists and is not a new one
        if (!placeholderNames.has(originalName) && feedbases.includes(originalName)) {
          const deleteResponse = await fetch(`/api/feedbases/${encodeURIComponent(originalName)}`, {
            method: 'DELETE',
            headers: getAuthHeaders()
          })
          
          if (!deleteResponse.ok) {
            throw new Error(`Failed to delete old feedbase: ${originalName}`)
          }
        }
      }
      
      // Save with the new name
      const response = await fetch(`/api/feedbases/${encodeURIComponent(newName)}`, {
        method: 'PUT',
        headers: getAuthHeaders(),
        body: JSON.stringify({ data })
      })
      
      if (!response.ok) {
        throw new Error(`Failed to save feedbase: ${newName}`)
      }
      
      // Refresh the feedbases list
      await loadFeedbases()
      setIsEditing(false)
      setSelectedFeedbase(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
      throw err
    }
  }

  // Delete feedbase
  const deleteFeedbase = async (name: string) => {
    const confirmMessage = copy.manager.confirmDelete.replace('{{name}}', name)
    if (!confirm(confirmMessage)) {
      return
    }

    try {
      const response = await fetch(`/api/feedbases/${encodeURIComponent(name)}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      })
      
      if (!response.ok) {
        throw new Error(`Failed to delete feedbase: ${name}`)
      }
      
      // Refresh the feedbases list
      await loadFeedbases()
      
      // Clear selection if we deleted the currently selected feedbase
      if (selectedFeedbase?.name === name) {
        setSelectedFeedbase(null)
        setIsEditing(false)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    }
  }

  // Export feedbase as Excel
  const exportFeedbase = async (name: string) => {
    try {
      const response = await fetch(`/api/feedbases/${encodeURIComponent(name)}/export`, {
        headers: getAuthHeaders()
      })
      
      if (!response.ok) {
        throw new Error(`Failed to export feedbase: ${name}`)
      }
      
      // Get the filename from the Content-Disposition header, or use a default
      const contentDisposition = response.headers.get('Content-Disposition')
      let filename = `${name}.xlsx`
      if (contentDisposition) {
        // First try to extract UTF-8 encoded filename
        const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/)
        if (utf8Match) {
          try {
            filename = decodeURIComponent(utf8Match[1])
          } catch {
            // Fall back to regular filename if decoding fails
            const regularMatch = contentDisposition.match(/filename=([^;]+)/)
            if (regularMatch) {
              filename = regularMatch[1].replace(/"/g, '').trim()
            }
          }
        } else {
          // Use regular filename if no UTF-8 version found
          const regularMatch = contentDisposition.match(/filename=([^;]+)/)
          if (regularMatch) {
            filename = regularMatch[1].replace(/"/g, '').trim()
          }
        }
      }
      
      // Create blob and download
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed')
    }
  }


  // Create new feedbase
  const createNew = () => {
    const newFeedbase: Feedbase = {
      name: copy.manager.newFeedbaseName,
      data: {
        animal_type: 'dairy_cow', // Default to dairy_cow
        feeds: {}
      }
    }
    setSelectedFeedbase(newFeedbase)
    setIsEditing(true)
  }

  // Load feedbases on component mount
  useEffect(() => {
    loadFeedbases()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex flex-col items-center gap-3">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
          <div className="text-muted-foreground">{copy.manager.loading}</div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <div className="flex items-center gap-2 text-red-600">
          <AlertCircle className="h-5 w-5" />
          <span>{copy.manager.errorPrefix}: {error}</span>
        </div>
        <Button onClick={() => { setError(null); loadFeedbases() }} variant="outline">
          {copy.manager.retry}
        </Button>
      </div>
    )
  }

  // Filter feedbases by animal type
  const animalOptions = copy.common.animals

  const filteredFeedbases = animalTypeFilter === 'all'
    ? feedbases
    : feedbases.filter(name => feedbasesData[name]?.animal_type === animalTypeFilter)

  // Transform feedbase names to objects with animal_type
  const feedbaseItems = filteredFeedbases.map(name => ({
    name,
    animal_type: feedbasesData[name]?.animal_type
  }))

  return (
    <div className="h-full flex flex-col lg:flex-row gap-6">
      {/* Sidebar - Feedbase List */}
      <div className="w-full lg:w-80 lg:flex-shrink-0">
        <div className="h-full flex flex-col">
          <div className="flex flex-col gap-3 mb-4 pb-3 border-b">
            <div className="flex sm:justify-between sm:items-center gap-3">
              <h2 className="text-lg font-semibold text-foreground">{copy.manager.sidebarTitle}</h2>
              <Button
                size="sm"
                onClick={createNew}
                className="flex items-center gap-2"
              >
                <Plus className="h-4 w-4" />
                <span className="hidden sm:inline">{copy.manager.createButton}</span>
              </Button>
            </div>

            {/* Animal type filter */}
            <div className="flex gap-2 flex-wrap">
              {Object.entries(animalOptions).map(([type, { label }]) => (
                <button
                  key={type}
                  onClick={() => setAnimalTypeFilter(type)}
                  className={`px-3 py-1 text-xs rounded-full transition-colors ${
                    animalTypeFilter === type
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted text-muted-foreground hover:bg-muted/80'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div className="flex-1 min-h-0">
            <FeedbaseList
              feedbases={feedbaseItems}
              selectedFeedbase={selectedFeedbase?.name || null}
              onSelect={loadFeedbase}
              onDelete={deleteFeedbase}
              onExport={exportFeedbase}
            />
          </div>
        </div>
      </div>

      {/* Main content - Feedbase Editor */}
      <div className="flex-1 min-w-0 min-h-0">
        {isEditing && selectedFeedbase ? (
          <FeedbaseEditor
            key={selectedFeedbase.name}
            feedbase={selectedFeedbase}
            onSave={saveFeedbase}
            onCancel={() => {
              setIsEditing(false)
              setSelectedFeedbase(null)
            }}
          />
        ) : (
          <div className="flex items-center justify-center h-full">
            <Card className="w-full max-w-sm">
              <CardContent className="p-8 text-center">
                <Plus className="h-16 w-16 text-muted-foreground mx-auto mb-4 opacity-50" />
                <h3 className="text-lg font-semibold mb-2">{copy.manager.emptyStateTitle}</h3>
                <p className="text-muted-foreground mb-4 text-sm leading-relaxed">
                  {copy.manager.emptyStateDescription}
                </p>
                <Button onClick={createNew} className="w-full">
                  {copy.manager.createPrimary}
                </Button>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </div>
  )
}
