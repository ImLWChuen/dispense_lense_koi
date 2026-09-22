import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Dispense Lens",
  description:
      "AI-assisted industrial dispensing defect diagnosis and troubleshooting platform.",
};

import { AuthProvider } from "@/components/providers/AuthContext";
import { ThemeProvider } from "@/components/providers/ThemeContext";

export default function RootLayout({
                                     children,
                                   }: Readonly<{
  children: React.ReactNode;
}>) {
  return (
      <html lang="en" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              try {
                var t = localStorage.getItem('dispenselens_theme') || 'light';
                var d = t === 'dark' || (t === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
                if (d) {
                  document.documentElement.classList.add('dark');
                  document.documentElement.setAttribute('data-theme', 'dark');
                } else {
                  document.documentElement.classList.remove('dark');
                  document.documentElement.setAttribute('data-theme', 'light');
                }
              } catch (e) {}
            `,
          }}
        />
      </head>
      <body>
        <ThemeProvider>
          <AuthProvider>{children}</AuthProvider>
        </ThemeProvider>
      </body>
      </html>
  );
}