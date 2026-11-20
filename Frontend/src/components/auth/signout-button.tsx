"use client"

import { useState } from "react"
import { signOutFederated } from "@/lib/auth/signout"
import { LogOut, LoaderCircle } from "lucide-react"

export function SignOutButton({ className = "" }: { className?: string }) {
  const [busy, setBusy] = useState(false)
  return (
    <button type="button" disabled={busy} className={className || "inline-flex items-center gap-2 rounded-xl border border-stone-200 px-4 py-2.5 text-sm font-medium text-stone-700 hover:bg-stone-50 disabled:opacity-60"}
      onClick={() => {
        setBusy(true)
        void signOutFederated().catch(() => setBusy(false))
      }}>
      {busy ? <LoaderCircle className="size-4 animate-spin" /> : <LogOut className="size-4" />}
      {busy ? "Cerrando sesión…" : "Cerrar sesión"}
    </button>
  )
}
