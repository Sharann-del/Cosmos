import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import SignOutButton from "./SignOutButton";

interface Chat {
  id: string;
  title: string;
  created_at: string;
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export default async function DashboardPage() {
  const supabase = createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  const { data: chats } = await supabase
    .from("chats")
    .select("id, title, created_at")
    .eq("user_id", user.id)
    .order("created_at", { ascending: false });

  const chatList: Chat[] = chats ?? [];

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

      {/* Content */}
      <main className="flex-1 px-6 py-8 max-w-4xl w-full mx-auto">
        <div className="mb-8">
          <h1 className="text-sm text-white mb-1">Chat history</h1>
          <p className="text-xs text-[#505050]">
            {chatList.length} {chatList.length === 1 ? "conversation" : "conversations"}
          </p>
        </div>

        {chatList.length === 0 ? (
          <div className="border border-[#1a1a1a] p-8 text-center">
            <p className="text-xs text-[#505050] mb-1">No chats yet.</p>
            <p className="text-xs text-[#2a2a2a]">
              Download the app to get started.
            </p>
          </div>
        ) : (
          <div className="border border-[#1a1a1a]">
            {/* Table header */}
            <div className="grid grid-cols-[1fr_auto] border-b border-[#1a1a1a] px-4 py-2">
              <span className="text-xs text-[#505050] uppercase tracking-widest">
                Title
              </span>
              <span className="text-xs text-[#505050] uppercase tracking-widest">
                Date
              </span>
            </div>

            {/* Rows */}
            {chatList.map((chat, i) => (
              <div
                key={chat.id}
                className={`grid grid-cols-[1fr_auto] px-4 py-3 items-center gap-4 hover:bg-[#0a0a0a] transition-colors ${
                  i < chatList.length - 1 ? "border-b border-[#1a1a1a]" : ""
                }`}
              >
                <span className="text-xs text-[#c8c8c8] truncate">
                  {chat.title || "Untitled chat"}
                </span>
                <span className="text-xs text-[#505050] whitespace-nowrap">
                  {formatDate(chat.created_at)}
                </span>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
