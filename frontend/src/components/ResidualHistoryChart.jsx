const acceptedStatus = 'perda residual estimada pelo balanço hídrico'
const originLabels = { manual: 'manual', medida: 'medida', simulada: 'simulada', mista: 'mista' }

export function validMonthlyResiduals(history) {
  if (!Array.isArray(history)) return []
  const months = new Map()
  const reservoirs = new Set()
  for (const item of history) {
    const start = String(item.period_start || '')
    const end = String(item.period_end || '')
    const reservoirId = String(item.reservoir_id ?? '')
    if (!/^[1-9]\d*$/.test(reservoirId) || !/^\d{4}-\d{2}-01$/.test(start) || !/^\d{4}-\d{2}-\d{2}$/.test(end) || item.status !== acceptedStatus || item.coverage !== 'completa' || !originLabels[item.origin] || item.loss_residual_mm_day == null) continue
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

export default function ResidualHistoryChart({ history }) {
  const values = validMonthlyResiduals(history)
  const maximum = Math.max(1, ...values.map((item) => item.value))
  const magnitude = 10 ** Math.floor(Math.log10(maximum))
  const scale = Math.ceil(maximum / magnitude * 1.15) * magnitude
  return <section className="residual-chart" aria-labelledby="residual-chart-title"><div className="residual-chart-heading"><div><p className="eyebrow">HISTÓRICO</p><h3 id="residual-chart-title">Perda residual ao longo dos meses</h3><p>Estimativa do balanço hídrico em mm/dia, por período mensal completo.</p></div><span>mm/dia</span></div>
    {values.length === 0 ? <div className="residual-chart-empty"><strong>Sem histórico calculado</strong><p>Os períodos aparecerão aqui quando houver dados completos e cálculos disponíveis.</p></div> : <><div className="residual-chart-plot" tabIndex={0} role="img" aria-label={`Perda residual estimada em milímetros por dia: ${values.map((item) => `${item.month}: ${item.value.toLocaleString('pt-BR')} (${originLabels[item.origin]})`).join('; ')}`}><div className="residual-chart-axis" aria-hidden="true">{[1, .75, .5, .25, 0].map((tick) => <span key={tick}>{(scale * tick).toLocaleString('pt-BR', { maximumFractionDigits: 2 })}</span>)}</div><div className="residual-chart-content"><div className="residual-chart-grid" aria-hidden="true" /><div className="residual-chart-bars">{values.map((item) => <div key={item.month} className="residual-chart-column"><div className="residual-chart-track"><i style={{ height: `${item.value / scale * 100}%` }}><span>{item.value.toLocaleString('pt-BR', { maximumFractionDigits: 2 })}</span></i></div><small>{item.month.slice(5)}/{item.month.slice(2, 4)}<br /><em>{originLabels[item.origin]}</em></small></div>)}</div></div></div><p className="residual-chart-swipe">Deslize o gráfico para ver os demais meses.</p><p className="residual-chart-note">Somente meses completos e válidos são exibidos. Meses ausentes não são estimados.</p></>}
  </section>
}
