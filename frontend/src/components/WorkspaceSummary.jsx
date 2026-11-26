import { Bell, Building2, FileText, Gauge, MapPin, MapPinOff, Waves } from 'lucide-react'
import { propertyCoordinates } from '../map/mapUtils'

const sourceLabel = (source) => ({ manual: 'manual', simulada: 'simulado', dispositivo: 'dispositivo', imagem_revisada: 'imagem revisada' })[source] || source || 'origem não informada'
const formatDate = (value) => { const date = new Date(value); return Number.isFinite(date.getTime()) ? date.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' }) : 'Horário indisponível' }

export default function WorkspaceSummary({ properties, selectedProperty, loading, error, dashboard, meters, outorgas, alerts, latestActivity, onNavigate }) {
  const ready = Boolean(selectedProperty && !loading && !error)
  const located = properties.filter((property) => propertyCoordinates(property)).length
  const metrics = [
    { label: 'Reservatórios', Icon: Waves, count: dashboard?.reservoirs?.length, target: 'Estação / nível' },
    { label: 'Hidrômetros', Icon: Gauge, count: meters?.length, target: 'Hidrômetros' },
    { label: 'Outorgas', Icon: FileText, count: outorgas?.length, target: 'Outorga' },
    { label: 'Alertas abertos', Icon: Bell, count: alerts?.length, target: 'Alertas', limited: alerts?.length >= 50 },
  ]
  const status = !selectedProperty ? 'Selecione uma propriedade' : error ? 'Dados indisponíveis' : loading ? 'Carregando dados…' : 'Na propriedade selecionada'
  return <div className="workspace-stat-strip" aria-label="Resumo das propriedades e da operação">
    <div className="workspace-stat-card workspace-stat-property"><span className="workspace-stat-label">Propriedades</span><strong>{properties.length}</strong><small>no seu espaço</small><span className="workspace-stat-icon" aria-hidden="true"><Building2 size={18} strokeWidth={1.8} /></span></div>
    <div className="workspace-stat-card workspace-stat-property"><span className="workspace-stat-label">Com localização</span><strong>{located}</strong><small>disponíveis no mapa</small><span className="workspace-stat-icon" aria-hidden="true"><MapPin size={18} strokeWidth={1.8} /></span></div>
    <div className="workspace-stat-card workspace-stat-property"><span className="workspace-stat-label">Localização pendente</span><strong>{properties.length - located}</strong><small>acessíveis pela lista</small><span className="workspace-stat-icon" aria-hidden="true"><MapPinOff size={18} strokeWidth={1.8} /></span></div>
    <div className="workspace-stat-context"><div><span>Última medição</span>{!selectedProperty ? <b>Selecione uma propriedade</b> : error ? <b>Dados indisponíveis</b> : loading ? <b>Carregando…</b> : latestActivity ? <><b>{latestActivity.label} · {latestActivity.value}</b><small>{formatDate(latestActivity.observedAt)} · {sourceLabel(latestActivity.source)}</small></> : <b>Ainda não há medições</b>}</div></div>
    {metrics.map(({ label, Icon, count, target, limited }) => <button type="button" className="workspace-stat-card workspace-stat-metric" key={label} disabled={!ready} onClick={() => onNavigate(target)}><span className="workspace-stat-label">{label}</span><strong>{ready ? (count ?? '—') : '—'}</strong><small>{ready && count == null ? 'Falha ao carregar' : ready && limited ? 'Primeira página; pode haver mais' : status}</small><span className="workspace-stat-icon" aria-hidden="true"><Icon size={18} strokeWidth={1.8} /></span></button>)}
  </div>
}
