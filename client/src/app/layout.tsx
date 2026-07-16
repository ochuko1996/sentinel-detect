import type { Metadata } from "next";
import { Big_Shoulders_Display, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";
import { ClassificationBar } from "@/components/layout/ClassificationBar";

const displayFont = Big_Shoulders_Display({
  subsets: ["latin"],
  weight: ["500", "600", "700", "800", "900"],
  variable: "--font-display",
});

const monoFont = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: "SENTINEL // Detect Console",
  description: "Operations console for the SENTINEL Detect object detection and security analytics platform.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${displayFont.variable} ${monoFont.variable}`}>
      <body className="relative h-screen overflow-hidden bg-void bg-grid-fine bg-fixed">
        <div className="grain-overlay" />
        <div className="vignette-overlay" />
        <AuthProvider>
          <div className="relative z-10 flex h-full flex-col">
            <ClassificationBar />
            {children}
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}
