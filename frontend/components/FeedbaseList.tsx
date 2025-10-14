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

  const getAnimalTypeLabel = (animalType?: string) => {
    const labels: Record<string, string> = {
      'dairy_cow': '奶牛',
      'beef_cow': '肉牛',
      'cat': '猫',
      'dog': '狗'
    }
    return labels[animalType || 'dairy_cow'] || '奶牛'
  }

  const getAnimalTypeEmoji = (animalType?: string) => {
    const emojis: Record<string, string> = {
      'dairy_cow': '🐄',
      'beef_cow': '🐂',
      'cat': '🐱',
      'dog': '🐶'
    }
    return emojis[animalType || 'dairy_cow'] || '🐄'
  }

  if (feedbases.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center py-12">
          <FileText className="h-12 w-12 text-muted-foreground mx-auto mb-3 opacity-50" />
          <div className="text-muted-foreground font-medium">暂无饲料库</div>
          <div className="text-sm text-muted-foreground mt-1">点击上方的「新建」按钮创建饲料库</div>
        </div>
      </div>
    )
  }

  return (
    <div className="h-full overflow-auto">
      <div className="space-y-3 p-1">
        {feedbases.map((feedbase) => (
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
                  <div className="font-medium text-foreground group-hover:text-primary transition-colors mb-2">
                    {feedbase.name}
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
                    点击编辑饲料库
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
                      导出
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      onClick={() => onDelete(feedbase.name)}
                      className="text-red-600 focus:text-red-700 text-sm"
                    >
                      <Trash2 className="h-4 w-4 mr-2" />
                      删除
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}