import { createClient } from "@supabase/supabase-js";
import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  const { email, password } = await req.json();
  if (!email || !password) {
    return NextResponse.json({ error: "Missing credentials" }, { status: 400 });
  }

  const supabase = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );

  const { data, error } = await supabase.auth.signInWithPassword({ email, password });
  if (error || !data.session) {
    return NextResponse.json({ error: error?.message ?? "Login failed" }, { status: 401 });
  }

  const token = data.session.access_token;
  const userId = data.user.id;

  const authed = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    { global: { headers: { Authorization: `Bearer ${token}` } } }
  );

  const { data: settings } = await authed
    .from("user_settings")
    .select("openrouter_api_key")
    .eq("user_id", userId)
    .single();

  const fullName = (data.user.user_metadata?.full_name as string | undefined) || "";

  return NextResponse.json({
    token,
    user: {
      id: userId,
      email: data.user.email,
      full_name: fullName,
      openrouter_api_key: settings?.openrouter_api_key ?? "",
    },
  });
}
