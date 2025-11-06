'use client'

import { useState, useMemo } from 'react'
import { Save, X, Plus, Trash2, FileText } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import FeedEditor from './FeedEditor'
import { Feedbase, FeedbaseData, FeedData } from './FeedbaseManager'
import { useI18n } from '@/contexts/I18nContext'
import { getFeedbaseCopy } from './feedbaseCopy'

interface FeedbaseEditorProps {
  feedbase: Feedbase
  onSave: (originalName: string, newName: string, data: FeedbaseData) => Promise<void>
  onCancel: () => void
}

type LegacyFeedData = { dry_matter_percent: number; nutrients: Record<string, number>; cost_per_kg: number }

export default function FeedbaseEditor({ feedbase, onSave, onCancel }: FeedbaseEditorProps) {
  const isSystemDefault = feedbase.name.startsWith('default_')
  const { locale } = useI18n()
  const copy = getFeedbaseCopy(locale)
  const editorCopy = copy.editor
  const commonCopy = copy.common
  const [name, setName] = useState(feedbase.name)
  const [animalType, setAnimalType] = useState(feedbase.data.animal_type || 'dairy_cow')
  
  // Normalize feed data once using useMemo
  const initialFeeds = useMemo(() => {
    const original = feedbase.data.feeds as Record<string, FeedData | LegacyFeedData>
    const normalized: Record<string, FeedData> = {}
    for (const [fname, fdata] of Object.entries(original)) {
      if (fdata && 'dry_matter_percent' in (fdata as LegacyFeedData) && !('dm_percent' in (fdata as FeedData))) {
        const { dry_matter_percent, nutrients, cost_per_kg } = fdata as LegacyFeedData
        normalized[fname] = { dm_percent: dry_matter_percent, nutrients, cost_per_kg }
      } else {
        normalized[fname] = fdata as FeedData
      }
    }
    return normalized
  }, [feedbase.data.feeds])
  
  const [feeds, setFeeds] = useState<Record<string, FeedData>>(initialFeeds)
  const [editingFeed, setEditingFeed] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSave = async () => {
    if (!name.trim()) {
      setError(editorCopy.validationName)
      return
    }

    try {
      setSaving(true)
      setError(null)
      await onSave(feedbase.name, name.trim(), {
        animal_type: animalType,
        feeds
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : editorCopy.saveError)
    } finally {
      setSaving(false)
    }
  }

  const addNewFeed = () => {
    const feedName = `${editorCopy.newFeedPrefix}${Object.keys(feeds).length + 1}`
    const newFeed: FeedData = {
      dm_percent: 90,
      nutrients: {},
      cost_per_kg: 0
    }
    
    setFeeds(prev => ({ ...prev, [feedName]: newFeed }))
    setEditingFeed(feedName)
  }

  const handleFeedChange = (newName: string, feedData: FeedData) => {
    if (!editingFeed) return
    
    setFeeds(prev => {
      const updated = { ...prev }
      
      // Remove old feed if name changed
      if (editingFeed !== newName && editingFeed in updated) {
        delete updated[editingFeed]
      }
      
      // Add/update feed with new data
      updated[newName] = feedData
      return updated
    })
    
    // Update editing feed name if it changed
    if (editingFeed !== newName) {
      setEditingFeed(newName)
    }
  }

  const selectFeed = (feedName: string) => {
    setEditingFeed(feedName)
  }

  const deleteFeed = (feedName: string) => {
    setFeeds(prev => {
      const updated = { ...prev }
      delete updated[feedName]
      return updated
    })
    
    if (editingFeed === feedName) {
      setEditingFeed(null)
    }
  }

  const feedNames = Object.keys(feeds).sort()

  const animalTypeOptions = Object.entries(commonCopy.animals)
    .filter(([value]) => value !== 'all')
    .map(([value, { label }]) => ({ value, label }))

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="space-y-4 mb-6">
      <div className="flex justify-between items-center">
        <div className="flex-1 flex gap-4 items-center">
          <div className="flex-1">
            <Input
              value={name}
              onChange={(e) => !isSystemDefault && setName(e.target.value)}
                placeholder={editorCopy.namePlaceholder}
                disabled={isSystemDefault}
                className="text-lg font-semibold border border-dashed border-muted-foreground/30 bg-transparent px-3 py-2 hover:border-muted-foreground/50 focus:border-primary focus:ring-1 focus:ring-primary/20 transition-colors disabled:opacity-70 disabled:cursor-not-allowed"
              />
            </div>
            {isSystemDefault && (
              <span className="text-xs px-2 py-1 bg-blue-100 text-blue-700 rounded">
                {editorCopy.systemBadge}
              </span>
            )}
            <div className="w-48">
              <select
                value={animalType}
                onChange={(e) => !isSystemDefault && setAnimalType(e.target.value)}
                disabled={isSystemDefault}
                className="w-full px-3 py-2 border border-muted rounded-md text-sm focus:border-primary focus:ring-1 focus:ring-primary/20 transition-colors bg-background disabled:opacity-70 disabled:cursor-not-allowed"
              >
                {animalTypeOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="flex gap-2 ml-4">
            <Button variant="outline" onClick={onCancel}>
              <X className="h-4 w-4 mr-1" />
              {isSystemDefault ? editorCopy.close : editorCopy.cancel}
            </Button>
            {!isSystemDefault && (
              <Button onClick={handleSave} disabled={saving}>
                <Save className="h-4 w-4 mr-1" />
                {saving ? editorCopy.saving : editorCopy.save}
              </Button>
            )}
          </div>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-600 text-sm">
          {error === 'Save failed' ? editorCopy.saveError : error}
        </div>
      )}

      {/* Content */}
      <div className="flex-1 min-h-0 flex flex-col lg:flex-row gap-6">
        {/* Feed List */}
        <div className="w-full lg:w-80 lg:flex-shrink-0 flex flex-col min-h-0">
          <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3 mb-4 flex-shrink-0">
            <h3 className="font-semibold text-lg">{editorCopy.feedListTitle(feedNames.length)}</h3>
            {!isSystemDefault && (
              <Button size="sm" onClick={addNewFeed} className="flex items-center gap-2">
                <Plus className="h-4 w-4" />
                <span className="hidden sm:inline">{editorCopy.addFeed}</span>
              </Button>
            )}
          </div>

          <div className="flex-1 min-h-0 overflow-auto">
            {feedNames.length === 0 ? (
              <div className="flex items-center justify-center h-full">
                <div className="text-center py-12">
                  <FileText className="h-12 w-12 text-muted-foreground mx-auto mb-3 opacity-50" />
                  <div className="text-muted-foreground font-medium">{editorCopy.emptyFeedTitle}</div>
                  <div className="text-sm text-muted-foreground mt-1">{editorCopy.emptyFeedDescription}</div>
                </div>
              </div>
            ) : (
              <div className="space-y-3 p-1">
                {feedNames.map((feedName) => (
                  <Card
                    key={feedName}
                    className={`transition-all duration-200 cursor-pointer ${
                      editingFeed === feedName 
                        ? 'ring-2 ring-primary shadow-sm bg-primary/5' 
                        : 'hover:bg-muted/30 hover:shadow-sm'
                    }`}
                  >
                    <CardContent className="p-4">
                      <div className="flex items-center justify-between gap-3">
                        <button 
                          className="flex-1 min-w-0 text-left group"
                          onClick={() => selectFeed(feedName)}
                          title={feedName}
                        >
                          <div className="font-medium text-foreground group-hover:text-primary transition-colors truncate">
                            {feedName}
                          </div>
                          <div className="text-sm text-muted-foreground mt-1">
                            {editorCopy.feedSummary(feeds[feedName].dm_percent, feeds[feedName].cost_per_kg)}
                          </div>
                        </button>
                        {!isSystemDefault && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-8 w-8 p-0 text-red-600 hover:text-red-700 opacity-60 hover:opacity-100 transition-opacity"
                            onClick={(e) => {
                              e.stopPropagation()
                              deleteFeed(feedName)
                            }}
                            title={editorCopy.deleteFeedTooltip(feedName)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Feed Editor */}
        <div className="flex-1 min-w-0 min-h-0">
          {editingFeed && feeds[editingFeed] ? (
            <div className="h-full flex flex-col">
              <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3 mb-4 pb-3 border-b">
                <h3 className="font-semibold text-lg text-foreground">{editorCopy.editHeading(editingFeed)}</h3>
              </div>
              <div className="flex-1 min-h-0 overflow-hidden">
                <div className="h-full overflow-y-auto">
                  <FeedEditor
                    feedName={editingFeed}
                    feedData={feeds[editingFeed]}
                    onChange={handleFeedChange}
                    readOnly={isSystemDefault}
                  />
                </div>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-full">
              <Card className="w-full max-w-sm">
                <CardContent className="p-8 text-center">
                  <Plus className="h-16 w-16 text-muted-foreground mx-auto mb-4 opacity-50" />
                  <h3 className="text-lg font-semibold mb-2">{editorCopy.selectFeedTitle}</h3>
                  <p className="text-muted-foreground mb-4 text-sm leading-relaxed">
                    {isSystemDefault ? editorCopy.selectFeedDescriptionReadOnly : editorCopy.selectFeedDescription}
                  </p>
                  {!isSystemDefault && (
                    <Button onClick={addNewFeed} className="w-full">
                      {editorCopy.addFeedPrimary}
                    </Button>
                  )}
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
