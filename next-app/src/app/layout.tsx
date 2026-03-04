import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Panchakarma Clinic Assistant",
  description: "アーユルヴェーダ・ヘルスケア臨床家向けアシスタント",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ja">
      <body style={{ margin: 0, minHeight: "100vh", background: "#fbfaf7" }}>
        {children}
      </body>
    </html>
  );
}
