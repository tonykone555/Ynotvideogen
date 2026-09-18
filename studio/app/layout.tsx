import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "YNOT Gen Studio",
  description: "Mobile-first AI creative studio for product ads",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
