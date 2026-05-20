"use client";

import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

export default function SignOutButton() {
  const router = useRouter();

  async function handleSignOut() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/");
    router.refresh();
  }

  return (
    <button
      onClick={handleSignOut}
      className="text-xs border border-[#1a1a1a] px-3 py-1 text-[#505050] hover:border-[#2a2a2a] hover:text-[#c8c8c8] transition-colors"
    >
      Sign out
    </button>
  );
}
