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

  return (
    <div style={{ minHeight: '100vh', background: '#000', color: '#fff' }}>

      {/* nav */}
      <nav style={{ padding: '1.75rem 3rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid #0d0d0d' }}>
        <Link href="/" className="font-gloock" style={{ fontSize: '1.3rem', color: '#fff', textDecoration: 'none', letterSpacing: '-0.02em' }}>
          Cosmos
        </Link>
        <div style={{ display: 'flex', alignItems: 'center', gap: '2rem' }}>
          <span className="font-crimson" style={{ fontSize: '0.95rem', color: '#2a2a2a' }}>
            {user.email}
          </span>
          <SignOutButton />
        </div>
      </nav>

      <main style={{ maxWidth: '56rem', margin: '0 auto', padding: '6vh 3rem 12vh' }}>

        {/* chats */}
        <section style={{ marginBottom: '6vh' }}>
          <div style={{ marginBottom: '1.5rem' }}>
            <h1 className="font-crimson" style={{ fontSize: 'clamp(1.8rem, 3vw, 2.4rem)', fontWeight: 400, color: '#fff', margin: '0 0 0.3rem', letterSpacing: '-0.01em' }}>
              Chats
            </h1>
            <p className="font-crimson" style={{ fontSize: '1rem', color: '#333', margin: 0 }}>
              {chatList.length} {chatList.length === 1 ? 'conversation' : 'conversations'}
            </p>
          </div>

          {chatList.length === 0 ? (
            <div style={{ padding: '3rem 0', borderTop: '1px solid #0d0d0d', borderBottom: '1px solid #0d0d0d' }}>
              <p className="font-crimson" style={{ fontSize: '1rem', color: '#2a2a2a', margin: 0 }}>
                No chats yet. Open Cosmos in your terminal to get started.
              </p>
            </div>
          ) : (
            <div style={{ borderTop: '1px solid #0d0d0d' }}>
              {chatList.map((chat) => (
                <div
                  key={chat.id}
                  style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '2rem', alignItems: 'center', padding: '1rem 0', borderBottom: '1px solid #0d0d0d' }}
                >
                  <span className="font-crimson" style={{ fontSize: '1.05rem', color: '#ccc', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {chat.title || 'Untitled chat'}
                  </span>
                  <span className="font-crimson" style={{ fontSize: '0.9rem', color: '#2a2a2a', whiteSpace: 'nowrap' }}>
                    {timeAgo(chat.updated_at)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* folders */}
        {folderList.length > 0 && (
          <section>
            <div style={{ marginBottom: '1.5rem' }}>
              <h2 className="font-crimson" style={{ fontSize: 'clamp(1.8rem, 3vw, 2.4rem)', fontWeight: 400, color: '#fff', margin: '0 0 0.3rem', letterSpacing: '-0.01em' }}>
                Folders
              </h2>
              <p className="font-crimson" style={{ fontSize: '1rem', color: '#333', margin: 0 }}>
                {folderList.length} {folderList.length === 1 ? 'folder' : 'folders'}
              </p>
            </div>

            <div style={{ borderTop: '1px solid #0d0d0d' }}>
              {folderList.map((folder) => (
                <div
                  key={folder.id}
                  style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '1rem 0', borderBottom: '1px solid #0d0d0d' }}
                >
                  <span className="font-crimson" style={{ fontSize: '0.8rem', color: '#222' }}>
                    {folder.parent_id ? '↳' : '▸'}
                  </span>
                  <span className="font-crimson" style={{ fontSize: '1.05rem', color: '#ccc' }}>
                    {folder.name}
                  </span>
                </div>
              ))}
            </div>
          </section>
        )}

      </main>
    </div>
  )
}
