"use client"

import { useState } from "react"
import { signIn } from "next-auth/react"
import { ArrowRight, LoaderCircle } from "lucide-react"
import { PRIVATEWAY_OIDC_PROVIDER_ID } from "@/lib/auth/constants"

export function SignInButton() {
  const [busy, setBusy] = useState(false)
  return (
    <button
      type="button"
      disabled={busy}
      onClick={() => {
        setBusy(true)
        void signIn(PRIVATEWAY_OIDC_PROVIDER_ID, { callbackUrl: "/" }).catch(() => setBusy(false))
      }}
      className="inline-flex w-full items-center justify-center gap-3 rounded-xl bg-emerald-900 px-5 py-3.5 text-sm font-semibold text-white transition hover:bg-emerald-800 disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-emerald-800"
    >
      {busy ? <LoaderCircle className="size-4 animate-spin" /> : <ArrowRight className="size-4" />}
      {busy ? "Conectando con tu organización…" : "Continuar con mi organización"}
    </button>
  )
}
