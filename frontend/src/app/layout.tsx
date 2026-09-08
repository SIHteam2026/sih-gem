import type { Metadata } from "next";
import { Geist, Geist_Mono, Stack_Sans_Text } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const stackSans = Stack_Sans_Text({
  subsets: ["latin"],
  variable: "--font-stack-sans",
  weight: ["300", "400", "600", "700"],
});

export const metadata: Metadata = {
  title: "OPAL | Procurement Review",
  description: "Intelligent procurement review layer.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} ${stackSans.variable} antialiased`}
    >
      <body>{children}</body>
    </html>
  );
}
