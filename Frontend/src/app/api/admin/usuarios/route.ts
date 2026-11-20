import { NextResponse } from "next/server"
import { createManagedUser, listManagedUsers } from "@/lib/keycloak/admin"
import { adminFailure, authorizeAdmin, noStoreHeaders, readSmallJson, validateAdminMutation } from "@/lib/keycloak/http"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

export async function GET(request: Request) {
  const admin = await authorizeAdmin()
  if (admin.error) return admin.error
  try {
    const search = new URL(request.url).searchParams.get("search") || ""
    const users = await listManagedUsers(search)
    return NextResponse.json({ users, limit: 100 }, { headers: noStoreHeaders })
  } catch (error) {
    return adminFailure(error)
  }
}

export async function POST(request: Request) {
  const admin = await authorizeAdmin()
  if (admin.error) return admin.error
  const originError = validateAdminMutation(request)
  if (originError) return originError
  try {
    const body = await readSmallJson(request)
    await createManagedUser(body)
    return NextResponse.json({ ok: true }, { status: 201, headers: noStoreHeaders })
  } catch (error) {
    return adminFailure(error)
  }
}
