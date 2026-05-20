"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

export default function LoginPage() {
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
      const { error: signInError } = await supabase.auth.signInWithPassword({
        email,
        password,
      });

      if (signInError) {
        setError(signInError.message);
        return;
      }

      router.push("/dashboard");
      router.refresh();
    } catch {
      setError("An unexpected error occurred. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-black text-white font-mono flex flex-col">
      {/* Nav */}
      <nav className="border-b border-[#1a1a1a] px-6 py-3">
        <Link
          href="/"
          className="text-xs text-[#505050] tracking-widest uppercase hover:text-[#c8c8c8] transition-colors"
        >
          cosmos
        </Link>
      </nav>

      {/* Form */}
      <div className="flex-1 flex items-center justify-center px-6">
        <div className="w-full max-w-sm">
          <div className="border border-[#1a1a1a] p-8">
            <h1 className="text-sm text-white mb-1">Log in</h1>
            <p className="text-xs text-[#505050] mb-8">
              Welcome back to Cosmos.
            </p>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs text-[#505050] mb-1" htmlFor="email">
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoComplete="email"
                  className="w-full bg-[#0a0a0a] border border-[#1a1a1a] px-3 py-2 text-xs text-white placeholder-[#2a2a2a] focus:outline-none focus:border-[#505050] transition-colors"
                  placeholder="you@example.com"
                />
              </div>

              <div>
                <label className="block text-xs text-[#505050] mb-1" htmlFor="password">
                  Password
                </label>
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                  className="w-full bg-[#0a0a0a] border border-[#1a1a1a] px-3 py-2 text-xs text-white placeholder-[#2a2a2a] focus:outline-none focus:border-[#505050] transition-colors"
                  placeholder="••••••••"
                />
              </div>

              {error && (
                <p className="text-xs text-[#c8c8c8] border border-[#2a2a2a] bg-[#0a0a0a] px-3 py-2">
                  {error}
                </p>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full border border-[#2a2a2a] px-4 py-2 text-xs text-white hover:border-[#505050] hover:bg-[#0a0a0a] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {loading ? "Logging in..." : "Log in →"}
              </button>
            </form>

            <p className="text-xs text-[#505050] mt-6">
              Don&apos;t have an account?{" "}
              <Link
                href="/signup"
                className="text-[#c8c8c8] hover:text-white transition-colors"
              >
                Sign up
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
