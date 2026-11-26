import { useEffect, useRef, useState } from 'react'
import { ArrowRight, ChartNoAxesCombined, Check, ChevronDown, Database, Plus, Ruler } from 'lucide-react'
import { waterService } from '../services/triton'
import { IntegrationEmpty, IntegrationField, IntegrationHeader, IntegrationNotice, IntegrationPagination } from './IntegrationUI'

const number = (value) => Number(value).toLocaleString('pt-BR', { maximumFractionDigits: 3 })

function CurvePreview({ curve }) {
  const points = curve.points.map((point) => ({ x: Number(point.level), y: Number(point.volume) }))
  const minX = points[0].x, maxX = points.at(-1).x, maxY = Math.max(1, ...points.map((point) => point.y))
  const coords = points.map((point) => ({ ...point, px: 34 + (point.x - minX) / (maxX - minX) * 420, py: 122 - point.y / maxY * 102 }))
  return <div className="integration-curve-preview"><div className="integration-chart-heading"><div><strong>Relação cadastrada</strong><span>Interpolação linear entre pontos · m / m³</span></div><span>{points.length} pontos</span></div><svg viewBox="0 0 480 150" role="img" aria-label={`Curva do levantamento: ${points.map((point) => `${number(point.x)} metros, ${number(point.y)} metros cúbicos`).join('; ')}`} preserveAspectRatio="none"><line x1="34" y1="20" x2="454" y2="20" className="integration-chart-grid" /><line x1="34" y1="71" x2="454" y2="71" className="integration-chart-grid" /><line x1="34" y1="122" x2="454" y2="122" className="integration-chart-grid" /><polyline points={coords.map((point) => `${point.px},${point.py}`).join(' ')} className="integration-chart-line" />{coords.map((point, index) => <circle key={index} cx={point.px} cy={point.py} r="3.5" className="integration-chart-point" />)}</svg><div className="integration-chart-axis"><span>{number(minX)} m</span><span>COTA · FAIXA DO LEVANTAMENTO</span><span>{number(maxX)} m</span></div><div className="integration-point-list">{points.map((point, index) => <span key={index}><b>{number(point.x)} m</b> <ArrowRight size={12} aria-hidden="true" /> {number(point.y)} m³</span>)}</div></div>
}

export default function StageCurves({ reservoirs }) {
  const [reservoirId, setReservoirId] = useState(''), [curves, setCurves] = useState([]), [error, setError] = useState(''), [notice, setNotice] = useState(''), [page, setPage] = useState(0)
  const [level, setLevel] = useState(''), [curveDate, setCurveDate] = useState(''), [volume, setVolume] = useState(null), [selectedCurve, setSelectedCurve] = useState(''), [previewId, setPreviewId] = useState(null), [loading, setLoading] = useState(false), [busy, setBusy] = useState(false)
  const request = useRef(0)
  const approvedCurves = curves.filter((curve) => curve.is_approved)

  async function load(id, currentPage) {
    const version = ++request.current
    if (!id) { setCurves([]); setLoading(false); return }
    setLoading(true)
    try {
      const { data } = await waterService.curves(id, { skip: currentPage * 20, limit: 20 })
      if (version === request.current) { setCurves(data); setError('') }
    } catch (e) {
      if (version === request.current) { setCurves([]); setError(e.response?.data?.detail || 'Erro ao carregar os levantamentos.') }
    } finally { if (version === request.current) setLoading(false) }
  }
  useEffect(() => { load(reservoirId, page) }, [reservoirId, page])

  async function submit(event) {
    event.preventDefault()
    const form = event.currentTarget
    const values = new FormData(form)
    setBusy(true)
    try {
      const points = String(values.get('points')).split('\n').filter((line) => line.trim()).map((line) => {
        const parts = line.split(';').map((value) => value.trim().replace(',', '.'))
        if (parts.length !== 2 || parts.some((value) => value === '' || !Number.isFinite(Number(value)))) throw new Error('Informe cada ponto como cota;volume, um por linha.')
        return { level: parts[0], volume: parts[1] }
      })
      await waterService.createCurve(reservoirId, { survey_date: values.get('survey_date'), survey_source: values.get('survey_source'), survey_responsible: values.get('survey_responsible'), level_unit: 'm', volume_unit: 'm3', points })
      form.reset(); setPage(0); await load(reservoirId, 0); setNotice('Levantamento cadastrado e aguardando aprovação.')
    } catch (e) { setError(typeof e.response?.data?.detail === 'string' ? e.response.data.detail : e.message || 'Não foi possível cadastrar o levantamento.') } finally { setBusy(false) }
  }

  async function approve(event, curve) {
    event.preventDefault()
    const values = new FormData(event.currentTarget)
    setBusy(true)
    try {
      await waterService.approveCurve(curve.id, { valid_from: values.get('valid_from'), valid_until: values.get('valid_until') })
      setNotice('Vigência da curva aprovada e registrada no histórico.')
      setError('')
      await load(reservoirId, page)
    } catch (e) { setError(e.response?.data?.detail || 'Não foi possível aprovar a curva.') } finally { setBusy(false) }
  }

  async function interpolate() {
    if (!selectedCurve || level === '') return
    try { const { data } = await waterService.curveVolume(selectedCurve, level, curveDate); setVolume(data); setError('') }
    catch (e) { setVolume(null); setError(e.response?.data?.detail || 'Não foi possível consultar o volume.') }
  }

  return <section className="integration-panel stage-curves">
    <IntegrationHeader icon={ChartNoAxesCombined} eyebrow="GEOMETRIA DO RESERVATÓRIO" title="Curvas cota–volume" description="Cadastre versões do levantamento e aprove a vigência antes de usá-las nos cálculos." />
    <div className="integration-selector"><IntegrationField label="Reservatório"><select value={reservoirId} onChange={(e) => { setReservoirId(e.target.value); setPage(0); setVolume(null); setPreviewId(null); setSelectedCurve(''); setNotice('') }}><option value="">Selecione um reservatório</option>{reservoirs.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</select></IntegrationField><p>Os pontos precisam vir de levantamento cota–volume; o perímetro KML não substitui essa curva.</p></div>
    {reservoirId && <>
      <details className="integration-disclosure"><summary><Plus size={16} /><span>Cadastrar levantamento<small>Adiciona uma versão sem alterar as anteriores</small></span><ChevronDown size={16} /></summary><form className="integration-disclosure-body" onSubmit={submit}>
        <div className="integration-form-grid three"><IntegrationField label="Data do levantamento"><input type="date" name="survey_date" required /></IntegrationField><IntegrationField label="Origem do levantamento"><input name="survey_source" placeholder="Documento ou levantamento" required /></IntegrationField><IntegrationField label="Responsável"><input name="survey_responsible" placeholder="Nome do responsável" required /></IntegrationField></div>
        <IntegrationField label="Pontos cota e volume" hint="Um por linha, em ordem crescente: cota em metros; volume em m³."><textarea name="points" rows={4} placeholder="cota; volume" required /></IntegrationField>
        <div className="integration-form-actions"><span>O cadastro aguarda aprovação e vigência antes do uso.</span><button className="button primary" disabled={busy}><Plus size={15} />Salvar levantamento</button></div>
      </form></details>
      <IntegrationNotice type="error">{error}</IntegrationNotice><IntegrationNotice type="success">{notice}</IntegrationNotice>
      <div className="integration-list-heading"><div><h4>Levantamentos</h4><p>Somente uma versão aprovada e vigente pode alimentar o balanço.</p></div></div>
      {loading ? <div className="integration-loading"><span className="spinner" />Carregando levantamentos…</div> : curves.length === 0 ? <IntegrationEmpty icon={Database} title="Nenhum levantamento nesta página">Cadastre os pontos do levantamento para iniciar a revisão.</IntegrationEmpty> : <>
        <div className="integration-list">{curves.map((curve) => <article className="integration-curve-item" key={curve.id}>
          <div className="integration-list-row"><span className="integration-row-icon"><ChartNoAxesCombined size={18} aria-hidden="true" /></span><div className="integration-row-main"><strong>Levantamento de {curve.survey_date.split('-').reverse().join('/')}</strong><small>{curve.survey_source} · {curve.survey_responsible}</small></div><span className={`integration-status${curve.is_approved ? ' is-approved' : ''}`}>{curve.is_approved ? 'Aprovada' : 'Aguardando aprovação'}</span><div className="integration-row-actions"><button type="button" className="integration-text-button" onClick={() => setPreviewId(previewId === curve.id ? null : curve.id)}>{previewId === curve.id ? 'Ocultar pontos' : 'Ver pontos'}</button></div></div>
          {curve.is_approved ? <p className="integration-curve-validity"><Check size={14} aria-hidden="true" /> Vigente de {curve.valid_from} a {curve.valid_until}</p> : <form className="integration-curve-approval" onSubmit={(event) => approve(event, curve)}><IntegrationField label="Vigência inicial"><input type="date" name="valid_from" defaultValue={curve.survey_date} required /></IntegrationField><IntegrationField label="Vigência final"><input type="date" name="valid_until" required /></IntegrationField><button type="submit" className="button secondary" disabled={busy}><Check size={15} />Aprovar período</button></form>}
          {previewId === curve.id && <CurvePreview curve={curve} />}
        </article>)}</div><IntegrationPagination page={page} count={curves.length} size={20} onPage={setPage} />
      </>}
      {approvedCurves.length > 0 && <div className="integration-query"><IntegrationField label="Curva aprovada"><select value={selectedCurve} onChange={(event) => { setSelectedCurve(event.target.value); setVolume(null) }}><option value="">Selecione uma versão vigente</option>{approvedCurves.map((curve) => <option value={curve.id} key={curve.id}>Levantamento de {curve.survey_date} · {curve.valid_from} a {curve.valid_until}</option>)}</select></IntegrationField><IntegrationField label="Data de referência"><input value={curveDate} onChange={(event) => setCurveDate(event.target.value)} type="date" /></IntegrationField><IntegrationField label="Nível para consulta" hint="A cota precisa estar dentro da faixa cadastrada."><div className="integration-input-suffix"><input value={level} onChange={(e) => setLevel(e.target.value)} type="number" min="0" step="0.001" placeholder="0,000" /><span>m</span></div></IntegrationField><button type="button" className="button secondary" disabled={!selectedCurve || !curveDate || level === ''} onClick={interpolate}>Consultar volume</button>{volume && <div className="integration-query-result"><span>VOLUME INTERPOLADO · CURVA {volume.curve_id}</span><strong>{number(volume.volume)} <small>m³</small></strong><em>Interpolação dentro da vigência e faixa levantada</em></div>}</div>}
    </>}
  </section>
}
