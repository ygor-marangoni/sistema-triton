import { useEffect, useMemo, useRef, useState } from 'react'
import { CircleMarker, MapContainer, Polygon, Popup, TileLayer, useMap, useMapEvents } from 'react-leaflet'
import { ArrowUpRight, ChevronDown, ChevronUp, Crosshair, MapPin, Search, TriangleAlert } from 'lucide-react'
import { alertService, propertyService } from '../services/triton'
import { errorMessage } from '../api/client'
import { filterMapProperties, findMapProperty, parseReservoirKml, propertyCoordinates } from '../map/mapUtils'
import WorkspaceSummary from './WorkspaceSummary'
import 'leaflet/dist/leaflet.css'

const DEFAULT_CENTER = [-14.235, -51.925]
const TILE_URL = import.meta.env.VITE_OSM_TILE_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
const TILE_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'

function ViewportController({ activeId, activeCoordinates, locatedProperties, reservoirLayers }) {
  const map = useMap()
  const initialFitDone = useRef(false)

  useEffect(() => {
    if (activeCoordinates) {
      map.setView(activeCoordinates, Math.max(map.getZoom(), 13), { animate: true })
      return
    }
    const reservoirCoordinates = reservoirLayers.flatMap((layer) => layer.rings.flat())
    if (activeId != null && reservoirCoordinates.length) {
      map.fitBounds(reservoirCoordinates, { padding: [32, 32], maxZoom: 15 })
      return
    }
    if (!initialFitDone.current && locatedProperties.length) {
      if (locatedProperties.length === 1) map.setView(locatedProperties[0].coordinates, 12)
      else map.fitBounds(locatedProperties.map((property) => property.coordinates), { padding: [32, 32], maxZoom: 11 })
      initialFitDone.current = true
    }
  }, [activeCoordinates, activeId, locatedProperties, map, reservoirLayers])

  return null
}

function MapClickPicker({ enabled, onPick }) {
  useMapEvents({
    click(event) {
      if (enabled) onPick(event.latlng.lat, event.latlng.lng)
    },
  })
  return null
}

function MapSizeSynchronizer() {
  const map = useMap()
  useEffect(() => {
    const observer = new ResizeObserver(() => map.invalidateSize({ pan: false }))
    observer.observe(map.getContainer())
    return () => observer.disconnect()
  }, [map])
  return null
}

function latestPropertyReadings(dashboard) {
  const levels = (dashboard?.latest_levels || []).filter((entry) => entry.latest).map((entry) => ({
    key: `level-${entry.reservoir_id}`,
    label: `Nível · ${entry.reservoir_name}`,
    value: `${Number(entry.latest.level_m).toLocaleString('pt-BR', { maximumFractionDigits: 3 })} m`,
    source: entry.latest.source,
    observedAt: entry.latest.observed_at,
  }))
  const meters = (dashboard?.recent_hydrometers || []).flatMap(({ hydrometer, readings }) => (readings || []).slice(0, 1).map((reading) => ({
    key: `meter-${hydrometer.id}`,
    label: `Hidrômetro · ${hydrometer.name}`,
    value: reading.volume_m3 == null ? 'Volume indisponível' : `${Number(reading.volume_m3).toLocaleString('pt-BR', { maximumFractionDigits: 3 })} m³`,
    source: reading.source,
    observedAt: reading.observed_at,
  })))
  return [...levels, ...meters].filter((entry) => entry.observedAt).sort((a, b) => new Date(b.observedAt) - new Date(a.observedAt)).slice(0, 3)
}

function formatObservedAt(value) {
  return new Date(value).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

function sourceLabel(source) {
  return ({ manual: 'informado manualmente', simulada: 'simulado', dispositivo: 'dispositivo', imagem_revisada: 'imagem revisada' })[source] || source
}

export default function PropertyMapPage({ properties, selectedProperty, onOpenProperty, onAddProperty, onPropertyUpdated, dashboard, meters, outorgas, alerts, latestActivity, propertyDataPending, propertyLoadError, onNavigate, isDemo }) {
  const [query, setQuery] = useState('')
  const [city, setCity] = useState('')
  const [locationFilter, setLocationFilter] = useState('all')
  const [mobileListOpen, setMobileListOpen] = useState(false)
  const [activeId, setActiveId] = useState(selectedProperty?.id ?? null)
  const [editingId, setEditingId] = useState(null)
  const [draft, setDraft] = useState({ latitude: '', longitude: '' })
  const [saving, setSaving] = useState(false)
  const [notice, setNotice] = useState('')
  const [locationError, setLocationError] = useState('')
  const [tilesFailed, setTilesFailed] = useState(false)
  const [summary, setSummary] = useState(null)
  const [summaryLoading, setSummaryLoading] = useState(false)
  const [summaryError, setSummaryError] = useState('')
  const [reservoirs, setReservoirs] = useState([])
  const [reservoirsLoading, setReservoirsLoading] = useState(false)
  const [enabledReservoirs, setEnabledReservoirs] = useState([])
  const [reservoirLayers, setReservoirLayers] = useState([])
  const [reservoirError, setReservoirError] = useState('')
  const markerRefs = useRef({})

  const filtered = useMemo(() => filterMapProperties(properties, { query, city, location: locationFilter }), [properties, query, city, locationFilter])
  const cities = useMemo(() => [...new Set(properties.map((property) => property.city).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'pt-BR')), [properties])
  const located = useMemo(() => filtered.flatMap((property) => {
    const coordinates = propertyCoordinates(property)
    return coordinates ? [{ ...property, coordinates }] : []
  }), [filtered])
  const pending = filtered.filter((property) => propertyCoordinates(property) === null)
  const activeProperty = findMapProperty(properties, activeId)
  const activeCoordinates = propertyCoordinates(activeProperty)

  useEffect(() => {
    if (selectedProperty?.id != null) setActiveId(selectedProperty.id)
  }, [selectedProperty?.id])

  useEffect(() => {
    if (activeId != null && !filtered.some((property) => property.id === activeId)) {
      setActiveId(null)
      setEditingId(null)
    }
  }, [activeId, filtered])

  useEffect(() => {
    Object.entries(markerRefs.current).forEach(([id, marker]) => {
      if (!marker) return
      if (Number(id) === activeId) marker.openPopup()
      else marker.closePopup()
    })
  }, [activeId, located])

  useEffect(() => {
    if (!activeProperty) {
      setSummary(null)
      setSummaryError('')
      setReservoirs([])
      setEnabledReservoirs([])
      setReservoirLayers([])
      return
    }
    let current = true
    setSummary(null)
    setSummaryError('')
    setSummaryLoading(true)
    Promise.all([propertyService.dashboard(activeProperty.id), alertService.list(activeProperty.id, 'open')])
      .then(([dashboardResponse, alertResponse]) => {
        if (current) setSummary({ dashboard: dashboardResponse.data, alerts: alertResponse.data })
      })
      .catch((error) => { if (current) setSummaryError(errorMessage(error)) })
      .finally(() => { if (current) setSummaryLoading(false) })

    setReservoirs([])
    setEnabledReservoirs([])
    setReservoirLayers([])
    setReservoirError('')
    setReservoirsLoading(true)
    propertyService.reservoirs(activeProperty.id)
      .then(({ data }) => { if (current) setReservoirs(data) })
      .catch((error) => { if (current) setReservoirError(errorMessage(error)) })
      .finally(() => { if (current) setReservoirsLoading(false) })
    return () => { current = false }
  }, [activeProperty?.id])

  useEffect(() => {
    if (!activeProperty || !enabledReservoirs.length) {
      setReservoirLayers([])
      return
    }
    let current = true
    setReservoirError('')
    Promise.all(enabledReservoirs.map((reservoirId) => propertyService.reservoirGeometry(reservoirId)))
      .then((responses) => {
        if (!current) return
        setReservoirLayers(responses.map(({ data }) => ({ id: data.id, name: data.name, rings: parseReservoirKml(data.geometry_kml) })))
      })
      .catch((error) => { if (current) setReservoirError(errorMessage(error)) })
    return () => { current = false }
  }, [activeProperty?.id, enabledReservoirs])

  function selectMapProperty(id) {
    const property = findMapProperty(properties, id)
    if (!property) return
    setActiveId(property.id)
    setEditingId(null)
    setMobileListOpen(false)
    setNotice('')
    setLocationError('')
  }

  function beginLocationEdit(property) {
    const coordinates = propertyCoordinates(property)
    setActiveId(property.id)
    setEditingId(property.id)
    setMobileListOpen(false)
    setDraft({ latitude: coordinates ? String(property.latitude) : '', longitude: coordinates ? String(property.longitude) : '' })
    setLocationError('')
    setNotice('Clique no mapa ou informe as coordenadas da propriedade.')
  }

  function pickMapPoint(latitude, longitude) {
    if (editingId == null) return
    setDraft({ latitude: latitude.toFixed(6), longitude: longitude.toFixed(6) })
    setLocationError('')
  }

  async function savePosition(event) {
    event.preventDefault()
    const latitude = Number(draft.latitude)
    const longitude = Number(draft.longitude)
    if (!draft.latitude.trim() || !draft.longitude.trim() || !propertyCoordinates({ latitude, longitude })) {
      setLocationError('Informe latitude entre −90 e 90 e longitude entre −180 e 180.')
      return
    }
    setSaving(true)
    setLocationError('')
    setNotice('')
    try {
      const { data } = await propertyService.update(editingId, { latitude, longitude })
      onPropertyUpdated(data)
      setEditingId(null)
      setDraft({ latitude: String(data.latitude), longitude: String(data.longitude) })
      setNotice('Posição da propriedade salva.')
    } catch (error) {
      setLocationError(errorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  async function clearPosition() {
    if (!activeProperty) return
    setSaving(true)
    setLocationError('')
    setNotice('')
    try {
      const { data } = await propertyService.update(activeProperty.id, { latitude: null, longitude: null })
      onPropertyUpdated(data)
      setEditingId(null)
      setDraft({ latitude: '', longitude: '' })
      setNotice('Localização removida; a propriedade voltou para pendentes.')
    } catch (error) {
      setLocationError(errorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  function toggleReservoir(reservoirId) {
    setEnabledReservoirs((current) => current.includes(reservoirId) ? current.filter((id) => id !== reservoirId) : [...current, reservoirId])
  }

  const recentReadings = latestPropertyReadings(summary?.dashboard)

  return <section className="property-map-page">
    <div className="map-page-heading"><div><p className="eyebrow">SEU ESPAÇO DE MONITORAMENTO</p><h1>Visão da operação</h1><p>Escolha uma propriedade e acompanhe seus dados em um só lugar.</p></div><div className="map-heading-actions"><span className="map-total">{properties.length} {properties.length === 1 ? 'propriedade' : 'propriedades'}</span>{properties.length > 0 && <button className="button secondary" type="button" onClick={onAddProperty}><MapPin size={15} aria-hidden="true" />Cadastrar propriedade</button>}</div></div>
    {isDemo && <div className="demo-map-note">Demonstração: as posições e os perímetros exibidos nesta conta são fictícios.</div>}
    <WorkspaceSummary properties={properties} selectedProperty={selectedProperty} loading={propertyDataPending} error={propertyLoadError} dashboard={dashboard} meters={meters} outorgas={outorgas} alerts={alerts} latestActivity={latestActivity} onNavigate={onNavigate} />
    <div className="map-filters">
      <label className="map-search-field"><span>Busca</span><span className="map-search"><Search size={17} aria-hidden="true" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar propriedade ou município" /></span></label>
      <label className="field"><span>Município</span><select value={city} onChange={(event) => setCity(event.target.value)}><option value="">Todos</option>{cities.map((name) => <option key={name} value={name}>{name}</option>)}</select></label>
      <label className="field"><span>Localização</span><select value={locationFilter} onChange={(event) => setLocationFilter(event.target.value)}><option value="all">Todas</option><option value="located">Com posição</option><option value="pending">Pendente</option></select></label>
    </div>

    {properties.length === 0 ? <div className="map-empty"><MapPin size={20} aria-hidden="true" /><div><b>Nenhuma propriedade cadastrada</b><span>Cadastre sua primeira propriedade para começar. Depois, informe a posição conferida no mapa.</span></div><button className="button primary" type="button" onClick={onAddProperty}>Cadastrar propriedade</button></div> : <div className="property-map-layout">
      <div className={`map-canvas-wrap${editingId != null ? ' picking' : ''}${located.length === 0 && editingId == null ? ' map-canvas-empty' : ''}`}>
        <MapContainer center={DEFAULT_CENTER} zoom={4} scrollWheelZoom={false} className="property-map-canvas" aria-label="Mapa de propriedades">
          <TileLayer url={TILE_URL} attribution={TILE_ATTRIBUTION} eventHandlers={{ loading: () => setTilesFailed(false), tileerror: () => setTilesFailed(true) }} />
          <MapSizeSynchronizer />
          <ViewportController activeId={activeId} activeCoordinates={activeCoordinates} locatedProperties={located} reservoirLayers={reservoirLayers} />
          <MapClickPicker enabled={editingId != null} onPick={pickMapPoint} />
          {located.map((property) => <CircleMarker
            key={property.id}
            ref={(marker) => { if (marker) markerRefs.current[property.id] = marker; else delete markerRefs.current[property.id] }}
            center={property.coordinates}
            radius={activeId === property.id ? 10 : 7}
            pathOptions={{ color: activeId === property.id ? '#075f58' : '#ffffff', weight: 2, fillColor: '#087e75', fillOpacity: 0.95 }}
            eventHandlers={{ click: () => selectMapProperty(property.id) }}
            bubblingMouseEvents={false}
          >
            <Popup><div className="map-popup"><b>{property.name}</b><span>{property.city}/{property.state}</span>{activeProperty?.id === property.id && recentReadings[0] && <small>{recentReadings[0].label}: {recentReadings[0].value}</small>}{activeProperty?.id === property.id && summary && <small>{summary.alerts.length ? `${summary.alerts.length} alerta(s) aberto(s)` : 'Nenhum alerta aberto'}</small>}<button type="button" onClick={() => onOpenProperty(property)}>Selecionar propriedade <ArrowUpRight size={14} aria-hidden="true" /></button></div></Popup>
          </CircleMarker>)}
          {reservoirLayers.flatMap((layer) => layer.rings.map((ring, index) => <Polygon key={`${layer.id}-${index}`} positions={ring} pathOptions={{ color: '#548c96', weight: 2, fillColor: '#7eb3bb', fillOpacity: 0.18 }} />))}
          {editingId != null && draft.latitude && draft.longitude && propertyCoordinates(draft) && <CircleMarker center={propertyCoordinates(draft)} radius={9} pathOptions={{ color: '#ffffff', weight: 2, fillColor: '#d89a34', fillOpacity: 1 }} />}
        </MapContainer>
        {tilesFailed && <div className="map-tile-warning" role="status"><TriangleAlert size={16} aria-hidden="true" /><span>Não foi possível carregar o mapa base. A lista e os dados das propriedades continuam disponíveis.</span></div>}
          {located.length === 0 && <div className="map-no-locations"><MapPin size={17} aria-hidden="true" /><span>As propriedades pendentes não aparecem como marcadores. Selecione uma na lista para abrir o painel ou definir a posição.</span></div>}
        {editingId != null && <div className="map-pick-hint"><Crosshair size={15} aria-hidden="true" />Clique no mapa para definir a posição de {activeProperty?.name}.</div>}
      </div>

      <aside className={`map-side-panel${mobileListOpen ? ' mobile-list-open' : ''}`}>
        <div className="map-list-heading"><div><b>Lista de propriedades</b><small>{filtered.length} resultado(s)</small></div><button className="map-mobile-list-toggle" type="button" aria-expanded={mobileListOpen} onClick={() => setMobileListOpen((open) => !open)}>{mobileListOpen ? 'Ocultar lista' : 'Mostrar lista'}{mobileListOpen ? <ChevronUp size={15} aria-hidden="true" /> : <ChevronDown size={15} aria-hidden="true" />}</button></div>
        <div className="map-property-list">
          {located.length > 0 && <section className="map-list-group"><h2>Com posição informada</h2>{located.map((property) => <button type="button" key={property.id} aria-pressed={activeId === property.id} className={`map-property-row${activeId === property.id ? ' active' : ''}`} onClick={() => selectMapProperty(property.id)}><MapPin size={16} aria-hidden="true" /><span><b>{property.name}</b><small>{property.city}/{property.state}</small></span><span className="map-row-coordinates">{property.latitude}, {property.longitude}</span></button>)}</section>}
          {pending.length > 0 && <section className="map-list-group"><h2>Localização pendente</h2>{pending.map((property) => <div key={property.id} className={`map-pending-row${activeId === property.id ? ' active' : ''}`}><button type="button" aria-pressed={activeId === property.id} className="map-pending-select" onClick={() => selectMapProperty(property.id)}><MapPin size={16} aria-hidden="true" /><span><b>{property.name}</b><small>{property.city}/{property.state} · sem coordenadas</small></span></button><button type="button" className="text-button" onClick={() => beginLocationEdit(property)}>Definir posição</button></div>)}</section>}
          {filtered.length === 0 && <p className="map-no-results">Nenhuma propriedade corresponde aos filtros.</p>}
        </div>

        {activeProperty && <section className="map-selected-property">
          <div className="map-selected-heading"><div><small>PRÉVIA DA PROPRIEDADE</small><h2>{activeProperty.name}</h2><p>{activeProperty.city}/{activeProperty.state}</p></div></div>
          {!activeCoordinates && <p className="map-pending-note">Localização pendente. Você pode abrir o painel agora e cadastrar a posição quando tiver as coordenadas conferidas.</p>}
          {summaryLoading ? <p className="map-muted">Carregando leituras e alertas…</p> : summaryError ? <p className="map-inline-error">{summaryError}</p> : <>
            <div className="map-summary-state"><span>Alertas abertos</span><b>{summary ? summary.alerts.length : '—'}</b></div>
            {recentReadings.length ? <div className="map-recent-list">{recentReadings.map((reading) => <div key={reading.key}><span>{reading.label}</span><b>{reading.value}</b><small>{sourceLabel(reading.source)} · {formatObservedAt(reading.observedAt)}</small></div>)}</div> : <p className="map-muted">Ainda não há leituras registradas para esta propriedade.</p>}
          </>}
          <button type="button" className="button primary map-open-dashboard" onClick={() => onOpenProperty(activeProperty)}>Selecionar propriedade <ArrowUpRight size={16} aria-hidden="true" /></button>
          {reservoirsLoading ? <p className="map-muted">Carregando reservatórios…</p> : reservoirs.length > 0 && <div className="reservoir-map-layers"><b>Camadas de reservatório</b>{reservoirs.map((reservoir) => <label key={reservoir.id}><input type="checkbox" checked={enabledReservoirs.includes(reservoir.id)} onChange={() => toggleReservoir(reservoir.id)} />{reservoir.name} · perímetro do reservatório</label>)}</div>}
          {reservoirError && <p className="map-inline-error">Não foi possível carregar o perímetro do reservatório. {reservoirError}</p>}
          {notice && <p className="map-inline-success" role="status">{notice}</p>}
          {locationError && <p className="map-inline-error" role="alert">{locationError}</p>}
          {editingId === activeProperty.id ? <form className="map-coordinate-form" onSubmit={savePosition}>
            <b>Posição informada</b><span>Use um ponto conferido em campo. Clique no mapa ou digite as coordenadas em graus decimais.</span>
            <div className="form-grid"><label className="field"><span>Latitude</span><input type="number" name="latitude" min="-90" max="90" step="0.000001" value={draft.latitude} onChange={(event) => setDraft((current) => ({ ...current, latitude: event.target.value }))} required /></label><label className="field"><span>Longitude</span><input type="number" name="longitude" min="-180" max="180" step="0.000001" value={draft.longitude} onChange={(event) => setDraft((current) => ({ ...current, longitude: event.target.value }))} required /></label></div>
            <div className="map-coordinate-actions"><button type="button" className="button secondary" disabled={saving} onClick={() => { setEditingId(null); setLocationError(''); setNotice('') }}>Cancelar</button><button type="submit" className="button primary" disabled={saving}>{saving ? 'Salvando…' : 'Salvar posição'}</button></div>
          </form> : <div className="map-location-actions"><button type="button" className="button secondary" onClick={() => beginLocationEdit(activeProperty)}>{activeCoordinates ? 'Corrigir posição' : 'Cadastrar posição'}</button>{activeCoordinates && <button type="button" className="text-button" disabled={saving} onClick={clearPosition}>Remover posição</button>}</div>}
        </section>}
      </aside>
    </div>}
  </section>
}
