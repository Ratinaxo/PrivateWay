import { NextResponse } from "next/server"

export const dynamic = "force-dynamic"

export function GET() {
  const site = process.env.NEXTAUTH_URL || "http://127.0.0.1:8080"
  const issuer = process.env.PRIVATEWAY_OIDC_ISSUER
  const clientId = process.env.PRIVATEWAY_OIDC_CLIENT_ID
  const fallback = new URL("/login", site)
  if (!issuer || !clientId) return NextResponse.redirect(fallback)
  const logout = new URL(`${issuer.replace(/\/+$/, "")}/protocol/openid-connect/logout`)
  logout.searchParams.set("client_id", clientId)
  logout.searchParams.set("post_logout_redirect_uri", fallback.toString())
  return NextResponse.redirect(logout, { headers: { "Cache-Control": "no-store" } })
}
