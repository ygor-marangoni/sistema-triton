import { useEffect, useMemo, useState } from 'react'
import { CircleMarker, MapContainer, Polygon, Popup, TileLayer, useMap } from 'react-leaflet'
import { MapPin, Waves } from 'lucide-react'
import { meteorologyService, propertyService } from '../services/triton'
import { parseReservoirKml, propertyCoordinates } from '../map/mapUtils'
import 'leaflet/dist/leaflet.css'

const tiles = import.meta.env.VITE_OSM_TILE_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'

function FitMap({ points }) {
  const map = useMap()
  useEffect(() => {
    if (!points.length) return
    if (points.length === 1) map.setView(points[0], 14)
    else map.fitBounds(points, { padding: [36, 36], maxZoom: 16 })
    setTimeout(() => map.invalidateSize(), 0)
  }, [map, points])
  return null
}

export default function BalanceMap({ property, meters, reservoirs, metersError = false, reservoirsError = false }) {
  const [layers, setLayers] = useState([])
  const [station, setStation] = useState(null)
  const [loading, setLoading] = useState(true)
  const [errors, setErrors] = useState([])
  useEffect(() => {
    let active = true
    setLoading(true); setLayers([]); setStation(null); setErrors([])
    const requests = [propertyService.geometry(property.id), meteorologyService.get(property.id), ...reservoirs.map((item) => propertyService.reservoirGeometry(item.id))]
    Promise.allSettled(requests).then((results) => {
      if (!active) return
      const next = []
      if (results[0].status === 'fulfilled') next.push({ name: 'Propriedade', rings: parseReservoirKml(results[0].value.data.boundary_kml), type: 'property' })
      if (results[1].status === 'fulfilled') setStation(results[1].value.data.station)
      results.slice(2).forEach((result) => {
        if (result.status === 'fulfilled') next.push({ name: result.value.data.name, rings: parseReservoirKml(result.value.data.geometry_kml), type: 'reservoir' })
      })
      setLayers(next)
      setErrors(results.some((result) => result.status === 'rejected') ? ['Alguns dados do mapa não puderam ser carregados.'] : [])
      setLoading(false)
    })
    return () => { active = false }
  }, [property.id, reservoirs])
  const markers = useMemo(() => [
    ...meters.map((meter) => ({ id: `meter-${meter.id}`, name: meter.name, type: meter.kind === 'entrada' ? 'Entrada' : 'Saída', position: propertyCoordinates(meter), color: meter.kind === 'entrada' ? '#08786e' : '#cc7c3d' })),
    ...(station ? [{ id: 'station', name: station.name, type: 'Estação meteorológica', position: propertyCoordinates(station), color: '#527ec3' }] : []),
  ].filter((marker) => marker.position), [meters, station])
  const points = useMemo(() => [...markers.map((marker) => marker.position), ...layers.flatMap((layer) => layer.rings.flat()), ...(propertyCoordinates(property) ? [propertyCoordinates(property)] : [])], [markers, layers, property])
  const missingMeters = meters.filter((meter) => !propertyCoordinates(meter)).length
  return <section className="balance-map-card" aria-labelledby="balance-map-title">
    <div className="balance-map-heading"><div><p className="eyebrow">VISÃO DA ÁREA</p><h3 id="balance-map-title">Mapa de monitoramento</h3><p>Perímetros e equipamentos com localização cadastrada.</p></div><span className="balance-map-count"><MapPin size={15} /> {markers.length} pontos</span></div>
    {loading ? <p className="balance-map-placeholder">Carregando mapa…</p> : points.length ? <div className="balance-map-canvas"><MapContainer center={points[0]} zoom={13} scrollWheelZoom={false} style={{ height: '100%', width: '100%' }}><TileLayer url={tiles} attribution="&copy; OpenStreetMap contributors" /><FitMap points={points} />{layers.flatMap((layer, index) => layer.rings.map((ring, r) => <Polygon key={`${index}-${r}`} positions={ring} pathOptions={{ color: layer.type === 'property' ? '#277c6e' : '#148eae', weight: 2, dashArray: '7 7', fillOpacity: .08 }}><Popup>{layer.name} · perímetro cadastrado</Popup></Polygon>))}{markers.map((marker) => <CircleMarker key={marker.id} center={marker.position} radius={8} pathOptions={{ color: '#fff', weight: 3, fillColor: marker.color, fillOpacity: 1 }}><Popup><strong>{marker.name}</strong><br />{marker.type}</Popup></CircleMarker>)}</MapContainer></div> : <div className="balance-map-placeholder"><Waves size={22} /><strong>Seu mapa começa com uma localização</strong><span>Cadastre coordenadas ou o perímetro para visualizar a área.</span></div>}
    <div className="balance-map-footer"><div className="balance-map-legend"><span><i className="entry" />Entrada</span><span><i className="exit" />Saída</span><span><i className="rain" />Estação meteorológica</span><span><i className="perimeter" />Perímetro</span></div>{metersError && <p role="alert">Não foi possível carregar os hidrômetros.</p>}{reservoirsError && <p role="alert">Não foi possível carregar os reservatórios.</p>}{missingMeters > 0 && <p>{missingMeters} hidrômetro(s) sem coordenadas.</p>}{errors.map((message) => <p role="alert" key={message}>{message}</p>)}</div>
  </section>
}
