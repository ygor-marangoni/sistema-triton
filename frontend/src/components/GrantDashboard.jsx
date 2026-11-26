import { Activity, CalendarDays, Droplets, Gauge } from 'lucide-react'

const fmt = (value, digits = 1) => value == null || !Number.isFinite(Number(value)) ? '—' : Number(value).toLocaleString('pt-BR', { maximumFractionDigits: digits })
const dayLabel = (date) => date.slice(8, 10)
const operationalMonth = (value) => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const parts = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Sao_Paulo', year: 'numeric', month: '2-digit' }).formatToParts(date)
  return `${parts.find((part) => part.type === 'year').value}-${parts.find((part) => part.type === 'month').value}`
}

function averageFlow(readings) {
  const valid = readings.filter((item) => item.flow_m3_h != null && Number.isFinite(Number(item.flow_m3_h)) && Number(item.flow_m3_h) >= 0 && item.interval_start_at && item.observed_at && new Date(item.observed_at) > new Date(item.interval_start_at))
  if (!valid.length) return null
  const weighted = valid.reduce((sum, item) => {
    const duration = (new Date(item.observed_at) - new Date(item.interval_start_at)) / 3600000
    return { hours: sum.hours + duration, total: sum.total + Number(item.flow_m3_h) * duration }
  }, { hours: 0, total: 0 })
  return weighted.hours ? weighted.total / weighted.hours : null
}

function BarChart({ title, subtitle, entries, limit }) {
  const values = entries.filter((entry) => entry.value != null).map((entry) => Number(entry.value)).filter(Number.isFinite)
  const ceiling = Math.max(1, ...values, limit == null ? 0 : Number(limit)) * 1.1
  return <article className="grant-chart"><div className="grant-chart-heading"><div><h4>{title}</h4><p>{subtitle}</p></div><span>m³</span></div>{entries.length ? <div className="grant-chart-scroll"><div className="grant-chart-bars" role="img" aria-label={`${title}: ${entries.map((entry) => `${entry.label}, ${fmt(entry.value)} metros cúbicos`).join('; ')}`}>
    {limit != null && <div className="grant-chart-limit" style={{ bottom: `${Number(limit) / ceiling * 100}%` }}><span>Limite diário · {fmt(limit)} m³</span></div>}
    {entries.map((entry) => <div className="grant-chart-column" key={entry.label}><div className="grant-chart-track"><i className={entry.over > 0 ? 'is-over' : ''} style={{ height: `${Math.max(0, Number(entry.value) / ceiling * 100)}%` }} /><span className="grant-chart-value" style={{ bottom: `${Math.max(0, Number(entry.value) / ceiling * 100)}%` }}>{fmt(entry.value)}</span></div><small>{entry.label}</small></div>)}
  </div></div> : <div className="grant-chart-empty"><Activity size={22} /><strong>Ainda sem leituras elegíveis</strong><span>Os registros aparecerão aqui após a revisão e o vínculo da outorga.</span></div>}</article>
}

export default function GrantDashboard({ comparison, dashboard }) {
  if (!comparison) return <section className="grant-dashboard" aria-label="Painel da outorga"><div className="grant-dashboard-title"><div><p className="eyebrow">ACOMPANHAMENTO</p><h3>Uso da outorga</h3><p>Os indicadores serão preenchidos com leituras elegíveis.</p></div></div><div className="grant-stats triton-kpi-grid">{['Volume registrado', 'Dias com leitura', 'Vazão média de entrada', 'Vazão média de saída'].map((label) => <div key={label}><span><Gauge size={19} />{label}</span><strong>—</strong><small>Sem dados disponíveis</small></div>)}</div><div className="grant-charts"><BarChart title="Uso diário" subtitle="Dias com volume atribuível" entries={[]} /><BarChart title="Uso semanal" subtitle="Soma dos dias registrados" entries={[]} /></div><p className="grant-dashboard-note">Cadastre uma outorga e vincule leituras para acompanhar o uso.</p></section>
  const days = comparison.daily || []
  const weekly = []
  for (let first = 1; first <= 29; first += 7) {
    const rows = days.filter((day) => Number(day.date.slice(8, 10)) >= first && Number(day.date.slice(8, 10)) < first + 7)
    if (rows.length) weekly.push({ label: `${String(first).padStart(2, '0')}–${String(Math.min(first + 6, new Date(comparison.year, comparison.month, 0).getDate())).padStart(2, '0')}`, value: rows.reduce((total, row) => total + Number(row.volume_m3), 0), over: rows.some((row) => Number(row.extrapolated_m3) > 0) })
  }
  const entryFlow = averageFlow(comparison.eligible_intervals || [])
  const month = `${comparison.year}-${String(comparison.month).padStart(2, '0')}`
  const exitReadings = (dashboard?.recent_hydrometers || []).filter((item) => item.hydrometer.kind === 'saída').flatMap((item) => item.readings || []).filter((reading) => reading.quality === 'validada' && reading.source !== 'simulada' && reading.observed_at && reading.interval_start_at && operationalMonth(reading.interval_start_at) === month && operationalMonth(reading.observed_at) === month)
  const exitFlow = averageFlow(exitReadings)
  const measured = comparison.measured_volume_m3
  const exceeded = measured != null && Number(measured) > Number(comparison.monthly_reference_limit_m3)
  const quota = Number(comparison.monthly_reference_limit_m3)
  const percent = measured != null && quota > 0 ? Number(measured) / quota * 100 : null
  const flows = [{ label: 'Entrada · outorga', value: entryFlow }, { label: 'Saída · propriedade', value: exitFlow }].filter((item) => item.value != null)
  const flowScale = Math.max(1, ...flows.map((item) => item.value))
  return <section className="grant-dashboard" aria-label="Painel da outorga"><div className="grant-dashboard-title"><div><p className="eyebrow">ACOMPANHAMENTO · {String(comparison.month).padStart(2, '0')}/{comparison.year}</p><h3>Uso da outorga</h3><p>Registros disponíveis no mês, sujeitos à cobertura das leituras.</p></div><span className={`grant-dashboard-status${exceeded ? ' is-over' : ''}`}>{measured == null ? 'Aguardando leituras' : exceeded ? 'Limite mensal ultrapassado' : 'Uso parcial registrado'}</span></div>
    <div className="grant-stats triton-kpi-grid"><div><span><Droplets size={19} />Volume registrado</span><strong>{measured == null ? 'Sem dados' : `${fmt(measured)} m³`}</strong><small>Limite mensal: {fmt(comparison.monthly_reference_limit_m3)} m³</small></div><div><span><CalendarDays size={19} />Dias com leitura</span><strong>{days.length}</strong><small>{comparison.missing_days} dia(s) sem leitura no mês</small></div><div><span><Gauge size={19} />Vazão média de entrada</span><strong>{entryFlow == null ? 'Sem dados' : `${fmt(entryFlow)} m³/h`}</strong><small>Média das leituras elegíveis desta outorga</small></div><div><span><Gauge size={19} />Vazão média de saída</span><strong>{exitFlow == null ? 'Sem dados' : `${fmt(exitFlow)} m³/h`}</strong><small>Média das últimas leituras revisadas da propriedade</small></div></div>
    <div className="grant-charts"><BarChart title="Uso diário" subtitle="Dias com volume atribuível" entries={days.map((day) => ({ label: dayLabel(day.date), value: day.volume_m3, over: Number(day.extrapolated_m3) }))} limit={comparison.daily_reference_limit_m3} /><BarChart title="Uso semanal" subtitle="Soma dos dias registrados · períodos parciais" entries={weekly} /></div>
    <div className="grant-insights"><article className="grant-chart grant-quota"><div><h4>Uso do limite mensal</h4><p>Considera somente o volume registrado.</p></div><div className="grant-quota-ring" role="img" aria-label={percent == null ? 'Percentual indisponível' : `${fmt(percent)} por cento do limite mensal nos registros disponíveis`} style={{ background: percent == null ? '#e8f0eb' : `conic-gradient(${exceeded ? '#cf7168' : '#1a967e'} ${Math.min(percent, 100)}%, #e8f0eb 0)` }}><div><strong>{percent == null ? '—' : `${fmt(percent)}%`}</strong><small>registrado</small></div></div></article><article className="grant-chart grant-flow"><h4>Vazões informadas</h4><p>Média ponderada pela duração das leituras disponíveis.</p>{flows.length ? flows.map((item) => <div className="grant-flow-row" key={item.label}><span>{item.label}</span><b>{fmt(item.value)} m³/h</b><div><i style={{ width: `${item.value / flowScale * 100}%` }} /></div></div>) : <div className="grant-chart-empty"><Gauge size={22} /><strong>Sem vazões revisadas</strong><span>Adicione leituras com vazão e intervalo.</span></div>}</article></div>
    <p className="grant-dashboard-note">Os gráficos mostram apenas leituras elegíveis. Ausência de leitura não significa consumo zero; intervalos entre dias não são distribuídos.</p>
  </section>
}
