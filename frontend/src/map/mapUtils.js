export function propertyCoordinates(property) {
  if (property?.latitude == null || property?.longitude == null || property.latitude === '' || property.longitude === '') return null
  const latitude = Number(property.latitude)
  const longitude = Number(property.longitude)
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null
  if (latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) return null
  return [latitude, longitude]
}

export function filterMapProperties(properties, { query = '', city = '', location = 'all' } = {}) {
  const search = query.trim().toLocaleLowerCase('pt-BR')
  return properties.filter((property) => {
    const located = propertyCoordinates(property) !== null
    if (location === 'located' && !located) return false
    if (location === 'pending' && located) return false
    if (city && property.city !== city) return false
    if (!search) return true
    return `${property.name} ${property.city} ${property.state}`.toLocaleLowerCase('pt-BR').includes(search)
  })
}

export function findMapProperty(properties, id) {
  return properties.find((property) => property.id === Number(id)) || null
}

export function parseReservoirKml(kml) {
  const polygons = []
  const polygonPattern = /<(?:[\w.-]+:)?Polygon\b[^>]*>([\s\S]*?)<\/(?:[\w.-]+:)?Polygon\s*>/gi
  let polygonMatch
  while ((polygonMatch = polygonPattern.exec(kml || '')) !== null) {
    const polygonMarkup = polygonMatch[1]
    const outerPattern = /<(?:[\w.-]+:)?outerBoundaryIs\b[^>]*>([\s\S]*?)<\/(?:[\w.-]+:)?outerBoundaryIs\s*>/i
    const outerMatch = outerPattern.exec(polygonMarkup)
    if (!outerMatch) continue
    const coordinateMatch = /<(?:[\w.-]+:)?coordinates\b[^>]*>([\s\S]*?)<\/(?:[\w.-]+:)?coordinates\s*>/i.exec(outerMatch[1])
    if (!coordinateMatch) continue
    const ring = coordinateMatch[1].trim().split(/\s+/).map((position) => {
      const [longitudeText, latitudeText] = position.split(',')
      const latitude = Number(latitudeText)
      const longitude = Number(longitudeText)
      if (!Number.isFinite(latitude) || !Number.isFinite(longitude) || latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) return null
      return [latitude, longitude]
    })
    if (ring.length >= 3 && ring.every(Boolean)) polygons.push(ring)
  }
  return polygons
}
