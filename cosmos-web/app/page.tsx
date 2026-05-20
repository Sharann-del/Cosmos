import Link from "next/link";

const ASCII_ART = ` ██████╗ ██████╗ ███████╗███╗   ███╗ ██████╗ ███████╗
██╔════╝██╔═══██╗██╔════╝████╗ ████║██╔═══██╗██╔════╝
██║     ██║   ██║███████╗██╔████╔██║██║   ██║███████╗
██║     ██║   ██║╚════██║██║╚██╔╝██║██║   ██║╚════██║
╚██████╗╚██████╔╝███████║██║ ╚═╝ ██║╚██████╔╝███████║
 ╚═════╝ ╚═════╝ ╚══════╝╚═╝     ╚═╝ ╚═════╝ ╚══════╝`;

const features = [
  {
    title: "25+ Free Models",
    description:
      "Access over 25 free AI models via OpenRouter. Switch between GPT-4o, Claude, Gemini, and more without spending a cent.",
  },
  {
    title: "Streaming Responses",
    description:
      "Real-time token streaming so you see output as it generates. No waiting for full responses to load.",
  },
  {
    title: "Chat History",
    description:
      "Every conversation is persisted to Supabase. Pick up where you left off across sessions and devices.",
  },
  {
    title: "Multiline Input",
    description:
      "Full multiline editing with keyboard shortcuts. Compose long prompts without fighting a single-line input.",
  },
];

export default function HomePage() {
  return (
    <div className="min-h-screen bg-black text-white font-mono flex flex-col">
      {/* Nav */}
      <nav className="border-b border-[#1a1a1a] px-6 py-3 flex items-center justify-between">
        <span className="text-sm text-[#505050] tracking-widest uppercase">
          cosmos
        </span>
        <div className="flex items-center gap-4">
          <Link
            href="/login"
            className="text-sm text-[#c8c8c8] hover:text-white transition-colors"
          >
            Login
          </Link>
          <Link
            href="/signup"
            className="text-sm border border-[#2a2a2a] px-3 py-1 text-[#c8c8c8] hover:border-[#505050] hover:text-white transition-colors"
          >
            Sign up
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="flex-1 flex flex-col items-center justify-center px-6 py-24 border-b border-[#1a1a1a]">
        <pre className="text-white text-xs sm:text-sm leading-tight mb-8 overflow-x-auto max-w-full">
          {ASCII_ART}
        </pre>
        <p className="text-[#505050] text-sm mb-10 tracking-wide">
          A terminal AI chat interface
        </p>
        <div className="flex items-center gap-4">
          <Link
            href="/signup"
            className="border border-[#2a2a2a] px-5 py-2 text-sm text-white hover:border-[#505050] hover:bg-[#0a0a0a] transition-colors"
          >
            Get Started →
          </Link>
          <a
            href="https://github.com"
            target="_blank"
            rel="noopener noreferrer"
            className="border border-[#1a1a1a] px-5 py-2 text-sm text-[#505050] hover:text-[#c8c8c8] hover:border-[#2a2a2a] transition-colors"
          >
            Download
          </a>
        </div>
      </section>

      {/* Features */}
      <section className="px-6 py-16 border-b border-[#1a1a1a]">
        <div className="max-w-4xl mx-auto">
          <p className="text-xs text-[#505050] uppercase tracking-widest mb-8">
            Features
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-px bg-[#1a1a1a]">
            {features.map((feature) => (
              <div key={feature.title} className="bg-black p-6">
                <h3 className="text-sm text-white mb-2">{feature.title}</h3>
                <p className="text-xs text-[#505050] leading-relaxed">
                  {feature.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section className="px-6 py-16 border-b border-[#1a1a1a]">
        <div className="max-w-4xl mx-auto">
          <p className="text-xs text-[#505050] uppercase tracking-widest mb-8">
            Pricing
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-px bg-[#1a1a1a]">
            {/* Free */}
            <div className="bg-black p-6">
              <div className="flex items-baseline gap-2 mb-4">
                <span className="text-white text-lg">Free</span>
                <span className="text-[#505050] text-xs">forever</span>
              </div>
              <ul className="space-y-2 mb-6">
                <li className="text-xs text-[#c8c8c8] flex items-start gap-2">
                  <span className="text-[#505050] mt-px">—</span>
                  Free OpenRouter models
                </li>
                <li className="text-xs text-[#c8c8c8] flex items-start gap-2">
                  <span className="text-[#505050] mt-px">—</span>
                  Unlimited chats
                </li>
                <li className="text-xs text-[#c8c8c8] flex items-start gap-2">
                  <span className="text-[#505050] mt-px">—</span>
                  Chat history
                </li>
              </ul>
              <Link
                href="/signup"
                className="inline-block border border-[#2a2a2a] px-4 py-2 text-xs text-white hover:border-[#505050] transition-colors"
              >
                Get started
              </Link>
            </div>

            {/* Pro */}
            <div className="bg-black p-6 opacity-40">
              <div className="flex items-baseline gap-2 mb-4">
                <span className="text-white text-lg">Pro</span>
                <span className="text-[#505050] text-xs">$9/mo</span>
              </div>
              <ul className="space-y-2 mb-6">
                <li className="text-xs text-[#c8c8c8] flex items-start gap-2">
                  <span className="text-[#505050] mt-px">—</span>
                  Everything in Free
                </li>
                <li className="text-xs text-[#c8c8c8] flex items-start gap-2">
                  <span className="text-[#505050] mt-px">—</span>
                  Priority model access
                </li>
                <li className="text-xs text-[#c8c8c8] flex items-start gap-2">
                  <span className="text-[#505050] mt-px">—</span>
                  Extended context
                </li>
              </ul>
              <span className="inline-block border border-[#1a1a1a] px-4 py-2 text-xs text-[#505050] cursor-not-allowed">
                Coming soon
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="px-6 py-4 flex items-center justify-between">
        <span className="text-xs text-[#2a2a2a] tracking-widest uppercase">
          COSMOS
        </span>
        <span className="text-xs text-[#2a2a2a]">
          Built with Next.js + Supabase
        </span>
      </footer>
    </div>
  );
}
