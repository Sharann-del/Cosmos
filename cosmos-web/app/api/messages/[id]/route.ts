import { NextRequest, NextResponse } from "next/server";
import { getAuthUser } from "@/lib/api-auth";

// GET /api/messages/[chat_id] — returns all messages for the chat
export async function GET(req: NextRequest, { params }: { params: { id: string } }) {
  const auth = await getAuthUser(req);
  if (!auth) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  // Verify the chat belongs to this user
  const { data: chat } = await auth.supabase
    .from("chats")
    .select("id")
    .eq("id", params.id)
    .eq("user_id", auth.user.id)
    .single();

  if (!chat) return NextResponse.json({ error: "Not found" }, { status: 404 });

  const { data, error } = await auth.supabase
    .from("messages")
    .select("role, content")
    .eq("chat_id", params.id)
    .order("created_at", { ascending: true });

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json(data ?? []);
}
