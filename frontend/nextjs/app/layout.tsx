import type { Metadata } from "next";
import { Lexend } from "next/font/google";
import PlausibleProvider from "next-plausible";
import { GoogleAnalytics } from '@next/third-parties/google'
import "./globals.css";

const inter = Lexend({ subsets: ["latin"] });

let title = "Arivara Researcher";
let description =
  "LLM based autonomous agent that conducts local and web research on any topic and generates a comprehensive report with citations.";
let ogimage = "/favicon.ico";
let sitename = "Arivara Researcher";

export const metadata: Metadata = {
  title,
  description,
  icons: {
    icon: "/favicon.ico",
  },
  openGraph: {
    images: [ogimage],
    title,
    description,
    siteName: sitename,
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    images: [ogimage],
    title,
    description,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {

  return (
    <html className="gptr-root" lang="en">
      <head>
        <PlausibleProvider domain="localhost:3000" />
        <GoogleAnalytics gaId={process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID!} />
      </head>
      <body
        className={`app-container ${inter.className} flex min-h-screen flex-col justify-between`}
        suppressHydrationWarning
      >
        {children}
      </body>
    </html>
  );
}
