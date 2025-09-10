'use client'

import { useState, useEffect } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { FeedData } from './FeedbaseManager'

interface FeedEditorProps {
  feedName: string
  feedData: FeedData
  onChange: (name: string, data: FeedData) => void
}

export default function FeedEditor({ feedName, feedData, onChange }: FeedEditorProps) {
  const [name, setName] = useState(feedName)
  const [dryMatterPercent, setDryMatterPercent] = useState(feedData.dm_percent.toString())
  const [costPerKg, setCostPerKg] = useState(feedData.cost_per_kg.toString())
  const [nutrients, setNutrients] = useState<Record<string, string>>(
    Object.fromEntries(
      Object.entries(feedData.nutrients).map(([key, value]) => [key, value.toString()])
    )
  )
  const [newNutrientName, setNewNutrientName] = useState('')

  // Reset state when feed changes
  useEffect(() => {
    setName(feedName)
    setDryMatterPercent(feedData.dm_percent.toString())
    setCostPerKg(feedData.cost_per_kg.toString())
    setNutrients(
      Object.fromEntries(
        Object.entries(feedData.nutrients).map(([key, value]) => [key, value.toString()])
      )
    )
    setNewNutrientName('')
  }, [feedName, feedData])

  const handleChange = (newName?: string, newDM?: string, newCost?: string, newNutrients?: Record<string, string>) => {
    const finalName = newName ?? name
    const finalDM = newDM ?? dryMatterPercent
    const finalCost = newCost ?? costPerKg
    const finalNutrients = newNutrients ?? nutrients
    
    const newFeedData: FeedData = {
      dm_percent: parseFloat(finalDM) || 0,
      cost_per_kg: parseFloat(finalCost) || 0,
      nutrients: Object.fromEntries(
        Object.entries(finalNutrients).map(([key, value]) => [key, parseFloat(value) || 0])
      )
    }

    onChange(finalName.trim(), newFeedData)
  }

  const addNutrient = () => {
    if (newNutrientName.trim() && !nutrients[newNutrientName.trim()]) {
      const updatedNutrients = {
        ...nutrients,
        [newNutrientName.trim()]: '0'
      }
      setNutrients(updatedNutrients)
      setNewNutrientName('')
      
      // Immediately call handleChange to update parent state
      handleChange(undefined, undefined, undefined, updatedNutrients)
    }
  }

  const removeNutrient = (key: string) => {
    const updatedNutrients = { ...nutrients }
    delete updatedNutrients[key]
    setNutrients(updatedNutrients)
    
    // Immediately call handleChange to update parent state
    handleChange(undefined, undefined, undefined, updatedNutrients)
  }



  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-lg font-semibold">饲料详细信息</h2>
      </div>
      
      {/* Basic Info */}
      <div className="space-y-4">
        <div className="flex items-center gap-2 pb-2 border-b">
          <h3 className="font-semibold text-foreground">基本信息</h3>
        </div>
        
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium mb-2 text-foreground">饲料名称</label>
            <Input
              value={name}
              onChange={(e) => {
                const newValue = e.target.value
                setName(newValue)
                handleChange(newValue)
              }}
              placeholder="请输入饲料名称"
              className="focus:ring-2 focus:ring-primary"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-2 text-foreground">干物质含量 (%)</label>
              <Input
                type="number"
                value={dryMatterPercent}
                onChange={(e) => {
                  const newValue = e.target.value
                  setDryMatterPercent(newValue)
                  handleChange(undefined, newValue)
                }}
                onWheel={(e) => e.currentTarget.blur()}
                placeholder="90"
                min="0"
                max="100"
                step="0.1"
                className="focus:ring-2 focus:ring-primary [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-2 text-foreground">成本 (¥/kg)</label>
              <Input
                type="number"
                value={costPerKg}
                onChange={(e) => {
                  const newValue = e.target.value
                  setCostPerKg(newValue)
                  handleChange(undefined, undefined, newValue)
                }}
                onWheel={(e) => e.currentTarget.blur()}
                placeholder="0.00"
                min="0"
                step="0.01"
                className="focus:ring-2 focus:ring-primary [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Nutrients */}
      <div className="space-y-4">
        <div className="flex items-center gap-2 pb-2 border-b">
          <h3 className="font-semibold text-foreground">营养成分</h3>
          <span className="text-xs text-muted-foreground bg-muted px-2 py-1 rounded">
            {Object.keys(nutrients).length} 项
          </span>
        </div>

        {/* Current nutrients */}
        {Object.keys(nutrients).length === 0 ? (
          <div className="flex items-center justify-center py-12 text-muted-foreground">
            <div className="text-center">
              <div className="text-sm">暂无营养成分</div>
              <div className="text-xs mt-1">使用下方输入框添加营养成分</div>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {Object.entries(nutrients).map(([key, value]) => (
              <Card key={key} className="p-3">
                <div className="flex gap-3 items-center">
                  <div className="flex-1 min-w-24">
                    <label className="block text-xs font-medium text-muted-foreground mb-1 truncate" title={key}>
                      {key}
                    </label>
                    <Input
                      type="number"
                      value={value}
                      onChange={(e) => {
                        const newValue = e.target.value
                        const updatedNutrients = { ...nutrients, [key]: newValue }
                        setNutrients(updatedNutrients)
                        handleChange(undefined, undefined, undefined, updatedNutrients)
                      }}
                      onWheel={(e) => e.currentTarget.blur()}
                      placeholder="0.0"
                      min="0"
                      step="0.01"
                      className="h-9 [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                    />
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-9 w-9 p-0 text-red-600 hover:text-red-700 hover:bg-red-50"
                    onClick={() => removeNutrient(key)}
                    title={`删除 ${key}`}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        )}

        {/* Add custom nutrient */}
        <Card className="p-3 bg-muted/30">
          <div className="flex gap-2">
            <Input
              value={newNutrientName}
              onChange={(e) => setNewNutrientName(e.target.value)}
              placeholder="输入营养成分名称（如：crude_protein）"
              onKeyPress={(e) => {
                if (e.key === 'Enter') {
                  addNutrient()
                }
              }}
              className="flex-1"
            />
            <Button 
              onClick={() => addNutrient()} 
              disabled={!newNutrientName.trim()}
              className="flex items-center gap-2"
            >
              <Plus className="h-4 w-4" />
              <span className="hidden sm:inline">添加</span>
            </Button>
          </div>
        </Card>
      </div>
    </div>
  )
}