import { NextRequest, NextResponse } from "next/server";
import { getAuthUser } from "@/lib/api-auth";

export async function PATCH(req: NextRequest) {
  const auth = await getAuthUser(req);
  if (!auth) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const body = await req.json();
  const { openrouter_api_key, full_name } = body;

  const updates: Record<string, string> = {};
  if (openrouter_api_key !== undefined) updates.openrouter_api_key = openrouter_api_key;
  if (full_name !== undefined) updates.full_name = full_name;

  if (Object.keys(updates).length === 0) {
    return NextResponse.json({ error: "Nothing to update" }, { status: 400 });
  }

  const { error } = await auth.supabase
    .from("user_settings")
    .upsert({ user_id: auth.user.id, ...updates }, { onConflict: "user_id" });

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  return NextResponse.json({ ok: true });
}
