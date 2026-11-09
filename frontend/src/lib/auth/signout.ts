"use client"

import { signOut } from "next-auth/react"

/** Limpia la sesión del BFF antes de salir a cerrar la sesión SSO de Keycloak. */
export async function signOutFederated() {
  await signOut({ redirect: false, callbackUrl: "/login" })
  window.location.assign("/api/auth/oidc-logout")
}
