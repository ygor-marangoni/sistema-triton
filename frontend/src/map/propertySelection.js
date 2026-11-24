import { findMapProperty } from './mapUtils.js'

const keyForUser = (userId) => `triton:property:${userId}`

export function savePropertySelection(storage, userId, propertyId) {
  if (userId == null || propertyId == null) return
  try { storage.setItem(keyForUser(userId), String(propertyId)) } catch { /* Storage can be disabled. */ }
}

export function restorePropertySelection(storage, userId, properties) {
  if (userId == null) return null
  try { return findMapProperty(properties, storage.getItem(keyForUser(userId))) } catch { return null }
}
