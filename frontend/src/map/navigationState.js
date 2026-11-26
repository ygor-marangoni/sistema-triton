const allowedTabs = new Set(['Início', 'Cadastro', 'Evaporação', 'Uso hídrico', 'Meteorologia', 'Outorga', 'Hidrômetros', 'Estação / nível', 'Energia', 'Alertas'])
const navigationKey = (userId) => `triton:navigation:${userId}`
const draftKey = (userId, propertyId) => `triton:reservoir-draft:${userId}:${propertyId}`

export function saveNavigation(storage, userId, propertyId, tab, reservoirFormOpen) {
  if (userId == null || !allowedTabs.has(tab)) return
  try { storage.setItem(navigationKey(userId), JSON.stringify({ propertyId: propertyId ?? null, tab, reservoirFormOpen: Boolean(reservoirFormOpen && propertyId != null) })) } catch { /* Continue without session storage. */ }
}

export function restoreNavigation(storage, userId, propertyId) {
  const fallback = { tab: 'Início', reservoirFormOpen: false }
  if (userId == null) return fallback
  try {
    const saved = JSON.parse(storage.getItem(navigationKey(userId)))
    if (!saved || !allowedTabs.has(saved.tab)) return fallback
    if (saved.tab === 'Cadastro' && saved.propertyId == null && propertyId == null) return { tab: 'Cadastro', reservoirFormOpen: false }
    if (propertyId == null || String(saved.propertyId) !== String(propertyId)) return fallback
    return { tab: saved.tab === 'Cadastro' ? 'Início' : saved.tab, reservoirFormOpen: saved.reservoirFormOpen === true }
  } catch { return fallback }
}

export function saveReservoirDraft(storage, userId, propertyId, draft) {
  if (userId == null || propertyId == null) return
  try { storage.setItem(draftKey(userId, propertyId), JSON.stringify(draft)) } catch { /* Continue if storage is unavailable or full. */ }
}

export function restoreReservoirDraft(storage, userId, propertyId) {
  if (userId == null || propertyId == null) return {}
  try { const draft = JSON.parse(storage.getItem(draftKey(userId, propertyId))); return draft && typeof draft === 'object' && !Array.isArray(draft) ? draft : {} } catch { return {} }
}

export function clearReservoirDraft(storage, userId, propertyId) {
  if (userId == null || propertyId == null) return
  try { storage.removeItem(draftKey(userId, propertyId)) } catch { /* Nothing else to do. */ }
}
