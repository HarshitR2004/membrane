import type { Metadata } from "next";
import { Unbounded, IBM_Plex_Mono } from "next/font/google";
import { Providers } from "./providers";
import "./globals.css";

const unbounded = Unbounded({
  variable: "--font-unbounded",
  subsets: ["latin"],
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  weight: ["400", "500", "600", "700"],
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Membrane | Universal Memory for AI",
  description: "The universal memory layer for AI agents, built on Walrus and Sui.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${unbounded.variable} ${plexMono.variable} antialiased relative`}
      >
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  );
}
