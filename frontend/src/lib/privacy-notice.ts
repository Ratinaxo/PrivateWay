/** La acción global puede proteger el historial sin modificar el último mensaje. */
export function shouldNotifyCurrentMessage(decision: unknown): boolean {
  return !!decision && typeof decision === "object" &&
    "accion" in decision && decision.accion === "seudonimizar" &&
    "mensaje_actual_seudonimizado" in decision && decision.mensaje_actual_seudonimizado === true
}
