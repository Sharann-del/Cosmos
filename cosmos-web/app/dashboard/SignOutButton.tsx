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
      className="font-crimson"
      style={{ background: "transparent", border: "none", padding: 0, color: "#333", fontSize: "1rem", cursor: "pointer", transition: "color 0.2s" }}
      onMouseEnter={e => { e.currentTarget.style.color = "#888" }}
      onMouseLeave={e => { e.currentTarget.style.color = "#333" }}
    >
      Sign out
    </button>
  );
}
