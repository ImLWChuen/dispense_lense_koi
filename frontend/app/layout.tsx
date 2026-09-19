import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DispenseLens",
  description:
      "AI-assisted industrial dispensing defect diagnosis and troubleshooting platform.",
};

import { AuthProvider } from "@/components/providers/AuthContext";

export default function RootLayout({
                                     children,
                                   }: Readonly<{
  children: React.ReactNode;
}>) {
  return (
      <html lang="en">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
      </html>
  );
}