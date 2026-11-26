import { api } from '../api/client'

// Existing screens paginate locally; collect every API page so later records remain accessible.
async function listAll(path, params = {}) {
  const data = []
  let skip = 0
  while (true) {
    const response = await api.get(path, { params: { ...params, skip, limit: 100 } })
    data.push(...response.data)
    if (response.data.length < 100) return { ...response, data }
    skip += 100
  }
}

export const authService = {
  session: () => api.get('/auth/session'),
  me: () => api.get('/auth/me'),
  login: (data) => api.post('/auth/login', data),
  register: (data) => api.post('/auth/register', data),
  logout: () => api.post('/auth/logout'),
}

export const adminService = {
  users: () => api.get('/admin/users'),
  createUser: (data) => api.post('/admin/users', data),
}

export const propertyService = {
  list: () => listAll('/properties'),
  archived: () => listAll('/properties', { include_archived: true }).then((response) => ({ ...response, data: response.data.filter((property) => property.is_archived) })),
  create: (data) => api.post('/properties', data),
  update: (id, data) => api.patch(`/properties/${id}`, data),
  archive: (id) => api.delete(`/properties/${id}`),
  restore: (id) => api.post(`/properties/${id}/restore`),
  dashboard: (id) => api.get(`/dashboard/${id}`),
  reservoirs: (id) => api.get(`/properties/${id}/reservoirs`),
  reservoirGeometry: (reservoirId) => api.get(`/reservoirs/${reservoirId}/map-geometry`),
  createReservoir: (propertyId, data) => api.post(`/properties/${propertyId}/reservoirs`, data),
}

export const waterService = {
  outorgas: (propertyId) => listAll(`/properties/${propertyId}/outorgas`),
  createOutorga: (data) => api.post('/outorgas', data),
  updateDemand: (outorgaId, month, data) => api.patch(`/outorgas/${outorgaId}/monthly-demands/${month}`, data),
  meters: (propertyId) => listAll('/hydrometers', { property_id: propertyId }),
  createMeter: (data) => api.post('/hydrometers', data),
  editMeter: (id, data) => api.patch(`/hydrometers/${id}`, data),
  meterState: (id, is_active) => api.patch(`/hydrometers/${id}/state`, { is_active }),
  meterHistory: (id, params = {}) => api.get(`/hydrometers/${id}/history`, { params }),
  meterEvents: (id, params = {}) => api.get(`/hydrometers/${id}/totalizer-events`, { params }),
  createMeterEvent: (id, data) => api.post(`/hydrometers/${id}/totalizer-events`, data),
  meterOutorgaLinks: (id, params = {}) => api.get(`/hydrometers/${id}/outorga-links`, { params }),
  createMeterOutorgaLink: (id, data) => api.post(`/hydrometers/${id}/outorga-links`, data),
  closeMeterOutorgaLink: (id, data) => api.post(`/hydrometer-outorga-links/${id}/close`, data),
  reviewMeterReading: (id, data) => api.post(`/hydrometer-readings/${id}/review`, data),
  reviewLevelReading: (id, data) => api.post(`/level-readings/${id}/review`, data),
  editPermit: (id, data) => api.patch(`/outorgas/${id}`, data),
  permitState: (id, is_active) => api.patch(`/outorgas/${id}/state`, { is_active }),
  permitHistory: (id, params = {}) => api.get(`/outorgas/${id}/history`, { params }),
  readMeter: (id, data) => api.post(`/hydrometers/${id}/readings`, data),
  stations: (propertyId) => listAll('/level-stations', { property_id: propertyId }),
  createStation: (data) => api.post('/level-stations', data),
  updateStation: (id, data) => api.patch(`/level-stations/${id}`, data),
  deleteStation: (id) => api.delete(`/level-stations/${id}`),
  readLevel: (id, data) => api.post(`/level-stations/${id}/readings`, data),
  tariffs: (propertyId) => api.get(`/energy/tariffs/${propertyId}`),
  createTariff: (data) => api.post('/energy/tariffs', data),
  aneelCemigTariffs: (propertyId) => api.get(`/energy/tariffs/aneel/cemig/catalog/${propertyId}`),
  importAneelCemigTariff: (data) => api.post('/energy/tariffs/aneel/cemig/import', data),
  energy: (propertyId) => api.get(`/energy/estimate/${propertyId}`),
  evaporation: (propertyId) => api.get(`/evaporation/estimate/${propertyId}`),
  recordBalance: (reservoirId, data) => api.post(`/reservoirs/${reservoirId}/water-balance/monthly`, data),
  calculateAutomaticBalance: (reservoirId, year, month) => api.post(`/reservoirs/${reservoirId}/water-balance/monthly/automatic`, null, { params: { year, month } }),
  createOtherOutflow: (reservoirId, data) => api.post(`/reservoirs/${reservoirId}/water-balance/other-outflows`, data),
  reviewOtherOutflow: (id, data) => api.post(`/water-balance/other-outflows/${id}/review`, data),
  balanceSourceEvidence: (reservoirId, year, month, params = {}) => api.get(`/reservoirs/${reservoirId}/water-balance/source-evidence`, { params: { year, month, ...params } }),
  createRainfallInterval: (propertyId, data) => api.post(`/properties/${propertyId}/rainfall-intervals`, data),
  reviewRainfall: (id, data) => api.post(`/meteorological-observations/${id}/review`, data),
  balanceHistory: (propertyId, year) => api.get(`/properties/${propertyId}/water-balance/monthly`, { params: { year } }),
  permitDocuments: (propertyId, params = {}) => api.get(`/properties/${propertyId}/permit-documents`, { params }),
  uploadPermitDocument: (propertyId, file) => { const form = new FormData(); form.append('file', file); return api.post(`/properties/${propertyId}/permit-documents`, form) },
  permitDocumentFile: (id) => api.get(`/permit-documents/${id}/file`, { responseType: 'blob' }),
  reviewPermitDocument: (id, data) => api.post(`/permit-documents/${id}/review`, data),
  extractPermitField: (id, data) => api.post(`/permit-documents/${id}/extract`, data),
  permitDocumentHistory: (id, params = {}) => api.get(`/permit-documents/${id}/history`, { params }),
  curves: (reservoirId, params = {}) => api.get(`/reservoirs/${reservoirId}/stage-volume-curves`, { params }),
  createCurve: (reservoirId, data) => api.post(`/reservoirs/${reservoirId}/stage-volume-curves`, data),
  approveCurve: (id, data) => api.post(`/stage-volume-curves/${id}/approve`, data),
  curveVolume: (id, level, at) => api.get(`/stage-volume-curves/${id}/volume`, { params: { level, at } }),
}

export const alertService = {
  list: (propertyId, status, pagination = {}) => api.get(`/alerts/${propertyId}`, { params: { ...(status ? { status } : {}), ...pagination } }),
  evaluate: (propertyId) => api.post(`/alerts/${propertyId}/evaluate`),
  resolve: (alertId, note = null) => api.post(`/alerts/${alertId}/resolve`, { note }),
}

export const meteorologyService = {
  get: (propertyId, params = {}) => api.get(`/properties/${propertyId}/meteorology`, { params }),
  setStation: (propertyId, data) => api.put(`/properties/${propertyId}/meteorology/station`, data),
  sync: (propertyId, year) => api.post(`/properties/${propertyId}/meteorology/sync`, { year }),
}

export const rulerImageService = {
  list: (stationId, params = {}) => api.get(`/level-stations/${stationId}/image-reviews`, { params }),
  upload: (stationId, file, capturedAt) => {
    const form = new FormData()
    form.append('file', file)
    form.append('captured_at', capturedAt)
    return api.post(`/level-stations/${stationId}/image-reviews`, form, { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  get: (reviewId) => api.get(`/level-image-reviews/${reviewId}`),
  image: (reviewId) => api.get(`/level-image-reviews/${reviewId}/image`, { responseType: 'blob' }),
  suggest: (reviewId, level_m) => api.post(`/level-image-reviews/${reviewId}/suggestion`, { level_m }),
  calibrate: (reviewId, data) => api.post(`/level-image-reviews/${reviewId}/calibrate`, data),
  confirm: (reviewId, level_m) => api.post(`/level-image-reviews/${reviewId}/confirm`, { level_m }),
  history: (reviewId) => api.get(`/level-image-reviews/${reviewId}/history`),
}
