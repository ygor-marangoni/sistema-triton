import { ChartNoAxesColumnIncreasing } from 'lucide-react'

const acceptedStatus = 'perda residual estimada pelo balanço hídrico'
const originLabels = { manual: 'manual', medida: 'medida', estimada: 'estimada', simulada: 'simulada', mista: 'mista' }

export function validMonthlyResiduals(history) {
  if (!Array.isArray(history)) return []
  const months = new Map()
  const reservoirs = new Set()
  for (const item of history) {
    const start = String(item.period_start || '')
    const end = String(item.period_end || '')
    const reservoirId = String(item.reservoir_id ?? '')
    if (!/^[1-9]\d*$/.test(reservoirId) || !/^\d{4}-\d{2}-01$/.test(start) || !/^\d{4}-\d{2}-\d{2}$/.test(end) || item.status !== acceptedStatus || item.coverage !== 'comprovada' || !originLabels[item.origin] || item.loss_residual_mm_day == null) continue
    const [year, month] = start.split('-').map(Number)
    if (month < 1 || month > 12) continue
    const lastDay = new Date(Date.UTC(year, month, 0)).getUTCDate()
    if (end !== `${start.slice(0, 7)}-${String(lastDay).padStart(2, '0')}`) continue
    if (!['string', 'number'].includes(typeof item.loss_residual_mm_day) || String(item.loss_residual_mm_day).trim() === '') continue
    const value = Number(item.loss_residual_mm_day)
    if (!Number.isFinite(value) || value < 0) continue
    reservoirs.add(reservoirId)
    const key = start.slice(0, 7)
    months.set(key, months.has(key) ? null : { month: key, value, origin: item.origin })
  }
  if (reservoirs.size > 1) return []
  return [...months.values()].filter(Boolean).sort((a, b) => a.month.localeCompare(b.month)).slice(-12)
}

export default function ResidualHistoryChart({ history, toolbar, loading = false }) {
  const values = validMonthlyResiduals(history)
  const byMonth = new Map(values.map((item) => [item.month, item]))
  const slots = []
  if (values.length) {
    const [firstYear, firstMonth] = values[0].month.split('-').map(Number)
    const [lastYear, lastMonth] = values.at(-1).month.split('-').map(Number)
    for (let cursor = firstYear * 12 + firstMonth - 1; cursor <= lastYear * 12 + lastMonth - 1; cursor += 1) {
      const month = `${Math.floor(cursor / 12)}-${String(cursor % 12 + 1).padStart(2, '0')}`
      slots.push(byMonth.get(month) || { month, value: null })
    }
  }
  const maximum = Math.max(1, ...values.map((item) => item.value))
  const magnitude = 10 ** Math.floor(Math.log10(maximum))
  const scale = Math.ceil(maximum / magnitude * 1.15) * magnitude
  return <section className="residual-chart" aria-labelledby="residual-chart-title"><div className="residual-chart-heading"><div><p className="eyebrow">HISTÓRICO</p><h3 id="residual-chart-title">Perda residual ao longo dos meses</h3><p>Estimativa do balanço hídrico em mm/dia, por período mensal completo.</p></div><div className="residual-chart-controls">{toolbar}<span>mm/dia</span></div></div>
    {loading ? <div className="residual-chart-empty" role="status"><span className="spinner" /><strong>Carregando histórico…</strong></div> : values.length === 0 ? <div className="residual-chart-empty"><span className="residual-chart-empty-icon"><ChartNoAxesColumnIncreasing size={22} strokeWidth={1.6} aria-hidden="true" /></span><strong>Sem histórico calculado</strong><p>Os períodos aparecerão aqui quando houver dados completos e cálculos disponíveis.</p></div> : <><div className="residual-chart-plot" tabIndex={0} role="img" aria-label={`Perda residual estimada em milímetros por dia: ${slots.map((item) => item.value == null ? `${item.month}: sem dados válidos` : `${item.month}: ${item.value.toLocaleString('pt-BR')} (${originLabels[item.origin]})`).join('; ')}`}><div className="residual-chart-axis" aria-hidden="true">{[1, .75, .5, .25, 0].map((tick) => <span key={tick}>{(scale * tick).toLocaleString('pt-BR', { maximumFractionDigits: 2 })}</span>)}</div><div className="residual-chart-content"><div className="residual-chart-grid" aria-hidden="true" /><div className="residual-chart-bars">{slots.map((item) => <div key={item.month} className={`residual-chart-column${item.value == null ? ' is-missing' : ''}`}><div className="residual-chart-track">{item.value == null ? <span className="residual-chart-gap" title="Sem dados válidos">—</span> : <i style={{ height: `${item.value / scale * 100}%` }}><span>{item.value.toLocaleString('pt-BR', { maximumFractionDigits: 2 })}</span></i>}</div><small>{item.month.slice(5)}/{item.month.slice(2, 4)}<br /><em>{item.value == null ? 'sem dados' : originLabels[item.origin]}</em></small></div>)}</div></div></div><p className="residual-chart-swipe">Deslize o gráfico para ver os demais meses.</p><p className="residual-chart-note">Somente meses completos e válidos são exibidos. Meses ausentes não são estimados.</p></>}
  </section>
}
