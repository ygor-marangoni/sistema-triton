import test from 'node:test'
import assert from 'node:assert/strict'
import { filterMapProperties, findMapProperty, parseReservoirKml, propertyCoordinates } from './mapUtils.js'
import { restorePropertySelection, savePropertySelection } from './propertySelection.js'
import { clearReservoirDraft, restoreNavigation, restoreReservoirDraft, saveNavigation, saveReservoirDraft } from './navigationState.js'

const properties = [
  { id: 1, name: 'Fazenda Horizonte', city: 'Monte Carmelo', state: 'MG', latitude: '-18.731234', longitude: '-47.498765' },
  { id: 2, name: 'Sítio da Serra', city: 'Patrocínio', state: 'MG', latitude: null, longitude: null },
]

test('restores a saved selection only for the same user and authorized properties', () => {
  const values = new Map()
  const storage = { getItem: (key) => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) }
  assert.equal(restorePropertySelection(storage, 11, properties), null)
  savePropertySelection(storage, 11, 2)
  assert.equal(restorePropertySelection(storage, 11, properties), properties[1])
  assert.equal(restorePropertySelection(storage, 12, properties), null)
  assert.equal(restorePropertySelection(storage, 11, [properties[0]]), null)
  assert.equal(restorePropertySelection(null, 11, properties), null)
})

test('restores the current section and reservoir draft only for the same user and property', () => {
  const values = new Map()
  const storage = { getItem: (key) => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: (key) => values.delete(key) }
  saveNavigation(storage, 11, 1, 'Hidrômetros', false)
  assert.deepEqual(restoreNavigation(storage, 11, 1), { tab: 'Hidrômetros', reservoirFormOpen: false })
  saveNavigation(storage, 11, 1, 'Uso hídrico', false)
  assert.equal(restoreNavigation(storage, 11, 1).tab, 'Uso hídrico')
  saveNavigation(storage, 11, 1, 'Hidrômetros', true)
  assert.deepEqual(restoreNavigation(storage, 11, 1), { tab: 'Hidrômetros', reservoirFormOpen: true })
  assert.equal(restoreNavigation(storage, 12, 1).tab, 'Início')
  assert.equal(restoreNavigation(storage, 11, 2).tab, 'Início')
  saveNavigation(storage, 11, 1, 'Início', true)
  saveReservoirDraft(storage, 11, 1, { name: 'Reservatório teste', base_width_m: '2.5', geometry: '<kml>fixture</kml>' })
  assert.equal(restoreNavigation(storage, 11, 1).reservoirFormOpen, true)
  assert.equal(restoreReservoirDraft(storage, 11, 1).base_width_m, '2.5')
  assert.deepEqual(restoreReservoirDraft(storage, 11, 2), {})
  clearReservoirDraft(storage, 11, 1)
  assert.deepEqual(restoreReservoirDraft(storage, 11, 1), {})
  assert.deepEqual(restoreNavigation(null, 11, 1), { tab: 'Início', reservoirFormOpen: false })
})

test('uses only valid coordinate pairs and keeps pending properties unlocated', () => {
  assert.deepEqual(propertyCoordinates(properties[0]), [-18.731234, -47.498765])
  assert.equal(propertyCoordinates(properties[1]), null)
  assert.equal(propertyCoordinates({ latitude: 91, longitude: 20 }), null)
  assert.equal(propertyCoordinates({ latitude: 1, longitude: null }), null)
})

test('search, municipality, and pending-location filters narrow the same property list', () => {
  assert.deepEqual(filterMapProperties(properties, { query: 'horizonte' }).map((item) => item.id), [1])
  assert.deepEqual(filterMapProperties(properties, { city: 'Patrocínio' }).map((item) => item.id), [2])
  assert.deepEqual(filterMapProperties(properties, { location: 'pending' }).map((item) => item.id), [2])
  assert.deepEqual(filterMapProperties(properties, { query: 'sítio', city: 'Patrocínio', location: 'pending' }).map((item) => item.id), [2])
})

test('marker and list selection resolve to the same authorized property record', () => {
  assert.equal(findMapProperty(properties, 2), properties[1])
  assert.equal(findMapProperty(properties, 999), null)
  assert.equal(findMapProperty(properties, undefined), null, 'login must leave selection to the user')
})

test('parses only validated outer rings for the separately labeled reservoir layer', () => {
  const fixtureKml = '<kml><Placemark><Polygon><outerBoundaryIs><LinearRing><coordinates>-47.5,-18.7,0 -47.4,-18.7,0 -47.4,-18.6,0 -47.5,-18.7,0</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark></kml>'
  const rings = parseReservoirKml(fixtureKml)
  assert.equal(rings.length, 1)
  assert.deepEqual(rings[0][0], [-18.7, -47.5])
  assert.deepEqual(parseReservoirKml('<kml><Polygon><outerBoundaryIs><coordinates>200,95 0,0 1,1</coordinates></outerBoundaryIs></Polygon></kml>'), [])
})
