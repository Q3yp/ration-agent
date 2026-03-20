'use client'

import { useRouter } from 'next/navigation'
import { useEffect, useRef } from 'react'
import { Button } from '@/components/ui/button'
import { useI18n } from '@/contexts/I18nContext'
import { LocaleToggle } from '@/components/shared/LocaleToggle'

/* ── Custom SVG icons ── */

function ConversationIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="3" y="4" width="26" height="18" rx="4" stroke="currentColor" strokeWidth="1.8" />
      <path d="M10 26L8 22H24L22 26H10Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
      <line x1="8" y1="10" x2="18" y2="10" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <line x1="8" y1="14" x2="14" y2="14" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <rect x="20" y="12" width="1.5" height="5" fill="currentColor" opacity="0.5">
        <animate attributeName="opacity" values="0.5;1;0.5" dur="1.2s" repeatCount="indefinite" />
      </rect>
    </svg>
  )
}

function ModelIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="8" cy="8" r="3" stroke="currentColor" strokeWidth="1.8" />
      <circle cx="24" cy="8" r="3" stroke="currentColor" strokeWidth="1.8" />
      <circle cx="16" cy="16" r="3" stroke="currentColor" strokeWidth="1.8" fill="currentColor" fillOpacity="0.15" />
      <circle cx="8" cy="24" r="3" stroke="currentColor" strokeWidth="1.8" />
      <circle cx="24" cy="24" r="3" stroke="currentColor" strokeWidth="1.8" />
      <line x1="10.5" y1="9.5" x2="13.5" y2="14" stroke="currentColor" strokeWidth="1.4" />
      <line x1="21.5" y1="9.5" x2="18.5" y2="14" stroke="currentColor" strokeWidth="1.4" />
      <line x1="13.5" y1="18" x2="10.5" y2="22" stroke="currentColor" strokeWidth="1.4" />
      <line x1="18.5" y1="18" x2="21.5" y2="22" stroke="currentColor" strokeWidth="1.4" />
    </svg>
  )
}

function OptimizeIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <polyline points="4,26 4,4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" opacity="0.4" />
      <polyline points="4,26 28,26" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" opacity="0.4" />
      <polyline
        points="6,22 10,18 14,20 18,12 22,10 26,8"
        stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="none"
      />
      <line x1="6" y1="8" x2="26" y2="8" stroke="currentColor" strokeWidth="1.2" strokeDasharray="3 2" opacity="0.35" />
    </svg>
  )
}

function BackgroundElements() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let animationFrameId: number

    // Configuration
    const particleCount = 180
    const connectionDistance = 120
    const particleSpeed = 0.5
    const particleRadius = 2

    class Particle {
      x: number
      y: number
      vx: number
      vy: number

      constructor(width: number, height: number) {
        this.x = Math.random() * width
        this.y = Math.random() * height
        this.vx = (Math.random() - 0.5) * particleSpeed
        this.vy = (Math.random() - 0.5) * particleSpeed
      }

      update(width: number, height: number) {
        this.x += this.vx
        this.y += this.vy

        if (this.x < 0 || this.x > width) this.vx *= -1
        if (this.y < 0 || this.y > height) this.vy *= -1
      }

      draw(ctx: CanvasRenderingContext2D) {
        ctx.beginPath()
        ctx.arc(this.x, this.y, particleRadius, 0, Math.PI * 2)
        ctx.fillStyle = 'rgba(100, 116, 139, 0.4)' // slate-500
        ctx.fill()
      }
    }

    let particles: Particle[] = []

    const initParticles = () => {
      particles = []
      for (let i = 0; i < particleCount; i++) {
        particles.push(new Particle(canvas.width, canvas.height))
      }
    }

    const resize = () => {
      canvas.width = window.innerWidth
      canvas.height = window.innerHeight
      initParticles()
    }

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height)

      // Update and draw particles
      particles.forEach(p => {
        p.update(canvas.width, canvas.height)
        p.draw(ctx)
      })

      // Draw connections
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x
          const dy = particles[i].y - particles[j].y
          const distance = Math.sqrt(dx * dx + dy * dy)

          if (distance < connectionDistance) {
            const opacity = 1 - (distance / connectionDistance)
            ctx.beginPath()
            ctx.moveTo(particles[i].x, particles[i].y)
            ctx.lineTo(particles[j].x, particles[j].y)
            ctx.strokeStyle = `rgba(100, 116, 139, ${opacity * 0.2})`
            ctx.lineWidth = 1
            ctx.stroke()
          }
        }
      }

      animationFrameId = requestAnimationFrame(draw)
    }

    window.addEventListener('resize', resize)
    resize()
    draw()

    return () => {
      window.removeEventListener('resize', resize)
      cancelAnimationFrame(animationFrameId)
    }
  }, [])

  return (
    <div className="absolute inset-0 z-0 overflow-hidden pointer-events-none">
      <canvas
        ref={canvasRef}
        className="absolute inset-0 w-full h-full opacity-60"
      />

      {/* Soft animated glows */}
      <div
        className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-indigo-200/20 mix-blend-multiply blur-[80px] animate-pulse"
        style={{ animationDuration: '8s' }}
      />
      <div
        className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] rounded-full bg-teal-200/20 mix-blend-multiply blur-[100px] animate-pulse"
        style={{ animationDuration: '10s', animationDelay: '2s' }}
      />

      {/* Fading mask to keep focus central */}
      <div className="absolute inset-0 bg-white/40 [mask-image:radial-gradient(ellipse_at_center,transparent_20%,black_100%)]" />
    </div>
  )
}

/* ── Page ── */

export default function LandingPage() {
  const router = useRouter()
  const { t } = useI18n()

  const handleEnter = () => router.push('/login')

  const capabilities = [
    {
      icon: ConversationIcon,
      title: t('landing.capabilityConversationTitle'),
      description: t('landing.capabilityConversationDescription'),
      color: "text-teal-600",
      bgColor: "bg-teal-50"
    },
    {
      icon: ModelIcon,
      title: t('landing.capabilityModelTitle'),
      description: t('landing.capabilityModelDescription'),
      color: "text-indigo-600",
      bgColor: "bg-indigo-50"
    },
    {
      icon: OptimizeIcon,
      title: t('landing.capabilityWorkflowTitle'),
      description: t('landing.capabilityWorkflowDescription'),
      color: "text-amber-600",
      bgColor: "bg-amber-50"
    },
  ]

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col relative font-sans">
      <BackgroundElements />

      {/* ── Nav ── */}
      <nav className="border-b border-slate-200/60 bg-white/70 backdrop-blur-md fixed w-full top-0 z-50 transition-all">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 flex justify-between items-center">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded border border-slate-300 bg-white flex items-center justify-center shadow-sm">
              <ModelIcon className="w-5 h-5 text-slate-700" />
            </div>
            <span className="text-base font-serif font-medium text-slate-800 tracking-wide">
              {t('common.appName')}
            </span>
          </div>
          <div className="flex gap-4 items-center">
            <LocaleToggle />
            <Button onClick={handleEnter} variant="outline" size="sm" className="font-medium bg-white/50 border-slate-300 hover:bg-slate-50">
              {t('landing.enterSystem')}
            </Button>
          </div>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section className="pt-40 sm:pt-52 pb-20 sm:pb-32 px-4 sm:px-6 flex-1 flex flex-col items-center justify-start relative z-10">
        <div className="max-w-4xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-100/80 border border-slate-200 text-xs font-medium text-slate-600 tracking-wider uppercase mb-8 shadow-sm backdrop-blur-sm">
            <span className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse" />
            NASEM 2021 Implementation
          </div>

          <h1 className="text-4xl sm:text-5xl md:text-6xl font-serif font-bold leading-[1.15] text-slate-900 tracking-tight">
            {t('landing.heroTitle')}
          </h1>
          <p className="mt-8 text-lg sm:text-xl text-slate-600 leading-relaxed max-w-2xl mx-auto font-light">
            {t('landing.heroSubtitle')}
          </p>
          <div className="mt-12 flex flex-col sm:flex-row gap-4 justify-center items-center">
            <Button onClick={handleEnter} size="lg" className="px-8 h-12 text-base font-medium shadow-md hover:shadow-lg transition-all duration-300 bg-slate-900 hover:bg-slate-800 text-white border-transparent">
              {t('landing.enterSystem')}
            </Button>
            <Button onClick={() => window.open('https://nap.nationalacademies.org/catalog/25806/nutrient-requirements-of-dairy-cattle-eighth-revised-edition', '_blank')} variant="outline" size="lg" className="px-8 h-12 text-base font-medium border-slate-300 bg-white/50 hover:bg-slate-50 transition-all duration-300 gap-2">
              {t('landing.modelPortal')}
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4 opacity-70">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                <polyline points="15 3 21 3 21 9"></polyline>
                <line x1="10" y1="14" x2="21" y2="3"></line>
              </svg>
            </Button>
          </div>
        </div>

        {/* ── Capabilities ── */}
        <div className="mt-32 w-full max-w-5xl mx-auto">
          <div className="h-px w-full bg-gradient-to-r from-transparent via-slate-200 to-transparent mb-16" />
          <div className="grid md:grid-cols-3 gap-8 sm:gap-12 relative">
            {capabilities.map(({ icon: Icon, title, description, color, bgColor }, i) => (
              <div key={title} className="group relative text-left p-8 rounded-2xl bg-white/60 border border-slate-200/60 shadow-sm backdrop-blur-sm hover:shadow-md hover:bg-white transition-all duration-300">
                <div className={`mb-6 w-14 h-14 rounded-xl flex items-center justify-center ${bgColor} ${color} ring-1 ring-inset ring-slate-900/5`}>
                  <Icon className="w-7 h-7" />
                </div>
                <h3 className="text-lg font-serif font-semibold text-slate-900 mb-3">{title}</h3>
                <p className="text-sm text-slate-600 leading-relaxed font-light">{description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="border-t border-slate-200 bg-white/50 backdrop-blur-sm relative z-10">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8 flex flex-col sm:flex-row justify-between items-center gap-4">
          <div className="text-sm font-serif text-slate-500">
            NASEM 2021 Nutrient Requirements of Dairy Cattle, 8th Edition
          </div>
          <div className="text-xs text-slate-400">
            &copy; {new Date().getFullYear()} {t('common.appName')}. All rights reserved.
          </div>
        </div>
      </footer>
    </div>
  )
}
