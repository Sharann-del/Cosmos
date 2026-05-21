import { createClient } from "@supabase/supabase-js";
import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  const { email, password, full_name, openrouter_api_key } = await req.json();
  if (!email || !password || !full_name || !openrouter_api_key) {
    return NextResponse.json({ error: "All fields are required" }, { status: 400 });
  }

  const anonClient = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );

  const { data, error: signUpError } = await anonClient.auth.signUp({
    email,
    password,
    options: { data: { full_name: full_name.trim() } },
  });

  if (signUpError || !data.user) {
    return NextResponse.json({ error: signUpError?.message ?? "Signup failed" }, { status: 400 });
  }

  // Use service role to bypass RLS — user isn't confirmed yet so auth.uid() won't match
  const adminClient = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!
  );

  const { error: insertError } = await adminClient
    .from("user_settings")
    .insert({
      user_id: data.user.id,
      openrouter_api_key: openrouter_api_key.trim(),
    });

  if (insertError) {
    return NextResponse.json({ error: insertError.message }, { status: 500 });
  }

  return NextResponse.json({ ok: true });
}
