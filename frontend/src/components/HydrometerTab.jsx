import { lazy, Suspense, useRef, useState } from 'react'
import { Gauge, Plus, Search } from 'lucide-react'
import MonitoringEmptyState from './MonitoringEmptyState'
import RowActions from './RowActions'
import RecordManagement from './RecordManagement'
import HydrometerOutorgaLinks from './HydrometerOutorgaLinks'
import HydrometerReadingReview from './HydrometerReadingReview'
const HydrometerLocationPicker = lazy(() => import('./HydrometerLocationPicker'))

const number = (value, digits = 1) => value == null ? '—' : Number(value).toLocaleString('pt-BR', { maximumFractionDigits: digits })
const localDateTime = () => { const date = new Date(); date.setMinutes(date.getMinutes() - date.getTimezoneOffset()); return date.toISOString().slice(0, 16) }

function Field({ label, children }) {
  return <label className="field"><span>{label}</span>{children}</label>
}

export default function HydrometerTab({ property, meters, outorgas, dashboard, busy, onAddReservoir, onCreateMeter, onRead, onUpdated }) {
  const reservoirs = dashboard?.reservoirs || []
  const formRef = useRef(null)
  const readRef = useRef(null)
  const editorRef = useRef(null)
  const linkRef = useRef(null)
  const reviewRef = useRef(null)
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const [panel, setPanel] = useState(null)
  const [readingId, setReadingId] = useState('')
  const [editingMeterId, setEditingMeterId] = useState(null)
  const [linkingMeterId, setLinkingMeterId] = useState(null)
  const [reviewingReadingId, setReviewingReadingId] = useState(null)
  const editingMeter = meters.find((meter) => meter.id === editingMeterId)
  const linkingMeter = meters.find((meter) => meter.id === linkingMeterId)
  const reviewingItem = (dashboard?.recent_hydrometers || []).flatMap((item) => item.readings.map((reading) => ({ meter: item.hydrometer, reading }))).find((item) => item.reading.id === reviewingReadingId)
  const openEditor = (id) => { setEditingMeterId(id); window.requestAnimationFrame(() => editorRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })) }
  const openLinks = (id) => { setLinkingMeterId(id); window.requestAnimationFrame(() => linkRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })) }
  const openReadingReview = (id) => { setReviewingReadingId(id); window.requestAnimationFrame(() => reviewRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })) }
  const normalize = (value) => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
  const filtered = meters.filter((meter) => normalize(`${meter.name} ${reservoirs.find((r) => r.id === meter.reservoir_id)?.name || ''}`).includes(normalize(query)))
  const pages = Math.max(1, Math.ceil(filtered.length / 10))
  const current = Math.min(page, pages)
  const visible = filtered.slice((current - 1) * 10, current * 10)
  const openForm = (kind = 'create', meterId = null) => { if (panel === kind && meters.length && meterId == null) { setPanel(null); return } if (kind === 'read') setReadingId(String(meterId || meters[0]?.id || '')); setPanel(kind); window.requestAnimationFrame(() => { const ref = kind === 'read' ? readRef : formRef; ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }); ref.current?.querySelector('input, select')?.focus({ preventScroll: true }) }) }
  return <div className="monitor-page hydrometer-page">
    <header className="monitor-heading"><div><p className="eyebrow">MONITORAMENTO</p><h2>Hidrômetros</h2><p>Acompanhe os equipamentos de entrada e saída e registre suas leituras.</p></div><div className="level-heading-actions">{meters.length > 0 && <><button type="button" className="button secondary" aria-expanded={panel === 'read'} onClick={() => openForm('read')}>Registrar leitura</button><button type="button" className="button secondary" aria-expanded={panel === 'create'} onClick={() => openForm('create')}><Plus size={16} aria-hidden="true" />Cadastrar hidrômetro</button></>}</div></header>
    {reservoirs.length > 0 && panel && <div className="two-column form-columns hydrometer-forms">
      {panel === 'create' && <form ref={formRef} className="form-card" onSubmit={onCreateMeter}><h3>Novo hidrômetro</h3><Field label="Nome"><input name="name" required /></Field><Field label="Reservatório"><select name="reservoir_id">{reservoirs.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Field><Field label="Tipo"><select name="kind"><option value="entrada">Entrada / captação</option><option value="saída">Saída</option></select></Field><div className="form-grid"><Field label="Potência elétrica kW"><input name="rated_power_kw" type="number" min="0.001" step="0.001" /></Field><Field label="Potência mecânica CV"><input name="rated_power_cv" type="number" min="0.001" step="0.001" /></Field></div><small>Preencha uma potência, no máximo. CV não é potência elétrica.</small><Suspense fallback={<p>Carregando mapa...</p>}><HydrometerLocationPicker property={property} /></Suspense><div className="form-actions"><button type="button" className="button secondary" disabled={busy} onClick={() => setPanel(null)}>Cancelar</button><button className="button primary" disabled={busy}>Cadastrar hidrômetro</button></div></form>}
      {panel === 'read' && meters.length > 0 && <form ref={readRef} className="form-card" onSubmit={onRead}><h3>Registrar leitura</h3><Field label="Hidrômetro"><select name="hydrometer_id" value={readingId} onChange={(event) => setReadingId(event.target.value)}>{meters.map((meter) => <option value={meter.id} key={meter.id}>{meter.name} · {meter.kind}</option>)}</select></Field><div className="form-grid"><Field label="Volume do intervalo (m³)"><input type="number" name="volume_m3" min="0" step="0.001" required /></Field><Field label="Vazão média (m³/h)"><input type="number" name="flow_m3_h" min="0" step="0.001" /></Field></div><Field label="Início do intervalo medido"><input type="datetime-local" name="interval_start_at" required /></Field><Field label="Data e hora observadas"><input type="datetime-local" name="observed_at" defaultValue={localDateTime()} required /></Field><Field label="Origem"><select name="source"><option value="manual">Manual</option><option value="simulada">Simulada</option></select></Field><div className="form-actions"><button type="button" className="button secondary" disabled={busy} onClick={() => setPanel(null)}>Cancelar</button><button className="button primary" disabled={busy}>Salvar leitura</button></div></form>}
    </div>}
    {meters.length ? <section className="hydrometer-overview"><div className="monitor-section-heading level-list-heading"><div><h3>Equipamentos cadastrados</h3><p>Vínculos e última leitura disponível de cada hidrômetro.</p></div><label className="level-search"><Search size={16} aria-hidden="true" /><span className="sr-only">Buscar hidrômetro</span><input value={query} onChange={(event) => { setQuery(event.target.value); setPage(1) }} placeholder="Buscar hidrômetro ou reservatório" /></label></div><div className="table-wrap equipment-table-wrap"><table className="responsive-equipment-table"><thead><tr><th>Equipamento</th><th>Tipo</th><th>Outorga</th><th>Potência</th><th>Última leitura</th><th>Ações</th></tr></thead><tbody>{visible.map((meter) => {
      const entry = dashboard?.recent_hydrometers?.find((item) => item.hydrometer.id === meter.id)?.readings?.[0]
      const reservoir = reservoirs.find((item) => item.id === meter.reservoir_id)
      return <tr key={meter.id}><td data-label="Equipamento"><b>{meter.name}</b><small>{reservoir?.name || `Reservatório #${meter.reservoir_id}`}</small></td><td data-label="Tipo">{meter.kind}</td><td data-label="Outorga">{meter.kind === 'saída' ? 'Não aplicável' : meter.outorga_id ? (outorgas.find((item) => item.id === meter.outorga_id)?.name || 'Cadastro atual') : 'Sem cadastro atual'}</td><td data-label="Potência">{meter.rated_power_kw ? `${number(meter.rated_power_kw)} kW elétricos` : meter.rated_power_cv ? `${number(meter.rated_power_cv)} CV mecânicos` : 'Não informada'}</td><td data-label="Última leitura">{entry ? `${entry.volume_m3 == null ? 'Volume indisponível' : `${number(entry.volume_m3)} m³`} · ${entry.source}` : 'Sem leitura'}</td><td className="equipment-actions"><RowActions name={meter.name} actions={[{ label: 'Registrar leitura', onClick: () => openForm('read', meter.id) }, ...(meter.kind === 'saída' ? [] : [{ label: 'Gerenciar vigência da outorga', onClick: () => openLinks(meter.id) }]), ...(entry?.volume_m3 != null && entry?.interval_start_at && entry?.quality !== 'validada' ? [{ label: 'Revisar última leitura', onClick: () => openReadingReview(entry.id) }] : []), { label: 'Editar e consultar histórico', onClick: () => openEditor(meter.id) }]} /></td></tr>
    })}</tbody></table>{!visible.length && <p className="level-no-results">Nenhum hidrômetro encontrado para essa busca.</p>}</div><div className="level-pagination"><span>{filtered.length} {filtered.length === 1 ? 'hidrômetro' : 'hidrômetros'} · página {current} de {pages}</span><div><button type="button" className="small-button" disabled={current <= 1} onClick={() => setPage(current - 1)}>Anterior</button><button type="button" className="small-button" disabled={current >= pages} onClick={() => setPage(current + 1)}>Próxima</button></div></div></section> : <MonitoringEmptyState icon={Gauge} label="MEDIÇÃO DE VOLUME" title="Nenhum hidrômetro cadastrado" description={reservoirs.length ? "Adicione um equipamento para registrar e acompanhar os volumes de entrada e saída." : "Cadastre um reservatório para associar um hidrômetro e registrar leituras."} actionLabel={reservoirs.length ? "Cadastrar hidrômetro" : "Cadastrar reservatório"} onAction={reservoirs.length ? () => openForm('create') : onAddReservoir} />}

    {editingMeter && <details ref={editorRef} className="record-inline meter-inline" open><summary>Editar {editingMeter.name} e consultar histórico</summary><RecordManagement key={editingMeter.id} compact kind="hidrômetro" records={[editingMeter]} onUpdated={onUpdated || (() => Promise.resolve())} /></details>}
    {linkingMeter && <details ref={linkRef} className="record-inline meter-inline" open><summary>Vigência de outorga · {linkingMeter.name}</summary><HydrometerOutorgaLinks key={linkingMeter.id} meter={linkingMeter} outorgas={outorgas} onUpdated={onUpdated} /></details>}
    {reviewingItem && <div ref={reviewRef}><HydrometerReadingReview meter={reviewingItem.meter} reading={reviewingItem.reading} onCancel={() => setReviewingReadingId(null)} onComplete={async () => { setReviewingReadingId(null); if (onUpdated) await onUpdated() }} /></div>}
  </div>
}
