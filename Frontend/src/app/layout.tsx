import type { Metadata } from "next"
import type { ReactNode } from "react"
import "./globals.css"

export const metadata: Metadata = {
  title: "PrivateWay | Espacio conversacional",
  description: "Interfaz conversacional unificada de PrivateWay",
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return <html lang="es" className="h-full antialiased"><body className="min-h-full flex flex-col">{children}</body></html>
}
