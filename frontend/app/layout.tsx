import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DispenseLens",
  description:
      "AI-assisted industrial dispensing defect diagnosis and troubleshooting platform.",
};

export default function RootLayout({
                                     children,
                                   }: Readonly<{
  children: React.ReactNode;
}>) {
  return (
      <html lang="en">
      <body>{children}</body>
      </html>
  );
}