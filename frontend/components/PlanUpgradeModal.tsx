'use client'

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Check } from 'lucide-react'
import { useI18n } from '@/contexts/I18nContext'

interface PlanUpgradeModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function PlanUpgradeModal({ open, onOpenChange }: PlanUpgradeModalProps) {
  const { t, tRaw } = useI18n()

  const getFeatures = (key: string): string[] => {
    const features = tRaw(key)
    return Array.isArray(features) ? features : []
  }

  const plans = [
    {
      key: 'free',
      name: t('planUpgrade.free.name'),
      price: t('planUpgrade.free.price'),
      period: t('planUpgrade.free.period'),
      features: getFeatures('planUpgrade.free.features'),
      current: true,
    },
    {
      key: 'pro',
      name: t('planUpgrade.pro.name'),
      price: t('planUpgrade.pro.price'),
      period: t('planUpgrade.pro.period'),
      features: getFeatures('planUpgrade.pro.features'),
      highlighted: true,
    },
    {
      key: 'enterprise',
      name: t('planUpgrade.enterprise.name'),
      price: t('planUpgrade.enterprise.price'),
      period: t('planUpgrade.enterprise.period'),
      features: getFeatures('planUpgrade.enterprise.features'),
    },
  ]

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-2xl font-bold text-center">
            {t('planUpgrade.title')}
          </DialogTitle>
          <DialogDescription className="text-center text-base">
            {t('planUpgrade.subtitle')}
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-6">
          {plans.map((plan) => (
            <Card
              key={plan.key}
              className={`relative ${
                plan.highlighted
                  ? 'border-primary shadow-lg scale-105'
                  : 'border-border'
              }`}
            >
              {plan.current && (
                <Badge className="absolute -top-3 left-1/2 transform -translate-x-1/2">
                  {t('chat.tierBadges.free')}
                </Badge>
              )}
              {plan.highlighted && (
                <Badge className="absolute -top-3 left-1/2 transform -translate-x-1/2 bg-primary">
                  {t('chat.tierBadges.paid')}
                </Badge>
              )}
              <CardHeader className="text-center pb-4">
                <CardTitle className="text-xl font-bold">{plan.name}</CardTitle>
                <div className="mt-4">
                  <div className="text-3xl font-bold">{plan.price}</div>
                  <div className="text-sm text-muted-foreground mt-1">
                    {plan.period}
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <ul className="space-y-3 mb-6">
                  {plan.features.map((feature, index) => (
                    <li key={index} className="flex items-start gap-2">
                      <Check className="h-5 w-5 text-primary flex-shrink-0 mt-0.5" />
                      <span className="text-sm">{feature}</span>
                    </li>
                  ))}
                </ul>
                <Button
                  className="w-full"
                  variant={plan.current ? 'outline' : 'default'}
                  disabled={!plan.current}
                >
                  {plan.current
                    ? t('chat.tierBadges.free')
                    : t('planUpgrade.comingSoon')}
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  )
}
