import { NextRequest, NextResponse } from "next/server";
import { getAuthUser } from "@/lib/api-auth";

export async function GET(req: NextRequest) {
  const auth = await getAuthUser(req);
  if (!auth) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { data: settings } = await auth.supabase
    .from("user_settings")
    .select("openrouter_api_key")
    .eq("user_id", auth.user.id)
    .single();

  const fullName = (auth.user.user_metadata?.full_name as string | undefined) || "";

  return NextResponse.json({
    id: auth.user.id,
    email: auth.user.email,
    full_name: fullName,
    openrouter_api_key: settings?.openrouter_api_key ?? "",
  });
}
