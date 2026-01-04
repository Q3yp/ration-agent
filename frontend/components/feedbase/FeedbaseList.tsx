'use client'

import { Trash2, Download, MoreHorizontal, FileText } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator
} from '@/components/ui/dropdown-menu'
import { useI18n } from '@/contexts/I18nContext'
import { getFeedbaseCopy } from './feedbaseCopy'

interface FeedbaseItem {
  name: string
  animal_type?: string
}

interface FeedbaseListProps {
  feedbases: FeedbaseItem[]
  selectedFeedbase: string | null
  onSelect: (name: string) => void
  onDelete: (name: string) => void
  onExport: (name: string) => void
}

export default function FeedbaseList({
  feedbases,
  selectedFeedbase,
  onSelect,
  onDelete,
  onExport
}: FeedbaseListProps) {
  const { locale } = useI18n()
  const copy = getFeedbaseCopy(locale)

  const getAnimalTypeLabel = (animalType?: string) => {
    const labels = copy.common.animals
    return labels[animalType || 'dairy_cow']?.label || labels.dairy_cow.label
  }

  const getAnimalTypeEmoji = (animalType?: string) => {
    const emojis = copy.common.animals
    return emojis[animalType || 'dairy_cow']?.emoji || emojis.dairy_cow.emoji
  }

  if (feedbases.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center py-12">
          <FileText className="h-12 w-12 text-muted-foreground mx-auto mb-3 opacity-50" />
          <div className="text-muted-foreground font-medium">{copy.list.emptyTitle}</div>
          <div className="text-sm text-muted-foreground mt-1">{copy.list.emptyDescription}</div>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full overflow-auto scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-gray-100 hover:scrollbar-thumb-gray-400">
      <div className="space-y-3 p-1">
        {feedbases.map((feedbase) => {
          const isSystemDefault = feedbase.name.startsWith('default_')

          return (
          <Card
            key={feedbase.name}
            className={`transition-all duration-200 hover:shadow-sm ${
              selectedFeedbase === feedbase.name
                ? 'ring-2 ring-primary shadow-sm bg-primary/5'
                : 'hover:bg-muted/30'
            }`}
          >
            <CardContent className="p-4">
              <div className="flex items-start justify-between gap-3">
                <button
                  className="flex-1 min-w-0 text-left group"
                  onClick={() => onSelect(feedbase.name)}
                  title={feedbase.name}
                >
                  <div className="font-medium text-foreground group-hover:text-primary transition-colors mb-2 flex items-center gap-2">
                    {feedbase.name}
                    {isSystemDefault && (
                      <span className="text-xs px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded font-normal">
                        {copy.list.systemTag}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-base">
                      {getAnimalTypeEmoji(feedbase.animal_type)}
                    </span>
                    <span className="text-xs px-2 py-0.5 bg-muted rounded text-muted-foreground">
                      {getAnimalTypeLabel(feedbase.animal_type)}
                    </span>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {isSystemDefault ? copy.list.viewOnly : copy.list.clickToEdit}
                  </div>
                </button>

                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 w-8 p-0 opacity-60 hover:opacity-100 transition-opacity flex-shrink-0"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <MoreHorizontal className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-32">
                    <DropdownMenuItem
                      onClick={() => onExport(feedbase.name)}
                      className="text-sm"
                    >
                      <Download className="h-4 w-4 mr-2" />
                      {copy.list.export}
                    </DropdownMenuItem>
                    {!isSystemDefault && (
                      <>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          onClick={() => onDelete(feedbase.name)}
                          className="text-red-600 focus:text-red-700 text-sm"
                        >
                          <Trash2 className="h-4 w-4 mr-2" />
                          {copy.list.delete}
                        </DropdownMenuItem>
                      </>
                    )}
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </CardContent>
          </Card>
          )
        })}
      </div>
    </div>
  )
}
