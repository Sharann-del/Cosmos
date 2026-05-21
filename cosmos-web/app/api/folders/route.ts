import { NextRequest, NextResponse } from "next/server";
import { getAuthUser } from "@/lib/api-auth";

export async function GET(req: NextRequest) {
  const auth = await getAuthUser(req);
  if (!auth) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { data, error } = await auth.supabase
    .from("folders")
    .select("id, name, parent_id, created_at")
    .eq("user_id", auth.user.id)
    .order("name", { ascending: true });

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json(data ?? []);
}

export async function POST(req: NextRequest) {
  const auth = await getAuthUser(req);
  if (!auth) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { name, parent_id } = await req.json();
  if (!name) return NextResponse.json({ error: "Missing name" }, { status: 400 });

  const payload: Record<string, unknown> = {
    user_id: auth.user.id,
    name: String(name).slice(0, 40),
  };
  if (parent_id) payload.parent_id = parent_id;

  const { data, error } = await auth.supabase
    .from("folders")
    .insert(payload)
    .select()
    .single();

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json(data);
}
