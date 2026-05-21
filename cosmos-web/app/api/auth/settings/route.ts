import { NextRequest, NextResponse } from "next/server";
import { getAuthUser } from "@/lib/api-auth";

export async function PATCH(req: NextRequest) {
  const auth = await getAuthUser(req);
  if (!auth) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { openrouter_api_key } = await req.json();
  if (!openrouter_api_key) {
    return NextResponse.json({ error: "Nothing to update" }, { status: 400 });
  }

  const { error } = await auth.supabase.auth.updateUser({
    data: { openrouter_api_key },
  });

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  return NextResponse.json({ ok: true });
}
