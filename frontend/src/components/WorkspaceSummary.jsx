import { Bell, FileText, Gauge, Waves } from 'lucide-react'
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
    { label: 'Alertas abertos', Icon: Bell, count: alerts?.length, target: 'Alertas' },
  ]
  const status = !selectedProperty ? 'Selecione uma propriedade' : error ? 'Dados indisponíveis' : loading ? 'Carregando dados…' : 'Na propriedade selecionada'
  return <div className="workspace-stat-strip" aria-label="Resumo das propriedades e da operação">
    <div><span>Propriedades</span><strong>{properties.length}</strong><small>no seu espaço</small></div>
    <div><span>Com localização</span><strong>{located}</strong><small>disponíveis no mapa</small></div>
    <div><span>Localização pendente</span><strong>{properties.length - located}</strong><small>acessíveis pela lista</small></div>
    <div className="workspace-stat-context"><div><span>Última medição</span>{!selectedProperty ? <b>Selecione uma propriedade</b> : error ? <b>Dados indisponíveis</b> : loading ? <b>Carregando…</b> : latestActivity ? <><b>{latestActivity.label} · {latestActivity.value}</b><small>{formatDate(latestActivity.observedAt)} · {sourceLabel(latestActivity.source)}</small></> : <b>Ainda não há medições</b>}</div></div>
    {metrics.map(({ label, Icon, count, target }) => <button type="button" className="workspace-stat-metric" key={label} disabled={!ready} onClick={() => onNavigate(target)}><span><Icon size={16} aria-hidden="true" />{label}</span><strong>{ready ? (count ?? '—') : '—'}</strong><small>{status}</small></button>)}
  </div>
}
