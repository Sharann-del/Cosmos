'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import Image from 'next/image'

// ─── palette ────────────────────────────────────────────────────────────────
const WARM_WHITE = '#ece7dd'
const AMBER      = '#c4a46a'
const DIM        = '#5c5244'
const BORDER     = '#1e1a14'
const CARD_BG    = '#0b0906'

// ─── data ───────────────────────────────────────────────────────────────────
const SUBTITLE = 'A terminal AI chat interface for people who live in the terminal.'

const FEATURES = [
  {
    num: '01',
    title: 'Twenty-five free models',
    body: 'GPT-4o, Claude 3.5, Gemini 1.5, Llama 3, Mistral and more via OpenRouter — all free, all switchable mid-session.',
  },
  {
    num: '02',
    title: 'Real-time streaming',
    body: 'Tokens arrive as the model generates them. No spinners, no wall-of-text reveal. Read while it thinks.',
  },
  {
    num: '03',
    title: 'Rich inline output',
    body: 'Mermaid flowcharts, sequence diagrams, bar charts, tables and blockquotes render directly in the terminal. Not a monochrome dump.',
  },
  {
    num: '04',
    title: 'Persistent history',
    body: 'Every conversation lives in Supabase. Resume across sessions and devices. Organize into folders.',
  },
  {
    num: '05',
    title: 'Multiline editing',
    body: 'Full multiline input with keyboard shortcuts. Compose long prompts without fighting a single-line box. Ctrl+Enter to send.',
  },
]

const STATS: { display: string; label: string; count?: number }[] = [
  { display: '25+',  label: 'free models',      count: 25 },
  { display: '128k', label: 'context window',   count: 128 },
  { display: '$0',   label: 'to get started'              },
  { display: '∞',    label: 'conversations'               },
]

const TABS = ['home', 'chat', 'code'] as const
type Tab = typeof TABS[number]

// ─── star canvas ────────────────────────────────────────────────────────────
function StarCanvas() {
  const ref = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = ref.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    canvas.width  = canvas.offsetWidth
    canvas.height = canvas.offsetHeight

    const density = (canvas.width * canvas.height) / 6000
    const count = Math.min(Math.floor(density), 280)

    const stars = Array.from({ length: count }, () => ({
      x:     Math.random() * canvas.width,
      y:     Math.random() * canvas.height,
      r:     Math.random() * 0.8 + 0.15,
      phase: Math.random() * Math.PI * 2,
      freq:  Math.random() * 0.007 + 0.002,
    }))

    let frame = 0
    let raf: number
    const tick = () => {
      frame++
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      for (const s of stars) {
        const a = 0.08 + 0.52 * (0.5 + 0.5 * Math.sin(s.phase + frame * s.freq))
        ctx.beginPath()
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(236, 231, 221, ${a})`
        ctx.fill()
      }
      raf = requestAnimationFrame(tick)
    }
    tick()
    return () => cancelAnimationFrame(raf)
  }, [])

  return <canvas ref={ref} className="absolute inset-0 w-full h-full pointer-events-none" style={{ opacity: 0.75 }} />
}

// ─── hooks ──────────────────────────────────────────────────────────────────
function useWordReveal(text: string, delay = 70, start = 900) {
  const words = text.split(' ')
  const [count, setCount] = useState(0)

  useEffect(() => {
    const t = setTimeout(() => {
      let i = 0
      const iv = setInterval(() => {
        i++
        setCount(i)
        if (i >= words.length) clearInterval(iv)
      }, delay)
      return () => clearInterval(iv)
    }, start)
    return () => clearTimeout(t)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return { words, count }
}

function useCountUp(target: number | undefined, trigger: boolean) {
  const [val, setVal] = useState(0)

  useEffect(() => {
    if (!trigger || target === undefined || target === 0) return
    const steps = 45
    const ms    = 1100
    let step    = 0
    const iv = setInterval(() => {
      step++
      const t = step / steps
      setVal(Math.round((1 - Math.pow(1 - t, 3)) * target))
      if (step >= steps) clearInterval(iv)
    }, ms / steps)
    return () => clearInterval(iv)
  }, [target, trigger])

  return val
}

// ─── stat cell ──────────────────────────────────────────────────────────────
function StatCell({ stat, trigger }: { stat: typeof STATS[number]; trigger: boolean }) {
  const num = useCountUp(stat.count, trigger)

  const text = stat.count
    ? stat.display.replace(/\d+/, String(num))
    : stat.display

  return (
    <div className="text-center">
      <div
        className="font-crimson mb-2 leading-none"
        style={{ fontSize: 'clamp(2.5rem, 6vw, 4rem)', fontStyle: 'italic', color: WARM_WHITE }}
      >
        {text}
      </div>
      <div className="font-mono text-[9px] tracking-[0.25em] uppercase" style={{ color: DIM }}>
        {stat.label}
      </div>
    </div>
  )
}

// ─── main component ─────────────────────────────────────────────────────────
export default function Landing() {
  const [titleIn,    setTitleIn]    = useState(false)
  const [activeTab,  setActiveTab]  = useState<Tab>('home')
  const [copied,     setCopied]     = useState(false)
  const [statsReady, setStatsReady] = useState(false)

  const statsRef    = useRef<HTMLDivElement>(null)
  const featureRefs = useRef<(HTMLDivElement | null)[]>([])
  const { words, count: wordCount } = useWordReveal(SUBTITLE)

  // mount title
  useEffect(() => {
    const t = setTimeout(() => setTitleIn(true), 80)
    return () => clearTimeout(t)
  }, [])

  // scroll-reveal feature cards
  useEffect(() => {
    const io = new IntersectionObserver(
      (entries) => entries.forEach(e => {
        if (e.isIntersecting) e.target.classList.add('card-visible')
      }),
      { threshold: 0.1 }
    )
    featureRefs.current.forEach(el => el && io.observe(el))
    return () => io.disconnect()
  }, [])

  // stats trigger
  useEffect(() => {
    if (!statsRef.current) return
    const io = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) setStatsReady(true) },
      { threshold: 0.25 }
    )
    io.observe(statsRef.current)
    return () => io.disconnect()
  }, [])

  const handleCopy = () => {
    navigator.clipboard.writeText('pip install cosmos-ai').then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div className="min-h-screen" style={{ background: '#000', color: WARM_WHITE }}>
      {/* scanline */}
      <div className="scanline-overlay" />

      {/* ── nav ─────────────────────────────────────────────────────────── */}
      <nav
        className="fixed top-0 left-0 right-0 z-50 px-6 sm:px-12 py-4 flex items-center justify-between"
        style={{
          borderBottom: `1px solid ${BORDER}`,
          background: 'rgba(0,0,0,0.88)',
          backdropFilter: 'blur(12px)',
          WebkitBackdropFilter: 'blur(12px)',
        }}
      >
        <span className="font-mono text-[10px] tracking-[0.3em] uppercase" style={{ color: '#3a3228' }}>
          cosmos
        </span>
        <div className="flex items-center gap-6">
          <Link
            href="/login"
            className="font-mono text-[11px] transition-colors duration-200"
            style={{ color: DIM }}
            onMouseEnter={e => (e.currentTarget.style.color = WARM_WHITE)}
            onMouseLeave={e => (e.currentTarget.style.color = DIM)}
          >
            login
          </Link>
          <Link
            href="/signup"
            className="font-mono text-[11px] px-4 py-1.5 transition-all duration-200"
            style={{ border: `1px solid #2c2418`, color: WARM_WHITE }}
            onMouseEnter={e => {
              e.currentTarget.style.borderColor = AMBER
              e.currentTarget.style.color = AMBER
            }}
            onMouseLeave={e => {
              e.currentTarget.style.borderColor = '#2c2418'
              e.currentTarget.style.color = WARM_WHITE
            }}
          >
            sign up
          </Link>
        </div>
      </nav>

      {/* ── hero ────────────────────────────────────────────────────────── */}
      <section className="relative min-h-screen flex flex-col items-center justify-center overflow-hidden px-6">
        <StarCanvas />

        {/* radial warmth behind title */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background: `radial-gradient(ellipse 75% 55% at 50% 48%,
              rgba(24, 16, 6, 0.95) 0%,
              rgba(12, 8, 3, 0.7) 45%,
              rgba(0,0,0,1) 78%)`,
          }}
        />

        <div className="relative z-10 flex flex-col items-center text-center">
          {/* eyebrow */}
          <div
            className="font-mono text-[10px] tracking-[0.35em] uppercase mb-8"
            style={{
              color: AMBER,
              opacity: titleIn ? 1 : 0,
              transform: titleIn ? 'none' : 'translateY(10px)',
              transition: 'opacity 0.6s ease, transform 0.6s ease',
            }}
          >
            Terminal AI Chat
          </div>

          {/* COSMOS — Gloock, used only here */}
          <h1
            className="font-gloock leading-none"
            style={{
              fontSize:      'clamp(5.5rem, 17vw, 12rem)',
              letterSpacing: '-0.025em',
              color:         '#ffffff',
              opacity:       titleIn ? 1 : 0,
              transform:     titleIn ? 'translateY(0) scale(1)' : 'translateY(28px) scale(0.97)',
              transition:    'opacity 1s cubic-bezier(0.16,1,0.3,1), transform 1s cubic-bezier(0.16,1,0.3,1)',
            }}
          >
            COSMOS
          </h1>

          {/* thin amber rule under title */}
          <div
            className="mt-6 mb-10"
            style={{
              width:      titleIn ? '4rem' : '0',
              height:     '1px',
              background: AMBER,
              opacity:    0.5,
              transition: 'width 0.8s cubic-bezier(0.16,1,0.3,1) 0.3s',
            }}
          />

          {/* subtitle — Crimson Pro italic, word-by-word */}
          <p
            className="font-crimson max-w-sm leading-relaxed mb-12"
            style={{ fontSize: '1.25rem', fontStyle: 'italic', color: '#7a6e60', minHeight: '3.5rem' }}
          >
            {words.map((w, i) => (
              <span
                key={i}
                className="inline-block"
                style={{
                  marginRight: '0.3em',
                  opacity:   i < wordCount ? 1 : 0,
                  transform: i < wordCount ? 'none' : 'translateY(6px)',
                  transition: 'opacity 0.3s ease, transform 0.3s ease',
                }}
              >
                {w}
              </span>
            ))}
          </p>

          {/* CTAs */}
          <div
            className="flex items-center gap-4"
            style={{
              opacity:   titleIn ? 1 : 0,
              transform: titleIn ? 'none' : 'translateY(16px)',
              transition: 'opacity 0.8s ease 0.4s, transform 0.8s ease 0.4s',
            }}
          >
            <Link
              href="/signup"
              data-text="Get Started →"
              className="glitch-btn font-mono text-[11px] px-7 py-3 transition-all duration-300"
              style={{ border: `1px solid rgba(196,164,106,0.35)`, color: WARM_WHITE }}
              onMouseEnter={e => {
                e.currentTarget.style.borderColor = AMBER
                e.currentTarget.style.color = AMBER
              }}
              onMouseLeave={e => {
                e.currentTarget.style.borderColor = 'rgba(196,164,106,0.35)'
                e.currentTarget.style.color = WARM_WHITE
              }}
            >
              Get Started →
            </Link>
            <a
              href="https://github.com/Sharann-del/Cosmos"
              target="_blank"
              rel="noopener noreferrer"
              className="font-mono text-[11px] px-7 py-3 transition-all duration-300"
              style={{ border: `1px solid ${BORDER}`, color: DIM }}
              onMouseEnter={e => {
                e.currentTarget.style.color = '#8a7e6e'
                e.currentTarget.style.borderColor = '#2c2418'
              }}
              onMouseLeave={e => {
                e.currentTarget.style.color = DIM
                e.currentTarget.style.borderColor = BORDER
              }}
            >
              GitHub →
            </a>
          </div>
        </div>

        {/* scroll cue */}
        <div className="absolute bottom-10 left-1/2 -translate-x-1/2 flex flex-col items-center gap-1">
          <div
            className="w-px"
            style={{
              height: '3rem',
              background: `linear-gradient(to bottom, ${AMBER}, transparent)`,
              opacity: 0.3,
              animation: 'scrollPulse 2s ease-in-out infinite',
            }}
          />
        </div>
      </section>

      {/* ── screenshots ─────────────────────────────────────────────────── */}
      <section className="px-6 sm:px-12 py-24" style={{ borderTop: `1px solid ${BORDER}` }}>
        <div className="max-w-4xl mx-auto">
          <Label>Preview</Label>

          <div className="mt-10 overflow-hidden" style={{ border: `1px solid ${BORDER}` }}>
            {/* chrome bar */}
            <div
              className="px-4 py-2.5 flex items-center gap-4"
              style={{ background: CARD_BG, borderBottom: `1px solid ${BORDER}` }}
            >
              <div className="flex items-center gap-1.5">
                {[0, 1, 2].map(i => (
                  <div key={i} className="w-2.5 h-2.5 rounded-full" style={{ background: '#221c14' }} />
                ))}
              </div>
              <div className="flex items-center gap-1 ml-auto">
                {TABS.map(tab => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className="font-mono text-[10px] px-3 py-1 transition-colors duration-200"
                    style={{
                      color:      activeTab === tab ? AMBER : '#3a3028',
                      background: activeTab === tab ? 'rgba(196,164,106,0.06)' : 'transparent',
                    }}
                  >
                    {tab}
                  </button>
                ))}
              </div>
            </div>

            <div className="relative" style={{ aspectRatio: '16/9', background: CARD_BG }}>
              {TABS.map(tab => (
                <div
                  key={tab}
                  className="absolute inset-0"
                  style={{
                    opacity:       activeTab === tab ? 1 : 0,
                    pointerEvents: activeTab === tab ? 'auto' : 'none',
                    transition:    'opacity 0.25s ease',
                  }}
                >
                  <Image
                    src={`/screenshots/${tab}.png`}
                    alt={`Cosmos ${tab}`}
                    fill
                    className="object-cover"
                    priority={tab === 'home'}
                  />
                </div>
              ))}
              {/* placeholder until screenshots land */}
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <span className="font-mono text-[9px]" style={{ color: '#1e1a14' }}>
                  /screenshots/{activeTab}.png
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── features ────────────────────────────────────────────────────── */}
      <section className="px-6 sm:px-12 py-24" style={{ borderTop: `1px solid ${BORDER}` }}>
        <div className="max-w-4xl mx-auto">
          <Label>Features</Label>

          <div className="mt-14">
            {FEATURES.map((f, i) => (
              <div
                key={f.num}
                ref={el => { featureRefs.current[i] = el }}
                className="card-hidden group py-9 grid gap-5 items-start"
                style={{
                  gridTemplateColumns: 'min(72px,18vw) auto 1fr',
                  borderBottom: `1px solid ${BORDER}`,
                  transitionDelay: `${i * 70}ms`,
                }}
              >
                {/* big decorative number — Crimson Pro */}
                <span
                  className="font-crimson leading-none transition-colors duration-400 select-none"
                  style={{
                    fontSize:   'clamp(2.2rem, 5vw, 3.25rem)',
                    fontStyle:  'italic',
                    color:      '#2c231a',
                    transition: 'color 0.3s ease',
                  }}
                  ref={el => {
                    if (!el) return
                    const parent = el.closest('.group') as HTMLElement
                    if (!parent) return
                    parent.addEventListener('mouseenter', () => { el.style.color = AMBER })
                    parent.addEventListener('mouseleave', () => { el.style.color = '#2c231a' })
                  }}
                >
                  {f.num}
                </span>

                {/* title — Crimson Pro upright */}
                <h3
                  className="font-crimson pt-1"
                  style={{ fontSize: '1.15rem', lineHeight: 1.25, color: WARM_WHITE, minWidth: '170px', maxWidth: '210px' }}
                >
                  {f.title}
                </h3>

                {/* body — mono */}
                <p
                  className="font-mono leading-relaxed pt-1"
                  style={{ fontSize: '10.5px', color: DIM }}
                >
                  {f.body}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── stats ───────────────────────────────────────────────────────── */}
      <section ref={statsRef} className="px-6 sm:px-12 py-24" style={{ borderTop: `1px solid ${BORDER}` }}>
        <div className="max-w-4xl mx-auto grid grid-cols-2 sm:grid-cols-4 gap-10">
          {STATS.map(s => (
            <StatCell key={s.label} stat={s} trigger={statsReady} />
          ))}
        </div>
      </section>

      {/* ── install ─────────────────────────────────────────────────────── */}
      <section className="px-6 sm:px-12 py-24" style={{ borderTop: `1px solid ${BORDER}` }}>
        <div className="max-w-4xl mx-auto grid sm:grid-cols-2 gap-16 items-start">
          {/* left copy */}
          <div>
            <Label>Install</Label>
            <h2
              className="font-crimson mt-6 mb-4 leading-tight"
              style={{ fontSize: 'clamp(1.75rem, 4vw, 2.5rem)', fontStyle: 'italic', color: WARM_WHITE }}
            >
              Up and running
              <br />
              <span style={{ color: DIM }}>in thirty seconds.</span>
            </h2>
            <p
              className="font-mono leading-relaxed mb-10 max-w-xs"
              style={{ fontSize: '10.5px', color: DIM }}
            >
              Install via pip, run cosmos, sign in. No config files, no API keys to source yourself.
            </p>
            <Link
              href="/signup"
              className="inline-flex font-mono text-[11px] px-5 py-2.5 transition-all duration-300"
              style={{ border: `1px solid #2c2418`, color: WARM_WHITE }}
              onMouseEnter={e => {
                e.currentTarget.style.borderColor = `rgba(196,164,106,0.5)`
                e.currentTarget.style.background  = CARD_BG
              }}
              onMouseLeave={e => {
                e.currentTarget.style.borderColor = '#2c2418'
                e.currentTarget.style.background  = 'transparent'
              }}
            >
              Create account →
            </Link>
          </div>

          {/* terminal block */}
          <div style={{ border: `1px solid ${BORDER}` }}>
            <div
              className="px-4 py-2 flex items-center justify-between"
              style={{ background: CARD_BG, borderBottom: `1px solid ${BORDER}` }}
            >
              <div className="flex items-center gap-1.5">
                {[0, 1, 2].map(i => (
                  <div key={i} className="w-2 h-2 rounded-full" style={{ background: '#1c1712' }} />
                ))}
              </div>
              <button
                onClick={handleCopy}
                className="font-mono text-[10px] transition-colors duration-200"
                style={{ color: copied ? AMBER : '#3a3228' }}
              >
                {copied ? '✓ copied' : 'copy'}
              </button>
            </div>
            <div className="px-5 py-6 space-y-3" style={{ background: '#000' }}>
              <Line prompt="$" cmd="pip install cosmos-ai" />
              <Line prompt="$" cmd="cosmos" />
              <div className="pt-2 space-y-1">
                <Ghost text="✓ Connecting to OpenRouter..." />
                <Ghost text="✓ Loading chat history..." />
                <Ghost text="Welcome back." amber />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── pricing ─────────────────────────────────────────────────────── */}
      <section className="px-6 sm:px-12 py-24" style={{ borderTop: `1px solid ${BORDER}` }}>
        <div className="max-w-4xl mx-auto">
          <Label>Pricing</Label>

          <div className="mt-12 grid grid-cols-1 sm:grid-cols-2 gap-px" style={{ background: BORDER }}>
            {/* free */}
            <div className="p-8 sm:p-10" style={{ background: '#000' }}>
              <h3
                className="font-crimson mb-1"
                style={{ fontSize: '2rem', color: WARM_WHITE }}
              >
                Free
              </h3>
              <p className="font-mono text-[9px] tracking-[0.25em] mb-8" style={{ color: '#3a3228' }}>
                FOREVER
              </p>
              <ul className="space-y-3.5 mb-10">
                {[
                  '25+ free OpenRouter models',
                  'Unlimited conversations',
                  'Chat history & folders',
                  'Streaming responses',
                  'Rich terminal output',
                ].map(item => (
                  <li key={item} className="flex items-baseline gap-3">
                    <span className="font-mono text-[9px]" style={{ color: AMBER }}>—</span>
                    <span className="font-mono text-[10.5px]" style={{ color: '#8a7e6e' }}>{item}</span>
                  </li>
                ))}
              </ul>
              <Link
                href="/signup"
                className="inline-block font-mono text-[11px] px-5 py-2.5 transition-all duration-300"
                style={{ border: `1px solid #2c2418`, color: WARM_WHITE }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = `rgba(196,164,106,0.5)` }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = '#2c2418' }}
              >
                Get started
              </Link>
            </div>

            {/* pro */}
            <div className="p-8 sm:p-10" style={{ background: '#000', opacity: 0.28 }}>
              <h3
                className="font-crimson mb-1"
                style={{ fontSize: '2rem', color: WARM_WHITE }}
              >
                Pro
              </h3>
              <p className="font-mono text-[9px] tracking-[0.25em] mb-8" style={{ color: '#3a3228' }}>
                $9 / MONTH
              </p>
              <ul className="space-y-3.5 mb-10">
                {[
                  'Everything in Free',
                  'Priority model access',
                  'Extended context (200k)',
                  'Early feature access',
                ].map(item => (
                  <li key={item} className="flex items-baseline gap-3">
                    <span className="font-mono text-[9px]" style={{ color: AMBER }}>—</span>
                    <span className="font-mono text-[10.5px]" style={{ color: '#8a7e6e' }}>{item}</span>
                  </li>
                ))}
              </ul>
              <span
                className="inline-block font-mono text-[11px] px-5 py-2.5 cursor-not-allowed"
                style={{ border: `1px solid ${BORDER}`, color: '#3a3228' }}
              >
                Coming soon
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* ── footer ──────────────────────────────────────────────────────── */}
      <footer
        className="px-6 sm:px-12 py-8 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
        style={{ borderTop: `1px solid ${BORDER}` }}
      >
        <span className="font-mono text-[9px] tracking-[0.3em] uppercase" style={{ color: '#221c14' }}>
          COSMOS
        </span>
        <div className="flex items-center gap-5">
          {['Next.js', 'Supabase', 'OpenRouter'].map((t, i, arr) => (
            <span key={t} className="flex items-center gap-5">
              <span className="font-mono text-[9px]" style={{ color: '#2c2418' }}>{t}</span>
              {i < arr.length - 1 && (
                <span className="font-mono text-[9px]" style={{ color: '#1a1510' }}>·</span>
              )}
            </span>
          ))}
        </div>
      </footer>
    </div>
  )
}

// ─── small helpers ───────────────────────────────────────────────────────────
function Label({ children }: { children: string }) {
  return (
    <p className="font-mono text-[9px] tracking-[0.3em] uppercase" style={{ color: '#3a3228' }}>
      {children}
    </p>
  )
}

function Line({ prompt, cmd }: { prompt: string; cmd: string }) {
  return (
    <div className="font-mono text-xs flex items-center gap-2">
      <span style={{ color: AMBER }}>{prompt}</span>
      <span style={{ color: '#8a7e6e' }}>{cmd}</span>
    </div>
  )
}

function Ghost({ text, amber }: { text: string; amber?: boolean }) {
  return (
    <div className="font-mono text-[10px]" style={{ color: amber ? `${AMBER}99` : '#2c2418' }}>
      {text}
    </div>
  )
}
