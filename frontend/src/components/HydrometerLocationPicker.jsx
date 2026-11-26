import { useState } from 'react'
import { CircleMarker, MapContainer, TileLayer, useMapEvents } from 'react-leaflet'
import { propertyCoordinates } from '../map/mapUtils'
import 'leaflet/dist/leaflet.css'

function Picker({ onPick }) {
  useMapEvents({ click: ({ latlng }) => onPick(latlng.lat.toFixed(6), latlng.lng.toFixed(6)) })
  return null
}

export default function HydrometerLocationPicker({ property }) {
  const [latitude, setLatitude] = useState('')
  const [longitude, setLongitude] = useState('')
  const position = propertyCoordinates({ latitude, longitude })
  const center = propertyCoordinates(property) || [-14.235, -51.925]
  return <div className="meter-location"><div><strong>Localização no mapa</strong><p>Clique no mapa ou informe as coordenadas. Você pode adicionar a localização depois.</p></div><div className="form-grid"><label className="field"><span>Latitude</span><input name="latitude" type="number" min="-90" max="90" step="0.000001" value={latitude} onChange={(event) => setLatitude(event.target.value)} placeholder="Ex.: -18.710962" /></label><label className="field"><span>Longitude</span><input name="longitude" type="number" min="-180" max="180" step="0.000001" value={longitude} onChange={(event) => setLongitude(event.target.value)} placeholder="Ex.: -47.473267" /></label></div><div className="meter-location-map"><MapContainer center={center} zoom={propertyCoordinates(property) ? 13 : 4} scrollWheelZoom={false} style={{ height: '100%', width: '100%' }}><TileLayer url={import.meta.env.VITE_OSM_TILE_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'} attribution="&copy; OpenStreetMap contributors" /><Picker onPick={(lat, lng) => { setLatitude(lat); setLongitude(lng) }} />{position && <CircleMarker center={position} radius={8} pathOptions={{ color: '#fff', weight: 3, fillColor: '#08786e', fillOpacity: 1 }} />}</MapContainer></div></div>
}
