"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

export default function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const supabase = createClient();
      const { error: signUpError } = await supabase.auth.signUp({ email, password });
      if (signUpError) { setError(signUpError.message); return; }
      router.push("/dashboard");
      router.refresh();
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
          Create an account.
        </h1>
        <p className="font-crimson" style={{ fontSize: "1rem", color: "#333", margin: "0 0 2.5rem" }}>
          Free forever. No credit card.
        </p>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
          <div>
            <label className="font-crimson" style={{ display: "block", fontSize: "0.9rem", color: "#444", marginBottom: "0.4rem" }} htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              placeholder="you@example.com"
              style={{ width: "100%", background: "#080808", border: "1px solid #111", padding: "0.65rem 0.85rem", color: "#fff", fontSize: "1rem", fontFamily: "var(--font-crimson)", outline: "none", boxSizing: "border-box" }}
              onFocus={e => { e.currentTarget.style.borderColor = "#333" }}
              onBlur={e => { e.currentTarget.style.borderColor = "#111" }}
            />
          </div>

          <div>
            <label className="font-crimson" style={{ display: "block", fontSize: "0.9rem", color: "#444", marginBottom: "0.4rem" }} htmlFor="password">
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="new-password"
              placeholder="••••••••"
              style={{ width: "100%", background: "#080808", border: "1px solid #111", padding: "0.65rem 0.85rem", color: "#fff", fontSize: "1rem", fontFamily: "var(--font-crimson)", outline: "none", boxSizing: "border-box" }}
              onFocus={e => { e.currentTarget.style.borderColor = "#333" }}
              onBlur={e => { e.currentTarget.style.borderColor = "#111" }}
            />
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
            {loading ? "Creating account…" : "Create account →"}
          </button>
        </form>

        <p className="font-crimson" style={{ fontSize: "0.95rem", color: "#333", marginTop: "2rem" }}>
          Already have an account?{" "}
          <Link href="/login" style={{ color: "#888", textDecoration: "none", borderBottom: "1px solid #222" }}>
            Log in
          </Link>
        </p>
      </div>
    </div>
  );
}
