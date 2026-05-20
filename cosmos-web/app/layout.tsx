import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Cosmos — Terminal AI Chat",
  description: "A terminal AI chat interface with 25+ free models, streaming responses, and chat history.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="bg-black text-white font-mono antialiased">
        {children}
      </body>
    </html>
  );
}
