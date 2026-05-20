import type { Metadata } from "next";
import { Gloock, Crimson_Pro, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const gloock = Gloock({
  weight: "400",
  subsets: ["latin"],
  variable: "--font-gloock",
  display: "swap",
});

const crimsonPro = Crimson_Pro({
  weight: ["400", "600"],
  subsets: ["latin"],
  variable: "--font-crimson",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  weight: ["400", "500"],
  subsets: ["latin"],
  variable: "--font-jetbrains",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Cosmos — Terminal AI Chat",
  description:
    "A terminal AI chat interface with 25+ free models, streaming responses, and chat history.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${gloock.variable} ${crimsonPro.variable} ${jetbrainsMono.variable}`}
    >
      <body className="bg-black text-white font-mono antialiased">{children}</body>
    </html>
  );
}
