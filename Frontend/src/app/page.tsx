import { ChatWorkspace } from "@/components/chat-workspace"
import { requireSession } from "@/lib/auth/session"

export const dynamic = "force-dynamic"

export default async function Home() {
  const session = await requireSession()
  return <ChatWorkspace user={{ name: session.user.name || "Usuario", email: session.user.email || null, isAdmin: Boolean(session.user.isAdmin) }} />
}
