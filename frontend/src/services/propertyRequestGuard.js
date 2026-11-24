// Mantém apenas a resposta mais recente da propriedade ainda selecionada.
export function createPropertyRequestGuard(getSelectedId) {
  let revision = 0
  return {
    start(id) {
      const current = ++revision
      return () => revision === current && getSelectedId() === id
    },
    invalidate() { revision += 1 },
  }
}
