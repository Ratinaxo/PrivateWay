import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PrivateWay | Espacio conversacional",
  description: "Interfaz conversacional unificada de PrivateWay",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="es" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
