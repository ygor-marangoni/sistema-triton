import { useState } from 'react'
import { Archive, CircleCheck, Clock3, FilePenLine, Gauge, History, RotateCcw, Save } from 'lucide-react'
import { waterService } from '../services/triton'
import { IntegrationField, IntegrationHeader, IntegrationNotice, IntegrationPagination } from './IntegrationUI'

const permitFields = [
  ['name', 'Nome', 'text'], ['permit_number', 'Número da outorga', 'text'], ['issued_on', 'Emissão', 'date'],
  ['valid_from', 'Início da vigência', 'date'], ['valid_until', 'Fim da vigência', 'date'], ['water_body', 'Corpo hídrico', 'text'],
  ['municipality', 'Município', 'text'], ['coordinates_gms', 'Coordenadas', 'text'], ['state', 'UF', 'text'], ['irrigated_area_ha', 'Área irrigada (ha)', 'number'],
]
const meterFields = [['name', 'Nome', 'text'], ['rated_power_kw', 'Potência elétrica (kW)', 'number'], ['rated_power_cv', 'Potência mecânica (CV)', 'number'], ['latitude', 'Latitude', 'number'], ['longitude', 'Longitude', 'number']]
const actions = { create: 'Cadastro criado', edit: 'Dados atualizados', state: 'Estado alterado', link: 'Vínculo alterado' }
const eventLabels = { reinicio: 'Reinício', troca: 'Troca de equipamento', retorno: 'Retorno do totalizador' }
const dateTime = (value) => value ? new Date(value).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' }) : 'Data não informada'
const describe = (value) => value == null ? 'Não informado' : Array.isArray(value) ? `${value.length} itens` : typeof value === 'object' ? 'Dados registrados' : String(value)

export default function RecordManagement({ kind, records, onUpdated, compact = false }) {
  const [selectedId, setSelectedId] = useState(() => compact && records[0] ? String(records[0].id) : ''), [history, setHistory] = useState(null), [error, setError] = useState(''), [notice, setNotice] = useState('')
  const [events, setEvents] = useState(null), [historyPage, setHistoryPage] = useState(0), [eventPage, setEventPage] = useState(0), [busy, setBusy] = useState(false)
  const selected = records.find((record) => String(record.id) === selectedId), permit = kind === 'outorga'
  const labels = Object.fromEntries([...permitFields, ...meterFields].map(([key, label]) => [key, label]))
  labels.is_active = 'Ativo'; labels.outorga_id = 'Outorga vinculada'
  async function save(event) {
    event.preventDefault(); const form = new FormData(event.currentTarget); const fields = permit ? permitFields : meterFields
    const data = Object.fromEntries(fields.map(([key]) => [key, form.get(key) === '' ? null : form.get(key)])); setBusy(true)
    try { await (permit ? waterService.editPermit(selected.id, data) : waterService.editMeter(selected.id, data)); await onUpdated(); setNotice('Alteração registrada no histórico.'); setError('') } catch (e) { setError(e.response?.data?.detail || 'Não foi possível salvar.') } finally { setBusy(false) }
  }
  async function changeState() {
    setBusy(true)
    try { await (permit ? waterService.permitState(selected.id, !selected.is_active) : waterService.meterState(selected.id, !selected.is_active)); await onUpdated(); setNotice('Estado atualizado e registrado.'); setError('') } catch (e) { setError(e.response?.data?.detail || 'Não foi possível alterar o estado.') } finally { setBusy(false) }
  }
  async function loadHistory(page = 0) {
    try { const params = { skip: page * 50, limit: 50 }; const { data } = await (permit ? waterService.permitHistory(selected.id, params) : waterService.meterHistory(selected.id, params)); setHistory(data); setHistoryPage(page); setError('') } catch (e) { setError(e.response?.data?.detail || 'Não foi possível carregar o histórico.') }
  }
  async function loadEvents(page = 0) { try { const { data } = await waterService.meterEvents(selected.id, { skip: page * 50, limit: 50 }); setEvents(data); setEventPage(page); setError('') } catch (e) { setError(e.response?.data?.detail || 'Não foi possível carregar eventos.') } }
  async function saveEvent(event) {
    event.preventDefault(); const form = event.currentTarget; const values = new FormData(form); setBusy(true)
    try { await waterService.createMeterEvent(selected.id, { event_type: values.get('event_type'), observed_at: new Date(values.get('observed_at')).toISOString(), note: values.get('note') }); form.reset(); await loadEvents(); setNotice('Evento registrado; leituras não foram alteradas.') } catch (e) { setError(e.response?.data?.detail || 'Não foi possível registrar o evento.') } finally { setBusy(false) }
  }
  return <section className={`integration-panel record-management${compact ? ' integration-panel-compact' : ''}`}>{!compact && <IntegrationHeader title={permit ? 'Gerenciar outorgas' : 'Gerenciar hidrômetros'} description="Edite informações e acompanhe o histórico sem perder registros anteriores." />}
    {!compact && <div className="integration-selector"><IntegrationField label={permit ? 'Outorga' : 'Hidrômetro'}><select value={selectedId} onChange={(e) => { setSelectedId(e.target.value); setHistory(null); setEvents(null); setNotice(''); setError('') }}><option value="">Selecione um cadastro</option>{records.map((record) => <option key={record.id} value={record.id}>{record.name} · {record.is_active ? 'ativo' : 'inativo'}</option>)}</select></IntegrationField><p>Selecione um item para editar ou consultar seu histórico.</p></div>}
    <IntegrationNotice type="error">{typeof error === 'string' ? error : error ? 'Dados inválidos. Confira os campos.' : ''}</IntegrationNotice><IntegrationNotice type="success">{notice}</IntegrationNotice>
    {selected && typeof selected.is_active !== 'boolean' && <IntegrationNotice type="info">A edição com histórico exige a versão atual da API e a migração correspondente.</IntegrationNotice>}
    {selected && typeof selected.is_active === 'boolean' && <div className="integration-record">{!compact && <div className="integration-record-heading"><div><span className="integration-row-icon">{permit ? <FilePenLine size={18} /> : <Gauge size={18} />}</span><div><strong>{selected.name}</strong><small>{permit ? `Outorga ${selected.permit_number}` : `Hidrômetro de ${selected.kind}`}</small></div></div><span className={`integration-status ${selected.is_active ? 'is-success' : 'is-pending'}`}>{selected.is_active ? 'Ativo' : 'Inativo'}</span></div>}
      <form key={`${kind}-${selected.id}`} className="integration-review-form" onSubmit={save}><div className="integration-section-title"><div><h5>Informações do cadastro</h5><p>As alterações ficam registradas no histórico.</p></div></div><div className="integration-form-grid">{(permit ? permitFields : meterFields).map(([key, label, type]) => <IntegrationField key={key} label={label}><input name={key} type={type} step={type === 'number' ? (key === 'latitude' || key === 'longitude' ? '0.000001' : '0.001') : undefined} defaultValue={selected[key] ?? ''} required={permit || key === 'name'} /></IntegrationField>)}</div><div className="integration-form-actions"><span>{permit ? 'A vigência é protegida quando há leituras vinculadas.' : 'O vínculo é protegido após o registro de leituras.'}</span><div><button type="button" className="button secondary" onClick={changeState} disabled={busy}>{selected.is_active ? <Archive size={15} /> : <RotateCcw size={15} />}{selected.is_active ? 'Inativar' : 'Reativar'}</button><button className="button primary" disabled={busy}><Save size={15} />Salvar alterações</button></div></div></form>
      <details className="integration-history" onToggle={(e) => { if (e.currentTarget.open && history === null) loadHistory(0) }}><summary><History size={16} /> Histórico de alterações <span>Cadastro e estados</span></summary>{history === null ? <p>Carregando histórico…</p> : <>{history.length ? <ol>{history.map((entry) => <li key={entry.id}><strong>{actions[entry.action] || entry.action}</strong><span>{dateTime(entry.created_at)} · usuário {entry.user_id}</span><details><summary>Ver valores</summary><dl className="integration-history-values">{Object.keys({ ...entry.previous_values, ...entry.new_values }).map((key) => <div key={key}><dt>{labels[key] || key}</dt><dd>{describe(entry.previous_values[key])} → {describe(entry.new_values[key])}</dd></div>)}</dl></details></li>)}</ol> : <p>Nenhuma alteração nesta página.</p>}<IntegrationPagination page={historyPage} count={history.length} size={50} onPage={loadHistory} /></>}</details>
      {!permit && <details className="integration-history" onToggle={(e) => { if (e.currentTarget.open && events === null) loadEvents(0) }}><summary><Clock3 size={16} /> Eventos do totalizador <span>Reinício, troca ou retorno</span></summary><p>O evento fica registrado, sem corrigir ou recalcular leituras anteriores.</p><form className="integration-event-form" onSubmit={saveEvent}><div className="integration-form-grid three"><IntegrationField label="Tipo de evento"><select name="event_type"><option value="reinicio">Reinício</option><option value="troca">Troca de equipamento</option><option value="retorno">Retorno do totalizador</option></select></IntegrationField><IntegrationField label="Horário observado"><input type="datetime-local" name="observed_at" required /></IntegrationField><IntegrationField label="Evidência ou observação"><input name="note" placeholder="Descreva o ocorrido" required maxLength="2000" /></IntegrationField></div><button className="button secondary" disabled={busy}><CircleCheck size={15} />Registrar evento</button></form>{events === null ? <p>Carregando eventos…</p> : <>{events.length ? <ol>{events.map((item) => <li key={item.id}><strong>{eventLabels[item.event_type] || item.event_type}</strong><span>{dateTime(item.observed_at)} · usuário {item.user_id}</span><p>{item.note}</p></li>)}</ol> : <p>Nenhum evento nesta página.</p>}<IntegrationPagination page={eventPage} count={events.length} size={50} onPage={loadEvents} /></>}</details>}
    </div>}
  </section>
}
