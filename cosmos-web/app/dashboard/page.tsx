import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
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
    supabase
      .from('chats')
      .select('id, title, updated_at')
      .eq('user_id', user.id)
      .order('updated_at', { ascending: false })
      .limit(50),
    supabase
      .from('folders')
      .select('id, name, parent_id')
      .eq('user_id', user.id)
      .order('name', { ascending: true }),
  ])

  const chatList: Chat[] = chats ?? []
  const folderList: Folder[] = folders ?? []

  return (
    <div className="min-h-screen bg-black text-white font-mono flex flex-col">
      {/* Nav */}
      <nav className="border-b border-[#1a1a1a] px-6 py-3 flex items-center justify-between">
        <span className="text-xs text-[#505050] tracking-widest uppercase">
          cosmos
        </span>
        <div className="flex items-center gap-4">
          <span className="text-xs text-[#505050] hidden sm:block">
            {user.email}
          </span>
          <SignOutButton />
        </div>
      </nav>

      <main className="flex-1 px-6 py-8 max-w-4xl w-full mx-auto space-y-10">

        {/* Chats */}
        <section>
          <div className="mb-4">
            <h1 className="text-sm text-white mb-1">Chats</h1>
            <p className="text-xs text-[#505050]">
              {chatList.length} {chatList.length === 1 ? 'conversation' : 'conversations'}
            </p>
          </div>

          {chatList.length === 0 ? (
            <div className="border border-[#1a1a1a] p-8 text-center">
              <p className="text-xs text-[#505050] mb-1">No chats yet.</p>
              <p className="text-xs text-[#2a2a2a]">
                Open the Cosmos terminal app to start chatting.
              </p>
            </div>
          ) : (
            <div className="border border-[#1a1a1a]">
              <div className="grid grid-cols-[1fr_auto] border-b border-[#1a1a1a] px-4 py-2">
                <span className="text-xs text-[#505050] uppercase tracking-widest">Title</span>
                <span className="text-xs text-[#505050] uppercase tracking-widest">Updated</span>
              </div>
              {chatList.map((chat, i) => (
                <div
                  key={chat.id}
                  className={`grid grid-cols-[1fr_auto] px-4 py-3 items-center gap-4 hover:bg-[#0a0a0a] transition-colors ${
                    i < chatList.length - 1 ? 'border-b border-[#1a1a1a]' : ''
                  }`}
                >
                  <span className="text-xs text-[#c8c8c8] truncate">
                    {chat.title || 'Untitled chat'}
                  </span>
                  <span className="text-xs text-[#505050] whitespace-nowrap">
                    {timeAgo(chat.updated_at)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Folders */}
        <section>
          <div className="mb-4">
            <h2 className="text-sm text-white mb-1">Folders</h2>
            <p className="text-xs text-[#505050]">
              {folderList.length} {folderList.length === 1 ? 'folder' : 'folders'}
            </p>
          </div>

          {folderList.length === 0 ? (
            <div className="border border-[#1a1a1a] p-8 text-center">
              <p className="text-xs text-[#505050]">No folders yet.</p>
            </div>
          ) : (
            <div className="border border-[#1a1a1a]">
              {folderList.map((folder, i) => (
                <div
                  key={folder.id}
                  className={`flex items-center gap-2 px-4 py-3 hover:bg-[#0a0a0a] transition-colors ${
                    i < folderList.length - 1 ? 'border-b border-[#1a1a1a]' : ''
                  }`}
                >
                  <span className="text-xs text-[#505050]">
                    {folder.parent_id ? '  ▸' : '▸'}
                  </span>
                  <span className="text-xs text-[#c8c8c8]">{folder.name}</span>
                </div>
              ))}
            </div>
          )}
        </section>

      </main>
    </div>
  )
}
