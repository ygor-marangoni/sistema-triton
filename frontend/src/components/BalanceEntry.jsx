import { useState } from 'react'
import { CalendarDays, ClipboardCheck, Save } from 'lucide-react'
import { waterService } from '../services/triton'
import { IntegrationField, IntegrationHeader, IntegrationNotice } from './IntegrationUI'
import BalanceSourceEvidence from './BalanceSourceEvidence'

const variables = [
  ['area_m2', 'Área superficial média', 'm²'],
  ['rain_mm', 'Precipitação acumulada', 'mm'],
  ['inflow_m3', 'Entradas', 'm³'],
  ['outflow_m3', 'Saídas monitoradas', 'm³'],
  ['other_outflow_m3', 'Outras saídas quantificadas', 'm³'],
  ['initial_volume_m3', 'Volume inicial', 'm³'],
  ['final_volume_m3', 'Volume final', 'm³'],
]

export default function BalanceEntry({ history, onUpdated, propertyId }) {
  const periods = (history || []).filter((item) => item.period_start_utc && item.period_end_utc_exclusive)
  const [choice, setChoice] = useState('')
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const period = periods.find((item) => `${item.reservoir_id}:${item.period_start}` === choice)

  if (!periods.length) return null

  async function save(event) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const inputs = {}
    for (const [key, label, unit] of variables) {
      const value = form.get(`${key}_value`)
      if (value === '') continue
      const reference = String(form.get(`${key}_reference`) || '').trim()
      if (!reference) { setError(`Informe a origem de ${label}.`); return }
      const datum = { value, unit, source: form.get(`${key}_source`), reference,
        period_start: period.period_start_utc, period_end: period.period_end_utc_exclusive,
        coverage_complete: form.has(`${key}_coverage`) }
      if (key === 'initial_volume_m3' || key === 'final_volume_m3') {
        datum.observed_at = form.has(`${key}_boundary`)
          ? (key === 'initial_volume_m3' ? period.period_start_utc : period.period_end_utc_exclusive)
          : null
      }
      inputs[key] = datum
    }
    try {
      const [year, month] = period.period_start.split('-').map(Number)
      const { data } = await waterService.recordBalance(period.reservoir_id, { year, month, inputs })
      setResult(data); setError('')
      if (onUpdated) await onUpdated()
    } catch (e) {
      setError(typeof e.response?.data?.detail === 'string' ? e.response.data.detail : 'Dados inválidos; confira valores e referências.')
    }
  }

  async function calculateAutomatic() {
    try {
      const [year, month] = period.period_start.split('-').map(Number)
      const { data } = await waterService.calculateAutomaticBalance(period.reservoir_id, year, month)
      setResult(data); setError('')
      if (onUpdated) await onUpdated()
    } catch (e) {
      setError(typeof e.response?.data?.detail === 'string' ? e.response.data.detail : 'Não foi possível calcular com os registros disponíveis.')
    }
  }

  return <section className="integration-panel balance-entry">
    <IntegrationHeader title="Balanço mensal" description="Monte o resultado com registros rastreáveis ou registre uma avaliação declarada." />
    <label className="integration-field balance-period-picker">
      <span>Reservatório e mês</span>
      <select value={choice} onChange={(event) => { setChoice(event.target.value); setResult(null); setError('') }}>
        <option value="">Selecione um período</option>
        {periods.map((item) => <option key={`${item.reservoir_id}:${item.period_start}`} value={`${item.reservoir_id}:${item.period_start}`}>
          {item.reservoir_name || `Reservatório ${item.reservoir_id}`} · {item.period_start.slice(0, 7)}
        </option>)}
      </select>
    </label>

    {period ? <>
      <BalanceSourceEvidence key={choice} propertyId={propertyId} period={period} onUpdated={onUpdated} />
      <div className="integration-auto-action">
        <div><strong>Calcular com cobertura comprovada</strong><span>Usa somente intervalos revisados, vínculos temporais e curva aplicável.</span></div>
        <button type="button" className="button secondary" onClick={calculateAutomatic}><ClipboardCheck size={15} />Calcular automaticamente</button>
      </div>
      <form key={`declared-${choice}`} className="integration-balance-form" onSubmit={save}>
        <div className="integration-period"><CalendarDays size={16} aria-hidden="true" /><span>{period.period_start.split('-').reverse().join('/')} a {period.period_end.split('-').reverse().join('/')} · horário de Brasília</span></div>
        <p className="integration-helper">Avaliação manual: informe apenas valores com origem conhecida. A cobertura marcada nesta seção é declarada por você e não comprova os intervalos.</p>
        <div className="integration-measure-table">
          <div className="integration-measure-heading" aria-hidden="true"><span>Grandeza</span><span>Valor</span><span>Origem</span><span>Referência</span><span>Declaração</span></div>
          {variables.map(([key, label, unit]) => <div className="integration-measure-row" key={key}>
            <div className="integration-measure-name"><strong>{label}</strong><small>{unit}</small></div>
            <IntegrationField label={`Valor de ${label}`}><input type="number" min="0" step="any" name={`${key}_value`} placeholder="—" /></IntegrationField>
            <IntegrationField label={`Origem de ${label}`}><select name={`${key}_source`}><option value="manual">Manual</option><option value="medida">Medição</option><option value="estimada">Estimativa</option><option value="simulada">Simulação</option></select></IntegrationField>
            <IntegrationField label={`Referência de ${label}`}><input name={`${key}_reference`} placeholder="Documento ou leitura" /></IntegrationField>
            <div className="integration-measure-checks">
              <label className="integration-check"><input type="checkbox" name={`${key}_coverage`} /><span>Cobertura declarada completa</span></label>
              {key.includes('_volume_m3') && <label className="integration-check"><input type="checkbox" name={`${key}_boundary`} /><span>Leitura no limite do mês</span></label>}
            </div>
          </div>)}
        </div>
        <div className="integration-form-actions"><span>Campos vazios ficam ausentes; nenhum valor é completado como zero.</span><button className="button primary"><Save size={15} />Registrar avaliação declarada</button></div>
      </form>
    </> : <p className="integration-placeholder">Selecione um período para consultar evidências e montar o balanço.</p>}
    <IntegrationNotice type={result?.loss_residual_mm_day == null ? 'info' : 'success'}>{result && (result.loss_residual_mm_day == null
      ? `${result.calculation_mode === 'automatico' ? 'Cálculo automático' : 'Avaliação manual'} · ${result.coverage || 'cobertura declarada'} · ${result.status} · ${(result.missing || []).concat(result.problems || []).join('; ')}`
      : `${result.loss_residual_mm_day} mm/dia · perda residual estimada · cobertura ${result.coverage}`)}</IntegrationNotice>
    <IntegrationNotice type="error">{error}</IntegrationNotice>
  </section>
}
