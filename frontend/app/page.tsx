'use client'

import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Sparkles, Brain, Database, TrendingUp, ChevronRight } from 'lucide-react'
import { useI18n } from '@/contexts/I18nContext'
import { LocaleToggle } from '@/components/shared/LocaleToggle'

export default function LandingPage() {
  const router = useRouter()
  const { t } = useI18n()

  const handleGetStarted = () => router.push('/login')

  const renderTags = (key: string, variant: 'primary' | 'secondary' = 'primary') => {
    const tags = t(key).split(',').map(tag => tag.trim())
    const base =
      variant === 'primary'
        ? 'bg-primary/10 text-primary'
        : 'bg-blue-100 text-blue-700'
    return tags.map((tag, index) => (
      <span key={index} className={`${base} text-xs px-3 py-1 rounded-full`}>
        {tag}
      </span>
    ))
  }

  const heroSubtitle = t('landing.heroSubtitle')

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      {/* Floating Language Toggle - Mobile only */}
      <div className="sm:hidden fixed top-16 right-4 z-50">
        <LocaleToggle />
      </div>

      <nav className="border-b bg-white/80 backdrop-blur-sm fixed w-full top-0 z-50">
        <div className="max-w-7xl mx-auto px-3 sm:px-6 py-3 sm:py-4 flex justify-between items-center">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 sm:h-6 sm:w-6 text-primary" />
            <span className="text-base sm:text-xl font-bold bg-gradient-to-r from-primary to-primary/70 bg-clip-text text-transparent truncate">
              {t('common.appName')}
            </span>
          </div>
          <div className="flex gap-2 items-center">
            <div className="hidden sm:block">
              <LocaleToggle />
            </div>
            <Button onClick={handleGetStarted} variant="default" size="sm" className="sm:size-default">
              {t('common.buttons.login')}
            </Button>
          </div>
        </div>
      </nav>

      <section className="pt-32 pb-20 px-6">
        <div className="max-w-7xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 bg-primary/10 text-primary px-4 py-2 rounded-full mb-6">
            <Sparkles className="h-4 w-4" />
            <span className="text-sm font-medium">{t('landing.heroBadge')}</span>
          </div>

          <h1 className="text-5xl md:text-6xl font-bold mb-6 bg-gradient-to-r from-gray-900 via-gray-800 to-gray-700 bg-clip-text text-transparent">
            {t('landing.heroTitle')}
          </h1>

          <p className="text-xl text-gray-600 mb-8 max-w-3xl mx-auto whitespace-pre-line">
            {heroSubtitle}
          </p>

          <div className="flex gap-4 justify-center">
            <Button size="lg" onClick={handleGetStarted} className="group">
              {t('common.buttons.getStarted')}
              <ChevronRight className="ml-2 h-4 w-4 group-hover:translate-x-1 transition-transform" />
            </Button>
          </div>

          <div className="mt-16 grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl mx-auto text-left">
            <div className="bg-white rounded-xl p-6 shadow-md border-2 border-primary/20">
              <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
                <span className="text-2xl">🏢</span>
                {t('landing.useCases.enterpriseTitle')}
              </h3>
              <p className="text-gray-600 text-sm mb-3">
                {t('landing.useCases.enterpriseDescription')}
              </p>
              <div className="flex gap-2">
                {renderTags('landing.useCases.enterpriseTags', 'primary')}
              </div>
            </div>

            <div className="bg-white rounded-xl p-6 shadow-md border-2 border-blue-200">
              <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
                <span className="text-2xl">🏠</span>
                {t('landing.useCases.personalTitle')}
              </h3>
              <p className="text-gray-600 text-sm mb-3">
                {t('landing.useCases.personalDescription')}
              </p>
              <div className="flex gap-2">
                {renderTags('landing.useCases.personalTags', 'secondary')}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="py-20 px-6 bg-white">
        <div className="max-w-7xl mx-auto">
          <h2 className="text-3xl md:text-4xl font-bold text-center mb-4">
            {t('landing.featuresTitle')}
          </h2>
          <p className="text-center text-gray-600 mb-12 max-w-2xl mx-auto whitespace-pre-line">
            {t('landing.featuresSubtitle')}
          </p>

          <div className="grid md:grid-cols-3 gap-8">
            <Card className="border-2 hover:border-primary/50 transition-colors">
              <CardContent className="pt-6">
                <div className="h-12 w-12 bg-primary/10 rounded-lg flex items-center justify-center mb-4">
                  <Brain className="h-6 w-6 text-primary" />
                </div>
                <h3 className="text-xl font-semibold mb-2">{t('landing.featureNaturalTitle')}</h3>
                <p className="text-gray-600">
                  {t('landing.featureNaturalDescription')}
                </p>
              </CardContent>
            </Card>

            <Card className="border-2 hover:border-primary/50 transition-colors">
              <CardContent className="pt-6">
                <div className="h-12 w-12 bg-primary/10 rounded-lg flex items-center justify-center mb-4">
                  <Database className="h-6 w-6 text-primary" />
                </div>
                <h3 className="text-xl font-semibold mb-2">{t('landing.featureKnowledgeTitle')}</h3>
                <p className="text-gray-600">
                  {t('landing.featureKnowledgeDescription')}
                </p>
              </CardContent>
            </Card>

            <Card className="border-2 hover:border-primary/50 transition-colors">
              <CardContent className="pt-6">
                <div className="h-12 w-12 bg-primary/10 rounded-lg flex items-center justify-center mb-4">
                  <TrendingUp className="h-6 w-6 text-primary" />
                </div>
                <h3 className="text-xl font-semibold mb-2">{t('landing.featureAutomationTitle')}</h3>
                <p className="text-gray-600">
                  {t('landing.featureAutomationDescription')}
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      <section className="py-20 px-6 bg-gray-50">
        <div className="max-w-7xl mx-auto">
          <h2 className="text-3xl md:text-4xl font-bold text-center mb-4">
            {t('landing.howItWorksTitle')}
          </h2>
          <p className="text-center text-gray-600 mb-12 max-w-2xl mx-auto whitespace-pre-line">
            {t('landing.howItWorksSubtitle')}
          </p>

          <div className="grid md:grid-cols-3 gap-8">
            {[
              {
                step: '1',
                title: t('landing.stepDescribeTitle'),
                description: t('landing.stepDescribeDescription'),
              },
              {
                step: '2',
                title: t('landing.stepProcessTitle'),
                description: t('landing.stepProcessDescription'),
              },
              {
                step: '3',
                title: t('landing.stepResultTitle'),
                description: t('landing.stepResultDescription'),
              },
            ].map(({ step, title, description }) => (
              <div key={step} className="text-center">
                <div className="w-16 h-16 bg-primary text-white rounded-full flex items-center justify-center text-2xl font-bold mx-auto mb-4">
                  {step}
                </div>
                <h3 className="text-xl font-semibold mb-2">{title}</h3>
                <p className="text-gray-600">
                  {description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}
