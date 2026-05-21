import { NextRequest, NextResponse } from "next/server";
import { getAuthUser } from "@/lib/api-auth";

export async function GET(req: NextRequest) {
  const auth = await getAuthUser(req);
  if (!auth) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const meta = auth.user.user_metadata ?? {};
  const fullName = (meta.full_name as string | undefined) || "";
  const orKey = (meta.openrouter_api_key as string | undefined) || "";

  return NextResponse.json({
    id: auth.user.id,
    email: auth.user.email,
    full_name: fullName,
    openrouter_api_key: orKey,
  });
}
