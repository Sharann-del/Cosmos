"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  useEffect(() => { document.documentElement.style.background = '#111'; return () => { document.documentElement.style.background = '' } }, []);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const supabase = createClient();
      const { error: signInError } = await supabase.auth.signInWithPassword({ email, password });
      if (signInError) { setError(signInError.message); return; }
      router.push("/dashboard");
      router.refresh();
    } catch {
      setError("An unexpected error occurred.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{
      minHeight: "100vh",
      width: "100%",
      background: "#111",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: "2rem",
    }}>
      <div style={{ width: "100%", maxWidth: "26rem" }}>

        <h1 className="font-crimson" style={{
          fontSize: "1.9rem",
          fontWeight: 400,
          color: "#e8e8e8",
          margin: "0 0 0.3rem",
          letterSpacing: "-0.01em",
        }}>
          Welcome back.
        </h1>
        <p className="font-crimson" style={{ fontSize: "1.05rem", color: "#444", margin: "0 0 2.5rem" }}>
          Sign in to continue.
        </p>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1.4rem" }}>
          <div>
            <label className="font-crimson" htmlFor="email" style={{ display: "block", fontSize: "0.9rem", color: "#555", marginBottom: "0.45rem" }}>
              Email
            </label>
            <input
              id="email" type="email" value={email} required autoComplete="email"
              placeholder="you@example.com"
              onChange={e => setEmail(e.target.value)}
              style={{ width: "100%", background: "#1a1a1a", border: "1px solid #222", padding: "0.8rem 1rem", color: "#fff", fontSize: "1rem", fontFamily: "var(--font-crimson)", outline: "none", boxSizing: "border-box", borderRadius: "2px" }}
              onFocus={e => { e.currentTarget.style.borderColor = "#444" }}
              onBlur={e => { e.currentTarget.style.borderColor = "#222" }}
            />
          </div>

          <div>
            <label className="font-crimson" htmlFor="password" style={{ display: "block", fontSize: "0.9rem", color: "#555", marginBottom: "0.45rem" }}>
              Password
            </label>
            <input
              id="password" type="password" value={password} required autoComplete="current-password"
              placeholder="••••••••"
              onChange={e => setPassword(e.target.value)}
              style={{ width: "100%", background: "#1a1a1a", border: "1px solid #222", padding: "0.8rem 1rem", color: "#fff", fontSize: "1rem", fontFamily: "var(--font-crimson)", outline: "none", boxSizing: "border-box", borderRadius: "2px" }}
              onFocus={e => { e.currentTarget.style.borderColor = "#444" }}
              onBlur={e => { e.currentTarget.style.borderColor = "#222" }}
            />
          </div>

          {error && (
            <p className="font-crimson" style={{ fontSize: "0.95rem", color: "#884444", margin: 0 }}>{error}</p>
          )}

          <button
            type="submit" disabled={loading} className="font-crimson"
            style={{ width: "100%", background: "#fff", border: "none", padding: "0.85rem", color: "#000", fontSize: "1rem", fontWeight: 600, cursor: loading ? "not-allowed" : "pointer", opacity: loading ? 0.5 : 1, borderRadius: "2px", transition: "opacity 0.2s", marginTop: "0.25rem" }}
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <p className="font-crimson" style={{ fontSize: "0.95rem", color: "#3a3a3a", marginTop: "2rem" }}>
          No account?{" "}
          <Link href="/signup" style={{ color: "#777", textDecoration: "none", borderBottom: "1px solid #333" }}>
            Sign up
          </Link>
        </p>
      </div>
    </div>
  );
}
