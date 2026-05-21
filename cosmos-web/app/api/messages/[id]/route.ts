import { NextRequest, NextResponse } from "next/server";
import { getAuthUser } from "@/lib/api-auth";

// GET /api/messages/[chat_id] — returns all messages for the chat
export async function GET(req: NextRequest, { params }: { params: { id: string } }) {
  const auth = await getAuthUser(req);
  if (!auth) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { data, error } = await auth.supabase
    .from("messages")
    .select("role, content")
    .eq("chat_id", params.id)
    .order("created_at", { ascending: true });

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json(data ?? []);
}
