'use client'

import { useEffect, useRef } from 'react'
import Image from 'next/image'
import Link from 'next/link'

// ─── data ────────────────────────────────────────────────────────────────────
const FEATURES = [
  {
    n:    '01',
    head: 'Twenty-five free models.',
    body: 'GPT, Claude, Gemini, Llama, Mistral and more — all free, all via OpenRouter. Switch mid-session.',
  },
  {
    n:    '02',
    head: 'History that sticks.',
    body: 'Every conversation synced to the cloud. Organized into folders. Always there when you come back.',
  },
  {
    n:    '03',
    head: 'Attach anything.',
    body: 'Drop in images, PDFs, DOCX, or any text file. The model sees it all.',
  },
  {
    n:    '04',
    head: 'Rich output, rendered.',
    body: 'Mermaid diagrams, bar charts, tables, and full Markdown — rendered inline, right in the terminal.',
  },
]

// ─── component ───────────────────────────────────────────────────────────────
export default function Landing() {
  const revealRefs = useRef<(HTMLElement | null)[]>([])

  useEffect(() => {
    const io = new IntersectionObserver(
      entries => entries.forEach(e => {
        if (e.isIntersecting) e.target.classList.add('feature-visible')
      }),
      { threshold: 0.08 },
    )
    revealRefs.current.forEach(el => el && io.observe(el))
    return () => io.disconnect()
  }, [])

  const addRef = (i: number) => (el: HTMLElement | null) => {
    revealRefs.current[i] = el
  }

  return (
    <div style={{ background: '#000', color: '#fff', overflowX: 'hidden' }}>

      {/* ────────────────────────── HERO ───────────────────────── */}
      <section style={{
        minHeight:      '100vh',
        display:        'flex',
        flexDirection:  'column',
        justifyContent: 'center',
        alignItems:     'center',
        textAlign:      'center',
        padding:        '0 2rem',
        position:       'relative',
      }}>
        {/* very faint vignette so the edges recede */}
        <div style={{
          position:      'absolute',
          inset:         0,
          background:    'radial-gradient(ellipse 90% 80% at 50% 60%, transparent 40%, #000 100%)',
          pointerEvents: 'none',
        }} />

        <h1
          className="font-gloock"
          style={{
            fontSize:   'clamp(6.5rem, 20vw, 18rem)',
            lineHeight: 0.92,
            letterSpacing: '-0.03em',
            color:      '#fff',
            margin:     '0 0 2.5rem',
            position:   'relative',
            animationName:            'cosmosEntry',
            animationDuration:        '1.4s',
            animationTimingFunction:  'cubic-bezier(0.16, 1, 0.3, 1)',
            animationFillMode:        'both',
            animationDelay:           '0.05s',
          }}
        >
          Cosmos
        </h1>

        <p
          className="font-crimson"
          style={{
            fontSize:   'clamp(1.1rem, 2vw, 1.4rem)',
            fontStyle:  'normal',
            color:      '#444',
            margin:     '0 0 3.5rem',
            lineHeight: 1,
            whiteSpace: 'nowrap',
            position:   'relative',
            animationName:           'cosmosEntry',
            animationDuration:       '1.2s',
            animationTimingFunction: 'cubic-bezier(0.16, 1, 0.3, 1)',
            animationFillMode:       'both',
            animationDelay:          '0.35s',
          }}
        >
          A terminal AI chat interface for people who live in the terminal.
        </p>

        <div style={{
          display:  'flex',
          gap:      '2.5rem',
          alignItems: 'center',
          position: 'relative',
          animationName:           'cosmosEntry',
          animationDuration:       '1s',
          animationTimingFunction: 'cubic-bezier(0.16, 1, 0.3, 1)',
          animationFillMode:       'both',
          animationDelay:          '0.6s',
        }}>
          <Link
            href="/signup"
            className="font-crimson"
            style={{ fontSize: '1.2rem', color: '#fff', textDecoration: 'none', borderBottom: '1px solid #fff', paddingBottom: '2px', transition: 'color 0.2s, border-color 0.2s' }}
            onMouseEnter={e => { e.currentTarget.style.color = '#888'; e.currentTarget.style.borderColor = '#888' }}
            onMouseLeave={e => { e.currentTarget.style.color = '#fff'; e.currentTarget.style.borderColor = '#fff' }}
          >
            Get started →
          </Link>
          <Link
            href="/login"
            className="font-crimson"
            style={{ fontSize: '1.2rem', color: '#333', textDecoration: 'none', transition: 'color 0.2s' }}
            onMouseEnter={e => { e.currentTarget.style.color = '#666' }}
            onMouseLeave={e => { e.currentTarget.style.color = '#333' }}
          >
            Log in
          </Link>
        </div>

      </section>

      {/* ───────────────────────── VIDEO ───────────────────────── */}
      <section style={{ position: 'relative', lineHeight: 0 }}>
        {/* glow above — bleeds upward from video's top edge */}
        <div style={{
          position:      'absolute',
          top:           '-10vw',
          left:          '-5%',
          right:         '-5%',
          height:        '24vw',
          background:    `radial-gradient(
            ellipse 80% 100% at 50% 100%,
            rgba(220, 220, 220, 0.75) 0%,
            rgba(180, 180, 180, 0.45) 35%,
            rgba(120, 120, 120, 0.20) 65%,
            transparent 88%
          )`,
          mixBlendMode:  'screen',
          pointerEvents: 'none',
          zIndex:        0,
        }} />

        <video
          src="/screenshots/animation.mp4"
          autoPlay
          muted
          loop
          playsInline
          style={{ width: '100%', display: 'block', position: 'relative', zIndex: 1 }}
        />

        {/* glow below — bleeds downward from video's bottom edge */}
        <div style={{
          position:      'absolute',
          bottom:        '-10vw',
          left:          '-5%',
          right:         '-5%',
          height:        '24vw',
          background:    `radial-gradient(
            ellipse 80% 100% at 50% 0%,
            rgba(220, 220, 220, 0.75) 0%,
            rgba(180, 180, 180, 0.45) 35%,
            rgba(120, 120, 120, 0.20) 65%,
            transparent 88%
          )`,
          mixBlendMode:  'screen',
          pointerEvents: 'none',
          zIndex:        0,
        }} />
      </section>

      {/* ─────────────────────── MANIFESTO ─────────────────────── */}
      <section
        ref={addRef(0)}
        className="feature-hidden"
        style={{ padding: '16vh 8vw 14vh', borderTop: '1px solid #0d0d0d' }}
      >
        <p className="font-crimson" style={{
          fontSize:      'clamp(2.2rem, 5.5vw, 5rem)',
          fontStyle:     'italic',
          fontWeight:    400,
          color:         '#fff',
          lineHeight:    1.15,
          maxWidth:      '18ch',
          margin:        0,
          letterSpacing: '-0.01em',
        }}>
          Built for the terminal.{' '}
          <span style={{ color: '#2a2a2a' }}>Not around it.</span>
        </p>
      </section>

      {/* ─────────────────────── FEATURES ──────────────────────── */}
      <section style={{ borderTop: '1px solid #0d0d0d' }}>
        {FEATURES.map((f, i) => (
          <div
            key={f.n}
            ref={addRef(i + 1)}
            className="feature-hidden"
            style={{
              display:         'grid',
              gridTemplateColumns: 'min(5rem, 10vw) 1fr min(40%, 34rem)',
              gap:             '0 4vw',
              alignItems:      'start',
              padding:         '6vh 8vw',
              borderBottom:    '1px solid #0d0d0d',
              transitionDelay: `${i * 60}ms`,
            }}
          >
            {/* number */}
            <span className="font-crimson" style={{ fontSize: '0.85rem', color: '#222', fontStyle: 'italic', paddingTop: '0.6rem' }}>
              {f.n}
            </span>

            {/* heading */}
            <h2 className="font-crimson" style={{
              fontSize:      'clamp(2.4rem, 5vw, 4.8rem)',
              fontStyle:     'italic',
              fontWeight:    400,
              color:         '#fff',
              margin:        0,
              lineHeight:    1.05,
              letterSpacing: '-0.02em',
            }}>
              {f.head}
            </h2>

            {/* body */}
            <p className="font-crimson" style={{
              fontSize:   'clamp(0.95rem, 1.3vw, 1.2rem)',
              fontWeight: 400,
              color:      '#444',
              margin:     0,
              lineHeight: 1.65,
              paddingTop: '0.5rem',
            }}>
              {f.body}
            </p>
          </div>
        ))}
      </section>

      {/* ────────────────────── SCREENSHOT ─────────────────────── */}
      <section
        ref={addRef(FEATURES.length + 1)}
        className="feature-hidden"
        style={{ padding: '14vh 8vw', borderTop: '1px solid #0d0d0d' }}
      >
        <p className="font-crimson" style={{
          fontSize:      '0.9rem',
          fontStyle:     'italic',
          color:         '#333',
          margin:        '0 0 3rem',
          letterSpacing: '0.02em',
        }}>
          The conversation interface.
        </p>

        <div style={{
          border:       '1px solid #111',
          overflow:     'hidden',
          position:     'relative',
          lineHeight:   0,
          maxWidth:     '100%',
        }}>
          {/* fake terminal chrome */}
          <div style={{
            background:   '#0a0a0a',
            borderBottom: '1px solid #111',
            padding:      '0.75rem 1rem',
            display:      'flex',
            alignItems:   'center',
            gap:          '0.5rem',
            lineHeight:   1,
          }}>
            {[0,1,2].map(i => (
              <div key={i} style={{ width: 9, height: 9, borderRadius: '50%', background: '#1a1a1a' }} />
            ))}
            <span className="font-crimson" style={{ fontSize: '0.75rem', fontStyle: 'italic', color: '#222', marginLeft: '0.75rem' }}>
              cosmos — chat
            </span>
          </div>

          <Image
            src="/screenshots/chat.png"
            alt="Cosmos chat interface"
            width={1600}
            height={900}
            style={{ width: '100%', height: 'auto', display: 'block' }}
            priority
          />
        </div>
      </section>

      {/* ──────────────────────── INSTALL ──────────────────────── */}
      <section
        ref={addRef(FEATURES.length + 2)}
        className="feature-hidden"
        style={{
          padding:       '14vh 8vw',
          borderTop:     '1px solid #0d0d0d',
          display:       'grid',
          gridTemplateColumns: '1fr 1fr',
          gap:           '6vw',
          alignItems:    'center',
        }}
      >
        {/* left: copy */}
        <div>
          <h2 className="font-crimson" style={{
            fontSize:      'clamp(2rem, 4.5vw, 4rem)',
            fontStyle:     'italic',
            fontWeight:    400,
            color:         '#fff',
            margin:        '0 0 1.5rem',
            lineHeight:    1.1,
            letterSpacing: '-0.02em',
          }}>
            Up and running in thirty seconds.
          </h2>
          <p className="font-crimson" style={{ fontSize: '1.1rem', color: '#444', margin: '0 0 2.5rem', lineHeight: 1.65, maxWidth: '28rem' }}>
            Install via pip, sign in, and you&apos;re talking to twenty-five models before your coffee cools.
          </p>
          <Link
            href="/signup"
            className="font-crimson"
            style={{ fontSize: '1.15rem', color: '#fff', textDecoration: 'none', borderBottom: '1px solid #333', paddingBottom: '2px', transition: 'border-color 0.2s' }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = '#fff' }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = '#333' }}
          >
            Create an account →
          </Link>
        </div>

        {/* right: terminal */}
        <div style={{ border: '1px solid #111', overflow: 'hidden' }}>
          <div style={{
            background:   '#0a0a0a',
            borderBottom: '1px solid #111',
            padding:      '0.75rem 1rem',
            display:      'flex',
            alignItems:   'center',
            gap:          '0.5rem',
          }}>
            {[0,1,2].map(i => (
              <div key={i} style={{ width: 9, height: 9, borderRadius: '50%', background: '#1a1a1a' }} />
            ))}
          </div>

          <div style={{ background: '#050505', padding: '2rem 1.75rem', fontFamily: 'var(--font-jetbrains)', fontSize: '0.8rem', lineHeight: 2 }}>
            <div>
              <span style={{ color: '#333' }}>$ </span>
              <span style={{ color: '#888' }}>pip install cosmos-ai</span>
            </div>
            <div style={{ color: '#222', paddingLeft: '1rem' }}>
              Successfully installed cosmos-ai
            </div>
            <div style={{ marginTop: '0.25rem' }}>
              <span style={{ color: '#333' }}>$ </span>
              <span style={{ color: '#888' }}>cosmos</span>
            </div>
            <div style={{ color: '#2a2a2a', paddingLeft: '1rem' }}>
              ✓ Authenticated<br />
              ✓ Loading history...<br />
              <span style={{ color: '#444' }}>Welcome back.</span>
            </div>
          </div>
        </div>
      </section>

      {/* ──────────────────────── FOOTER ───────────────────────── */}
      <footer style={{
        borderTop:      '1px solid #0d0d0d',
        padding:        '3rem 8vw',
        display:        'flex',
        justifyContent: 'space-between',
        alignItems:     'center',
        flexWrap:       'wrap',
        gap:            '1rem',
      }}>
        <span className="font-gloock" style={{ fontSize: '1rem', color: '#1a1a1a', letterSpacing: '-0.01em' }}>
          Cosmos
        </span>
        <div style={{ display: 'flex', gap: '2rem' }}>
          <Link href="/login" className="font-crimson" style={{ fontSize: '0.9rem', fontStyle: 'italic', color: '#222', textDecoration: 'none' }}>
            Login
          </Link>
          <Link href="/signup" className="font-crimson" style={{ fontSize: '0.9rem', fontStyle: 'italic', color: '#222', textDecoration: 'none' }}>
            Sign up
          </Link>
          <a href="https://github.com/Sharann-del/Cosmos" target="_blank" rel="noopener noreferrer" className="font-crimson" style={{ fontSize: '0.9rem', fontStyle: 'italic', color: '#222', textDecoration: 'none' }}>
            GitHub
          </a>
        </div>
        <span className="font-crimson" style={{ fontSize: '0.9rem', fontStyle: 'italic', color: '#1a1a1a' }}>
          Built for the terminal.
        </span>
      </footer>

    </div>
  )
}
