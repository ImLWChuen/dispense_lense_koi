import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Dispense Lens",
  description:
      "AI-assisted industrial dispensing defect diagnosis and troubleshooting platform.",
};

import { AuthProvider } from "@/components/providers/AuthContext";
import { ThemeProvider } from "@/components/providers/ThemeProvider";

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
                const t = localStorage.getItem('dispenselens_theme') || 'light';
                const d = localStorage.getItem('dispenselens_density') || 'comfortable';
                const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
                const isDark = t === 'dark' || (t === 'system' && prefersDark);
                if (isDark) {
                  document.documentElement.classList.add('dark');
                  document.documentElement.setAttribute('data-theme', 'dark');
                } else {
                  document.documentElement.classList.remove('dark');
                  document.documentElement.setAttribute('data-theme', 'light');
                }
                document.documentElement.setAttribute('data-density', d);
                if (d === 'compact') {
                  document.documentElement.classList.add('density-compact');
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