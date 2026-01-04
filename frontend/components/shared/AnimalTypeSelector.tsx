'use client'

import React, { useEffect, useState } from 'react'
import { AnimalType, AnimalTypeOption } from '@/types/chat'
import { Card } from '../ui/card'
import { Button } from '../ui/button'
import { httpClient } from '@/utils/httpClient'
import { useI18n } from '@/contexts/I18nContext'

interface AnimalTypeSelectorProps {
  onSelect: (animalType: AnimalType) => void
  onCancel: () => void
}

// Emoji mapping for animal types
const animalEmojis: Record<string, string> = {
  'dairy_cow': '🐄',
  'beef_cow': '🐂',
  'cat': '🐱',
  'dog': '🐶'
}

export function AnimalTypeSelector({ onSelect, onCancel }: AnimalTypeSelectorProps) {
  const [animalTypes, setAnimalTypes] = useState<AnimalTypeOption[]>([])
  const [selectedType, setSelectedType] = useState<AnimalType | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { t } = useI18n()

  useEffect(() => {
    fetchAnimalTypes()
  }, [])

  const fetchAnimalTypes = async () => {
    try {
      setLoading(true)
      const data = await httpClient.getJson('/animal-types')
      setAnimalTypes(data.animal_types || [])

      // Auto-select first option if available
      if (data.animal_types && data.animal_types.length > 0) {
        setSelectedType(data.animal_types[0].value)
      }
    } catch (err) {
      console.error('Error fetching animal types:', err)
      setError('Failed to load animal types')
    } finally {
      setLoading(false)
    }
  }

  const handleConfirm = () => {
    if (selectedType) {
      onSelect(selectedType)
    }
  }

  const handleCardClick = (typeValue: AnimalType) => {
    setSelectedType(typeValue)
  }

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 animate-in fade-in duration-200">
        <Card className="p-6 max-w-md w-full mx-4 shadow-2xl">
          <div className="text-center">{t('animalTypes.loading')}</div>
        </Card>
      </div>
    )
  }

  if (error) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 animate-in fade-in duration-200">
        <Card className="p-6 max-w-md w-full mx-4 shadow-2xl">
          <div className="text-center text-red-600">{error}</div>
          <Button onClick={onCancel} className="mt-4 w-full">
            {t('common.buttons.cancel')}
          </Button>
        </Card>
      </div>
    )
  }

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 animate-in fade-in duration-200"
      onClick={onCancel}
    >
      <Card
        className="p-6 max-w-md w-full mx-4 shadow-2xl animate-in zoom-in-95 duration-300"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-xl font-semibold mb-4 text-center">{t('animalTypes.selectTitle')}</h2>

        <div className="grid grid-cols-2 gap-3 mb-6">
          {animalTypes.map((type) => (
            <div
              key={type.value}
              onClick={() => handleCardClick(type.value as AnimalType)}
              className={`
                flex flex-col items-center justify-center p-4 border-2 rounded-xl cursor-pointer
                transition-all duration-200 hover:scale-105
                ${selectedType === type.value
                  ? 'border-primary bg-primary/5 shadow-md'
                  : 'border-gray-200 hover:border-primary/50 hover:bg-gray-50'
                }
              `}
            >
              <span className="text-4xl mb-2">
                {animalEmojis[type.value] || '🐾'}
              </span>
              <span className="text-sm font-medium text-center leading-tight">
                {type.label}
              </span>
            </div>
          ))}
        </div>

        <div className="flex gap-3">
          <Button onClick={onCancel} variant="outline" className="flex-1">
            {t('common.buttons.cancel')}
          </Button>
          <Button
            onClick={handleConfirm}
            disabled={!selectedType}
            className="flex-1"
          >
            {t('animalTypes.create')}
          </Button>
        </div>
      </Card>
    </div>
  )
}
