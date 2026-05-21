"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";

export default function SignupPage() {
  const [fullName, setFullName] = useState("");
  useEffect(() => { document.documentElement.style.background = '#111'; return () => { document.documentElement.style.background = '' } }, []);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [verified, setVerified] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const supabase = createClient();
      const { error: signUpError } = await supabase.auth.signUp({
        email,
        password,
        options: { data: { full_name: fullName.trim(), openrouter_api_key: apiKey.trim() } },
      });
      if (signUpError) { setError(signUpError.message); return; }
      setVerified(true);
    } catch {
      setError("An unexpected error occurred.");
    } finally {
      setLoading(false);
    }
  }

  const panel = (
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
        <h1 className="font-crimson" style={{ fontSize: "1.9rem", fontWeight: 400, color: "#e8e8e8", margin: "0 0 0.3rem", letterSpacing: "-0.01em" }}>
          Check your email.
        </h1>
        <p className="font-crimson" style={{ fontSize: "1.05rem", color: "#444", margin: "0 0 2.5rem", lineHeight: 1.7 }}>
          We sent a link to <span style={{ color: "#777" }}>{email}</span>. Click it to activate your account.
        </p>
        <Link href="/login" className="font-crimson" style={{ fontSize: "0.95rem", color: "#555", textDecoration: "none", borderBottom: "1px solid #2a2a2a" }}>
          Back to log in
        </Link>
      </div>
    </div>
  );

  if (verified) return panel;

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

        <h1 className="font-crimson" style={{ fontSize: "1.9rem", fontWeight: 400, color: "#e8e8e8", margin: "0 0 0.3rem", letterSpacing: "-0.01em" }}>
          Create an account.
        </h1>
        <p className="font-crimson" style={{ fontSize: "1.05rem", color: "#444", margin: "0 0 2.5rem" }}>
          Free forever. No credit card.
        </p>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1.4rem" }}>
          {[
            { id: "fullName", label: "Full name", type: "text", value: fullName, set: setFullName, placeholder: "Jane Smith", auto: "name" },
            { id: "email",    label: "Email",     type: "email", value: email, set: setEmail, placeholder: "you@example.com", auto: "email" },
            { id: "password", label: "Password",  type: "password", value: password, set: setPassword, placeholder: "••••••••", auto: "new-password" },
          ].map(f => (
            <div key={f.id}>
              <label className="font-crimson" htmlFor={f.id} style={{ display: "block", fontSize: "0.9rem", color: "#555", marginBottom: "0.45rem" }}>
                {f.label}
              </label>
              <input
                id={f.id} type={f.type} value={f.value} required
                autoComplete={f.auto} placeholder={f.placeholder}
                onChange={e => f.set(e.target.value)}
                style={{ width: "100%", background: "#1a1a1a", border: "1px solid #222", padding: "0.8rem 1rem", color: "#fff", fontSize: "1rem", fontFamily: "var(--font-crimson)", outline: "none", boxSizing: "border-box", borderRadius: "2px" }}
                onFocus={e => { e.currentTarget.style.borderColor = "#444" }}
                onBlur={e => { e.currentTarget.style.borderColor = "#222" }}
              />
            </div>
          ))}

          <div>
            <label className="font-crimson" htmlFor="apiKey" style={{ display: "block", fontSize: "0.9rem", color: "#555", marginBottom: "0.45rem" }}>
              OpenRouter API key
            </label>
            <input
              id="apiKey" type="password" value={apiKey} required
              autoComplete="off" placeholder="sk-or-..."
              onChange={e => setApiKey(e.target.value)}
              style={{ width: "100%", background: "#1a1a1a", border: "1px solid #222", padding: "0.8rem 1rem", color: "#fff", fontSize: "1rem", fontFamily: "var(--font-crimson)", outline: "none", boxSizing: "border-box", borderRadius: "2px" }}
              onFocus={e => { e.currentTarget.style.borderColor = "#444" }}
              onBlur={e => { e.currentTarget.style.borderColor = "#222" }}
            />
            <p className="font-crimson" style={{ fontSize: "0.82rem", color: "#333", margin: "0.4rem 0 0" }}>
              Get your free key at openrouter.ai/keys
            </p>
          </div>

          {error && (
            <p className="font-crimson" style={{ fontSize: "0.95rem", color: "#884444", margin: 0 }}>{error}</p>
          )}

          <button
            type="submit" disabled={loading} className="font-crimson"
            style={{ width: "100%", background: "#fff", border: "none", padding: "0.85rem", color: "#000", fontSize: "1rem", fontWeight: 600, cursor: loading ? "not-allowed" : "pointer", opacity: loading ? 0.5 : 1, borderRadius: "2px", transition: "opacity 0.2s", marginTop: "0.25rem" }}
          >
            {loading ? "Creating account…" : "Create account →"}
          </button>
        </form>

        <p className="font-crimson" style={{ fontSize: "0.95rem", color: "#3a3a3a", marginTop: "2rem" }}>
          Already have an account?{" "}
          <Link href="/login" style={{ color: "#777", textDecoration: "none", borderBottom: "1px solid #333" }}>
            Log in
          </Link>
        </p>
      </div>
    </div>
  );
}
