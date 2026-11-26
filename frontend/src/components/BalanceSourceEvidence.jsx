import { useCallback, useEffect, useState } from 'react'
import { Check, CloudRain, RefreshCw, Waves } from 'lucide-react'
import { waterService } from '../services/triton'
import { IntegrationField, IntegrationNotice } from './IntegrationUI'

const toLocalInput = (value) => {
  const date = new Date(value)
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset())
  return date.toISOString().slice(0, 16)
}
const toUtc = (value) => new Date(value).toISOString()
const fmt = (value) => value ? new Date(value).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' }) : 'Horário não informado'

function EvidenceRows({ rows, kind, notes, setNotes, onReview, busy }) {
  if (!rows?.length) return <p className="integration-source-empty">Nenhum registro neste período.</p>
  return <ul className="integration-source-list">{rows.map((row) => { const noteKey = `${kind}-${row.id}`; const reviewed = row.quality === 'validada' || row.quality?.startsWith('revisada'); return <li key={noteKey}>
    <div className="integration-source-detail"><strong>{row.level_m ?? row.value} {row.level_m != null ? 'm' : row.unit}</strong><span>{row.period_start_at ? `${fmt(row.period_start_at)} — ${fmt(row.period_end_at)}` : `Observado ${fmt(row.observed_at)}`}</span><small>{row.source}{row.reference ? ` · ${row.reference}` : row.image_review_id ? ` · imagem revisada #${row.image_review_id}` : ''}</small></div>
    <div className="integration-source-review"><span className={reviewed ? 'is-reviewed' : 'is-pending'}>{row.quality}</span>
      {row.quality !== 'validada' && !row.quality?.startsWith('revisada') && <form onSubmit={(event) => { event.preventDefault(); onReview(kind, row, true) }}>
        <input aria-label={`Justificativa da revisão ${row.id}`} value={notes[noteKey] || ''} onChange={(event) => setNotes((old) => ({ ...old, [noteKey]: event.target.value }))} placeholder="Como conferiu este registro?" required />
        <button className="button secondary" disabled={busy || !notes[noteKey]?.trim()}><Check size={14} />Revisar</button>
      </form>}
    </div>
  </li>})}</ul>
}

export default function BalanceSourceEvidence({ propertyId, period, onUpdated }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [notes, setNotes] = useState({})
  const [page, setPage] = useState(0)

  const load = useCallback(async () => {
    if (!period) return
    setLoading(true)
    try {
      const [year, month] = period.period_start.split('-').map(Number)
      const { data: response } = await waterService.balanceSourceEvidence(period.reservoir_id, year, month, { skip: page * 50, limit: 50 })
      setData(response); setError('')
    } catch (e) { setError(e.response?.data?.detail || 'Não foi possível carregar as evidências deste período.') }
    finally { setLoading(false) }
  }, [period, page])

  useEffect(() => { setData(null); setNotes({}); load() }, [load])

  async function create(event, kind) {
    event.preventDefault(); setBusy(true); setError(''); setNotice('')
    const formElement = event.currentTarget
    const form = new FormData(formElement)
    const interval = { period_start_at: toUtc(form.get('period_start_at')), period_end_at: toUtc(form.get('period_end_at')) }
    try {
      if (kind === 'rainfall') {
        await waterService.createRainfallInterval(propertyId, { station_id: Number(form.get('station_id')),
          value_mm: form.get('value'), source: form.get('source'), reference: form.get('reference'), ...interval })
      } else {
        await waterService.createOtherOutflow(period.reservoir_id, { value_m3: form.get('value'),
          source: form.get('source'), reference: form.get('reference'), ...interval })
      }
      setNotice('Evidência registrada e aguardando revisão.'); formElement.reset(); await load()
      if (onUpdated) await onUpdated()
    } catch (e) { setError(e.response?.data?.detail || 'Não foi possível registrar a evidência.') }
    finally { setBusy(false) }
  }

  async function review(kind, row, approved) {
    const note = notes[row.id]?.trim()
    if (!note) return
    setBusy(true); setError(''); setNotice('')
    try {
      const data = { approved, note }
      if (kind === 'rainfall') await waterService.reviewRainfall(row.id, data)
      else if (kind === 'level') await waterService.reviewLevelReading(row.id, data)
      else await waterService.reviewOtherOutflow(row.id, data)
      setNotes((old) => ({ ...old, [`${kind}-${row.id}`]: '' })); setNotice('Revisão registrada no histórico.'); await load()
      if (onUpdated) await onUpdated()
    } catch (e) { setError(e.response?.data?.detail || 'Não foi possível revisar o registro.') }
    finally { setBusy(false) }
  }

  if (!period) return null
  const start = toLocalInput(period.period_start_utc)
  const end = toLocalInput(period.period_end_utc_exclusive)
  const stations = data?.stations || []
  const hasMore = data?.rainfall?.has_more || data?.other_outflows?.has_more || data?.levels?.has_more
  const rowCount = Math.max(data?.rainfall?.items?.length || 0, data?.other_outflows?.items?.length || 0, data?.levels?.items?.length || 0)
  return <section className="integration-source-workspace" aria-label="Evidências de chuva e outras saídas">
    <header><div><h4>Chuva e outras saídas</h4><p>Registre intervalos e revise as referências antes do balanço.</p></div><button type="button" className="integration-icon-button" onClick={load} aria-label="Atualizar evidências" disabled={loading}><RefreshCw size={15} /></button></header>
    {error && <IntegrationNotice type="error">{error}</IntegrationNotice>}
    {notice && <IntegrationNotice type="success">{notice}</IntegrationNotice>}
    {loading ? <p className="integration-source-empty">Carregando registros…</p> : <>
      <div className="integration-source-columns">
        <details className="integration-subpanel"><summary><CloudRain size={17} /><span>Precipitação</span><small>{data?.rainfall?.items?.length || 0} registros</small></summary><div className="integration-source-body">
          {stations.length ? <form className="integration-source-form" onSubmit={(event) => create(event, 'rainfall')}>
            <IntegrationField label="Estação"><select name="station_id" required defaultValue={stations.length === 1 ? String(stations[0].id) : ''}><option value="">Selecione a estação</option>{stations.map((station) => <option key={station.id} value={station.id}>{station.name} · {station.station_code}</option>)}</select></IntegrationField>
            <div className="integration-source-form-grid"><IntegrationField label="Chuva acumulada (mm)"><input name="value" type="number" min="0" step="any" required /></IntegrationField><IntegrationField label="Origem"><select name="source"><option value="manual">Manual</option><option value="medida">Medição</option></select></IntegrationField></div>
            <div className="integration-source-form-grid"><IntegrationField label="Início observado"><input name="period_start_at" type="datetime-local" defaultValue={start} required /></IntegrationField><IntegrationField label="Fim observado"><input name="period_end_at" type="datetime-local" defaultValue={end} required /></IntegrationField></div>
            <IntegrationField label="Referência"><input name="reference" maxLength="255" placeholder="Caderno, pluviômetro ou documento" required /></IntegrationField><button className="button primary" disabled={busy}>Registrar chuva</button>
          </form> : <p className="integration-source-empty">Associe uma estação meteorológica à propriedade antes de registrar precipitação.</p>}
          <EvidenceRows rows={data?.rainfall?.items} kind="rainfall" notes={notes} setNotes={setNotes} onReview={review} busy={busy} />
        </div></details>
        <details className="integration-subpanel"><summary><Waves size={17} /><span>Outras saídas quantificadas</span><small>{data?.other_outflows?.items?.length || 0} registros</small></summary><div className="integration-source-body">
          <form className="integration-source-form" onSubmit={(event) => create(event, 'outflow')}>
            <div className="integration-source-form-grid"><IntegrationField label="Volume (m³)"><input name="value" type="number" min="0" step="0.001" required /></IntegrationField><IntegrationField label="Origem"><select name="source"><option value="manual">Manual</option><option value="medida">Medição</option><option value="documento">Documento</option></select></IntegrationField></div>
            <div className="integration-source-form-grid"><IntegrationField label="Início do intervalo"><input name="period_start_at" type="datetime-local" defaultValue={start} required /></IntegrationField><IntegrationField label="Fim do intervalo"><input name="period_end_at" type="datetime-local" defaultValue={end} required /></IntegrationField></div>
            <IntegrationField label="Referência"><input name="reference" maxLength="255" placeholder="Documento ou registro de campo" required /></IntegrationField><button className="button primary" disabled={busy}>Registrar saída</button>
          </form>
          <EvidenceRows rows={data?.other_outflows?.items} kind="outflow" notes={notes} setNotes={setNotes} onReview={review} busy={busy} />
        </div></details>
        <details className="integration-subpanel"><summary><Waves size={17} /><span>Leituras de nível</span><small>{data?.levels?.items?.length || 0} registros</small></summary><div className="integration-source-body">
          <p className="integration-source-help">Somente uma leitura revisada exatamente no início e no fim do mês permite converter nível em volume pela curva aprovada.</p>
          <EvidenceRows rows={data?.levels?.items} kind="level" notes={notes} setNotes={setNotes} onReview={review} busy={busy} />
        </div></details>
      </div>
      {(page > 0 || hasMore) && <div className="integration-pagination"><span>Página {page + 1} · {rowCount} registros por tipo{hasMore ? ' · há mais' : ''}</span><div><button type="button" className="integration-page-button" disabled={page === 0 || loading} onClick={() => setPage((value) => value - 1)}>Anterior</button><button type="button" className="integration-page-button" disabled={!hasMore || loading} onClick={() => setPage((value) => value + 1)}>Próxima</button></div></div>}
    </>}
  </section>
}
