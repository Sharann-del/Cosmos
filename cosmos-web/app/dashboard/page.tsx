import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
import Link from 'next/link'
import SignOutButton from './SignOutButton'

interface Chat {
  id: string
  title: string
  updated_at: string
}

interface Folder {
  id: string
  name: string
  parent_id: string | null
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  if (days < 30) return `${days}d ago`
  const months = Math.floor(days / 30)
  if (months < 12) return `${months}mo ago`
  return `${Math.floor(months / 12)}y ago`
}

export default async function DashboardPage() {
  const supabase = createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/login')

  const [{ data: chats }, { data: folders }] = await Promise.all([
    supabase.from('chats').select('id, title, updated_at').eq('user_id', user.id).order('updated_at', { ascending: false }).limit(50),
    supabase.from('folders').select('id, name, parent_id').eq('user_id', user.id).order('name', { ascending: true }),
  ])

  const chatList: Chat[] = chats ?? []
  const folderList: Folder[] = folders ?? []
  const displayName = user.user_metadata?.full_name || user.email?.split('@')[0] || 'there'

  return (
    <div style={{ minHeight: '100vh', background: '#0d0d0d', color: '#fff' }}>

      {/* nav */}
      <nav className="dash-nav" style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderBottom: '1px solid #161616',
      }}>
        <Link href="/" className="font-gloock" style={{
          fontSize: '1.5rem',
          color: '#fff',
          textDecoration: 'none',
          letterSpacing: '-0.02em',
        }}>
          Cosmos
        </Link>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
          <span className="font-crimson dash-email" style={{ fontSize: '0.9rem', color: '#2a2a2a' }}>
            {user.email}
          </span>
          <SignOutButton />
        </div>
      </nav>

      <main className="dash-main" style={{ maxWidth: '52rem', margin: '0 auto' }}>

        {/* greeting */}
        <div style={{ marginBottom: '8vh' }}>
          <h1 className="font-gloock" style={{
            fontSize: 'clamp(2.8rem, 6vw, 5rem)',
            fontWeight: 400,
            color: '#fff',
            margin: '0 0 0.6rem',
            letterSpacing: '-0.03em',
            lineHeight: 1,
          }}>
            Hello, {displayName}.
          </h1>
          <p className="font-crimson" style={{
            fontSize: 'clamp(1.1rem, 2vw, 1.3rem)',
            color: '#333',
            margin: 0,
          }}>
            {chatList.length === 0
              ? 'No conversations yet. Open Cosmos in your terminal to start.'
              : `${chatList.length} ${chatList.length === 1 ? 'conversation' : 'conversations'} synced.`}
          </p>
        </div>

        {/* chats */}
        {chatList.length > 0 && (
          <section style={{ marginBottom: '8vh' }}>
            <p className="font-crimson" style={{
              fontSize: '0.8rem',
              color: '#2a2a2a',
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              margin: '0 0 1.25rem',
            }}>
              Recent chats
            </p>

            <div style={{ borderTop: '1px solid #161616' }}>
              {chatList.map((chat) => (
                <div
                  key={chat.id}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '1fr auto',
                    alignItems: 'baseline',
                    gap: '2rem',
                    padding: '1.25rem 0',
                    borderBottom: '1px solid #161616',
                  }}
                >
                  <span className="font-crimson" style={{
                    fontSize: 'clamp(1.1rem, 2vw, 1.35rem)',
                    color: '#bbb',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    lineHeight: 1.3,
                  }}>
                    {chat.title || 'Untitled chat'}
                  </span>
                  <span className="font-crimson" style={{
                    fontSize: '0.9rem',
                    color: '#2a2a2a',
                    whiteSpace: 'nowrap',
                  }}>
                    {timeAgo(chat.updated_at)}
                  </span>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* folders */}
        {folderList.length > 0 && (
          <section>
            <p className="font-crimson" style={{
              fontSize: '0.8rem',
              color: '#2a2a2a',
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              margin: '0 0 1.25rem',
            }}>
              Folders
            </p>

            <div style={{ borderTop: '1px solid #161616' }}>
              {folderList.map((folder) => (
                <div
                  key={folder.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '1rem',
                    padding: '1.25rem 0',
                    borderBottom: '1px solid #161616',
                  }}
                >
                  <span style={{ fontSize: '0.75rem', color: '#222' }}>
                    {folder.parent_id ? '↳' : '▸'}
                  </span>
                  <span className="font-crimson" style={{
                    fontSize: 'clamp(1.1rem, 2vw, 1.35rem)',
                    color: '#bbb',
                  }}>
                    {folder.name}
                  </span>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* empty state */}
        {chatList.length === 0 && (
          <div style={{ borderTop: '1px solid #161616', paddingTop: '3rem' }}>
            <p className="font-crimson" style={{ fontSize: '1rem', color: '#1e1e1e', margin: 0 }}>
              pip install cosmos-ai · cosmos
            </p>
          </div>
        )}

      </main>
    </div>
  )
}
