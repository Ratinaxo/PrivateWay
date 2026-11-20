/**
 * OIDC corporativo; ninguna cuenta ficticia ni contraseña local.
 * Configuración exclusivamente del servidor Next.js (BFF).
 */
import type { NextAuthOptions } from "next-auth"
import type { OAuthConfig } from "next-auth/providers/oauth"

type OidcProfile = {
  sub: string
  name?: string | null
  preferred_username?: string | null
  email?: string | null
  picture?: string | null
}

import { PRIVATEWAY_OIDC_PROVIDER_ID } from "./constants"

export function isAuthConfigured(): boolean {
  return Boolean(
    process.env.PRIVATEWAY_OIDC_ISSUER?.trim() &&
    process.env.PRIVATEWAY_OIDC_CLIENT_ID?.trim() &&
    process.env.PRIVATEWAY_OIDC_CLIENT_SECRET?.trim() &&
    process.env.NEXTAUTH_URL?.trim() &&
    process.env.NEXTAUTH_SECRET && process.env.NEXTAUTH_SECRET.length >= 32,
  )
}

function oidcProvider(): OAuthConfig<OidcProfile> {
  const issuer = process.env.PRIVATEWAY_OIDC_ISSUER!.replace(/\/+$/, "")
  return {
    id: PRIVATEWAY_OIDC_PROVIDER_ID,
    name: "Identidad corporativa",
    type: "oauth",
    issuer,
    wellKnown: process.env.PRIVATEWAY_OIDC_WELL_KNOWN?.trim() || `${issuer}/.well-known/openid-configuration`,
    clientId: process.env.PRIVATEWAY_OIDC_CLIENT_ID!,
    clientSecret: process.env.PRIVATEWAY_OIDC_CLIENT_SECRET!,
    authorization: { params: { scope: "openid profile email" } },
    idToken: true,
    checks: ["pkce", "state", "nonce"],
    profile(profile) {
      // sub es la identidad estable del proveedor; el correo NO es un identificador fiable.
      if (!profile.sub) throw new Error("El proveedor no entregó un identificador OIDC")
      return {
        id: profile.sub,
        name: profile.name || profile.preferred_username || "Usuario",
        email: profile.email || null,
        image: profile.picture || null,
      }
    },
  }
}

export const authOptions: NextAuthOptions = {
  secret: process.env.NEXTAUTH_SECRET,
  providers: isAuthConfigured() ? [oidcProvider()] : [],
  pages: { signIn: "/login", error: "/login" },
  session: { strategy: "jwt", maxAge: 8 * 60 * 60 },
  callbacks: {
    async session({ session, token }) {
      if (session.user && typeof token.sub === "string") {
        session.user.id = token.sub
      }
      return session
    },
  },
}
