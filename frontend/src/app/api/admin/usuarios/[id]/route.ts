import { NextResponse } from "next/server"
import { updateManagedUser } from "@/lib/keycloak/admin"
import { adminFailure, authorizeAdmin, noStoreHeaders, readSmallJson, validateAdminMutation } from "@/lib/keycloak/http"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

export async function PATCH(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const admin = await authorizeAdmin()
  if (admin.error) return admin.error
  const originError = validateAdminMutation(request)
  if (originError) return originError
  try {
    const { id } = await params
    const data = await readSmallJson(request)
    if (!data || typeof data !== "object" || Array.isArray(data)) {
      return NextResponse.json({ error: { code: "DATOS_INVALIDOS" } }, { status: 422, headers: noStoreHeaders })
    }
    const body = data as Record<string, unknown>
    if (Object.keys(body).some((key) => !["action", "value"].includes(key))) {
      return NextResponse.json({ error: { code: "DATOS_INVALIDOS" } }, { status: 422, headers: noStoreHeaders })
    }
    await updateManagedUser(id, body.action, body.value, admin.id!)
    return NextResponse.json({ ok: true }, { headers: noStoreHeaders })
  } catch (error) {
    return adminFailure(error)
  }
}
