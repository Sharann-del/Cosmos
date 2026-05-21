"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

export default function OnboardingPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const supabase = createClient();
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) { router.push("/login"); return; }

      const { error: updateError } = await supabase.auth.updateUser({
        data: { full_name: fullName.trim() },
      });
      if (updateError) { setError(updateError.message); return; }

      const { error: upsertError } = await supabase
        .from("user_settings")
        .upsert({
          user_id: user.id,
          full_name: fullName.trim(),
          openrouter_api_key: apiKey.trim(),
        });
      if (upsertError) { setError(upsertError.message); return; }

      router.push("/dashboard");
    } catch {
      setError("An unexpected error occurred. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ minHeight: "100vh", background: "#000", color: "#fff", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "2rem" }}>

      <Link href="/" className="font-gloock" style={{ fontSize: "clamp(2rem, 6vw, 3.5rem)", color: "#fff", textDecoration: "none", letterSpacing: "-0.02em", marginBottom: "3.5rem", display: "block" }}>
        Cosmos
      </Link>

      <div style={{ width: "100%", maxWidth: "22rem" }}>
        <h1 className="font-crimson" style={{ fontSize: "1.6rem", fontWeight: 400, color: "#fff", margin: "0 0 0.4rem" }}>
          Set up your account.
        </h1>
        <p className="font-crimson" style={{ fontSize: "1rem", color: "#333", margin: "0 0 2.5rem" }}>
          Just two things to get started.
        </p>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
          <div>
            <label className="font-crimson" style={{ display: "block", fontSize: "0.9rem", color: "#444", marginBottom: "0.4rem" }} htmlFor="fullName">
              Your name
            </label>
            <input
              id="fullName"
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
              autoComplete="name"
              placeholder="Jane Smith"
              style={{ width: "100%", background: "#080808", border: "1px solid #111", padding: "0.65rem 0.85rem", color: "#fff", fontSize: "1rem", fontFamily: "var(--font-crimson)", outline: "none", boxSizing: "border-box" }}
              onFocus={e => { e.currentTarget.style.borderColor = "#333" }}
              onBlur={e => { e.currentTarget.style.borderColor = "#111" }}
            />
          </div>

          <div>
            <label className="font-crimson" style={{ display: "block", fontSize: "0.9rem", color: "#444", marginBottom: "0.4rem" }} htmlFor="apiKey">
              OpenRouter API key
            </label>
            <input
              id="apiKey"
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              required
              autoComplete="off"
              placeholder="sk-or-..."
              style={{ width: "100%", background: "#080808", border: "1px solid #111", padding: "0.65rem 0.85rem", color: "#fff", fontSize: "1rem", fontFamily: "var(--font-crimson)", outline: "none", boxSizing: "border-box" }}
              onFocus={e => { e.currentTarget.style.borderColor = "#333" }}
              onBlur={e => { e.currentTarget.style.borderColor = "#111" }}
            />
            <p className="font-crimson" style={{ fontSize: "0.82rem", color: "#2a2a2a", margin: "0.4rem 0 0" }}>
              Get one free at openrouter.ai
            </p>
          </div>

          {error && (
            <p className="font-crimson" style={{ fontSize: "0.9rem", color: "#666", margin: 0 }}>
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="font-crimson"
            style={{ width: "100%", background: "transparent", border: "1px solid #222", padding: "0.7rem", color: loading ? "#333" : "#fff", fontSize: "1rem", cursor: loading ? "not-allowed" : "pointer", transition: "border-color 0.2s, color 0.2s", marginTop: "0.25rem" }}
            onMouseEnter={e => { if (!loading) e.currentTarget.style.borderColor = "#555" }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = "#222" }}
          >
            {loading ? "Saving…" : "Continue →"}
          </button>
        </form>
      </div>
    </div>
  );
}
