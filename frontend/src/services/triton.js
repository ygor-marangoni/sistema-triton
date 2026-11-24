import { api } from '../api/client'

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
  list: () => api.get('/properties'),
  create: (data) => api.post('/properties', data),
  update: (id, data) => api.patch(`/properties/${id}`, data),
  dashboard: (id) => api.get(`/dashboard/${id}`),
  reservoirs: (id) => api.get(`/properties/${id}/reservoirs`),
  reservoirGeometry: (reservoirId) => api.get(`/reservoirs/${reservoirId}/map-geometry`),
  createReservoir: (propertyId, data) => api.post(`/properties/${propertyId}/reservoirs`, data),
}

export const waterService = {
  outorgas: (propertyId) => api.get(`/properties/${propertyId}/outorgas`),
  createOutorga: (data) => api.post('/outorgas', data),
  updateDemand: (outorgaId, month, data) => api.patch(`/outorgas/${outorgaId}/monthly-demands/${month}`, data),
  meters: (propertyId) => api.get('/hydrometers', { params: { property_id: propertyId } }),
  createMeter: (data) => api.post('/hydrometers', data),
  readMeter: (id, data) => api.post(`/hydrometers/${id}/readings`, data),
  stations: (propertyId) => api.get('/level-stations', { params: { property_id: propertyId } }),
  createStation: (data) => api.post('/level-stations', data),
  updateStation: (id, data) => api.patch(`/level-stations/${id}`, data),
  deleteStation: (id) => api.delete(`/level-stations/${id}`),
  readLevel: (id, data) => api.post(`/level-stations/${id}/readings`, data),
  tariffs: (propertyId) => api.get(`/energy/tariffs/${propertyId}`),
  createTariff: (data) => api.post('/energy/tariffs', data),
  energy: (propertyId) => api.get(`/energy/estimate/${propertyId}`),
  evaporation: (propertyId) => api.get(`/evaporation/estimate/${propertyId}`),
}

export const alertService = {
  list: (propertyId, status) => api.get(`/alerts/${propertyId}`, { params: status ? { status } : {} }),
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
