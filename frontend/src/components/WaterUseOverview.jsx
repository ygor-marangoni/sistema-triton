import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, FileText, Waves } from 'lucide-react'
import GrantDashboard from './GrantDashboard'
import { waterService } from '../services/triton'

const months = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
const fmt = (value) => Number(value).toLocaleString('pt-BR', { maximumFractionDigits: 1 })
const date = (value) => value ? value.split('-').reverse().join('/') : 'Não informada'

function DailyAvailability({ comparison }) {
  const parts = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Sao_Paulo', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date())
  const get = (type) => parts.find((part) => part.type === type).value
  const today = `${get('year')}-${get('month')}-${get('day')}`
  const reading = (comparison?.daily || []).find((item) => item.date === today)
  return <article className="water-charge-card"><span className="water-charge-icon"><Waves size={20} /></span><div><h3>Uso de hoje</h3><p>{reading ? `${fmt(reading.volume_m3)} m³ registrados` : 'Sem leitura hoje'}</p><small>{comparison?.daily_reference_limit_m3 == null ? 'Limite diário não informado.' : `Limite diário: ${fmt(comparison.daily_reference_limit_m3)} m³. A disponibilidade depende da cobertura das leituras.`}</small></div></article>
}

function AnnualChart({ data, loading, error }) {
  const rows = data?.months || []
  const values = rows.filter((row) => row.measured_volume_m3 != null).map((row) => Number(row.measured_volume_m3)).filter(Number.isFinite)
  const max = Math.max(1, ...values)
  return <article className="water-annual-card"><div className="water-card-heading"><div><h3>Histórico anual de uso</h3><p>Volumes registrados por mês · cobertura parcial</p></div><span>{data?.year || 'm³'}</span></div>
    {loading ? <div className="water-card-empty" role="status">Carregando histórico…</div> : error ? <div className="water-card-empty is-error" role="alert">{error}</div> : !values.length ? <div className="water-card-empty"><Waves size={22} /><strong>Sem registros para este ano</strong><span>Os meses aparecem quando houver leituras elegíveis.</span></div> : <div className="water-annual-scroll"><div className="water-annual-chart" role="img" aria-label={`Uso anual parcial: ${rows.map((row) => `${months[row.month - 1]}: ${row.measured_volume_m3 == null ? 'sem leitura' : `${fmt(row.measured_volume_m3)} metros cúbicos`}`).join('; ')}`}>
      {rows.map((row) => <div className="water-annual-column" key={row.month}><div className="water-annual-track">{row.measured_volume_m3 == null ? <span>—</span> : <><i style={{ height: `${Number(row.measured_volume_m3) === 0 ? 0 : Math.max(2, Number(row.measured_volume_m3) / max * 100)}%` }} /><b>{fmt(row.measured_volume_m3)}</b></>}</div><small>{months[row.month - 1]}</small></div>)}
    </div></div>}
    <p className="water-card-note">Meses com “—” não possuem volume elegível; os valores exibidos não comprovam cobertura completa.</p>
  </article>
}

export default function WaterUseOverview({ outorgas = [], comparisons = [], dashboard, onNavigate, compact = false, loadError = '' }) {
  const permits = useMemo(() => outorgas.filter((item) => !item.is_demo), [outorgas])
  const [selectedId, setSelectedId] = useState('')
  const selected = permits.find((item) => String(item.id) === selectedId) || permits[0]
  const comparison = comparisons.find((item) => item.outorga_id === selected?.id)
  const year = Number(new Intl.DateTimeFormat('en', { timeZone: 'America/Sao_Paulo', year: 'numeric' }).format(new Date()))
  const [annual, setAnnual] = useState(null)
  const [annualLoading, setAnnualLoading] = useState(false)
  const [annualError, setAnnualError] = useState('')
  useEffect(() => {
    if (!selected?.id) { setAnnual(null); return }
    let active = true
    setAnnual(null); setAnnualError(''); setAnnualLoading(true)
    waterService.annualOutorgaUsage(selected.id, year).then(({ data }) => { if (active) setAnnual(data) })
      .catch(() => { if (active) setAnnualError('Não foi possível carregar o histórico anual.') })
      .finally(() => { if (active) setAnnualLoading(false) })
    return () => { active = false }
  }, [selected?.id, year])
  if (loadError) return <section className="water-use-empty" role="alert"><strong>Não foi possível carregar o uso hídrico.</strong><span>{loadError}</span></section>
  if (!selected) return <section className="water-use-overview water-use-unconfigured" aria-label="Acompanhamento da outorga"><div className="water-use-empty"><span className="water-use-empty-icon"><FileText size={23} /></span><div><h3>Comece por uma outorga</h3><p>Cadastre os limites para acompanhar o uso da água.</p></div>{onNavigate && <button type="button" className="button primary" onClick={() => onNavigate('Outorga')}>Cadastrar outorga <ArrowRight size={16} /></button>}</div><GrantDashboard comparison={null} dashboard={dashboard} /><div className="water-use-extra"><AnnualChart data={null} loading={false} error="" /><div className="water-use-extra-side"><DailyAvailability comparison={null} /><article className="water-charge-card"><span className="water-charge-icon"><Waves size={20} /></span><div><h3>Cobrança pelo uso da água</h3><p>Valor indisponível</p><small>Cadastre uma fonte e os critérios de cobrança para calcular esse valor.</small></div></article></div></div></section>
  return <section className={`water-use-overview${compact ? ' is-compact' : ''}`} aria-label="Acompanhamento da outorga">
    <div className="water-use-toolbar"><div><p className="eyebrow">USO HÍDRICO</p><h2>Acompanhamento da outorga</h2><p>Consulte os limites e os registros disponíveis da propriedade.</p></div>{permits.length > 1 && <label className="water-use-select"><span>Outorga</span><select value={String(selected.id)} onChange={(event) => setSelectedId(event.target.value)}>{permits.map((item) => <option value={item.id} key={item.id}>{item.name} · {item.permit_number}</option>)}</select></label>}</div>
    <div className="water-use-summary"><div><span className="water-summary-icon"><FileText size={19} /></span><div><small>OUTORGA</small><h3>{selected.name}</h3><p>Portaria {selected.permit_number} · {selected.water_body}</p></div></div><div className="water-summary-dates"><span>Emissão <strong>{date(selected.issued_on)}</strong></span><span>Válida até <strong>{date(selected.valid_until)}</strong></span></div></div>
    <GrantDashboard comparison={comparison} dashboard={dashboard} />
    <div className="water-use-extra"><AnnualChart data={annual} loading={annualLoading} error={annualError} /><div className="water-use-extra-side"><DailyAvailability comparison={comparison} /><article className="water-charge-card"><span className="water-charge-icon"><Waves size={20} /></span><div><h3>Cobrança pelo uso da água</h3><p>Valor indisponível</p><small>Cadastre uma fonte e os critérios de cobrança para calcular esse valor.</small></div></article></div></div>
  </section>
}
