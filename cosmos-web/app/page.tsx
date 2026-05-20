import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
import Landing from './_components/Landing'

export default async function HomePage() {
  const supabase = createClient()
  const { data: { user } } = await supabase.auth.getUser()

  if (user) {
    redirect('/dashboard')
  }

  return <Landing />
}
