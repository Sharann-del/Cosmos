import { NextRequest, NextResponse } from "next/server";
import { getAuthUser } from "@/lib/api-auth";

export async function POST(req: NextRequest) {
  const auth = await getAuthUser(req);
  if (!auth) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { chat_id, role, content } = await req.json();
  if (!chat_id || !role || !content) {
    return NextResponse.json({ error: "Missing fields" }, { status: 400 });
  }

  // Verify chat ownership
  const { data: chat } = await auth.supabase
    .from("chats")
    .select("id")
    .eq("id", chat_id)
    .eq("user_id", auth.user.id)
    .single();

  if (!chat) return NextResponse.json({ error: "Not found" }, { status: 404 });

  const { data, error } = await auth.supabase
    .from("messages")
    .insert({ chat_id, role, content })
    .select()
    .single();

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json(data);
}
