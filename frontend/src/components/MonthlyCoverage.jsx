import { ChevronDown } from 'lucide-react'
import { IntegrationHeader } from './IntegrationUI'

const labels = { area_m2: 'Área superficial média', rain_mm: 'Precipitação', inflow_m3: 'Entradas', outflow_m3: 'Saídas monitoradas', other_outflow_m3: 'Outras saídas', initial_volume_m3: 'Volume inicial', final_volume_m3: 'Volume final' }
const monthNames = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
const label = (value) => Object.entries(labels).reduce((text, [key, name]) => text.replaceAll(key, name), String(value))

function SourceDetails({ sources }) {
  const entries = Object.entries(sources || {}).filter(([, rows]) => Array.isArray(rows) && rows.length)
  if (!entries.length) return null
  return <details className="integration-month-sources"><summary>Ver registros usados, horários e unidades</summary><dl className="integration-facts">
    {entries.map(([key, rows]) => <div key={key}><dt>{labels[key] || label(key)}</dt><dd>{rows.map((row, index) => <span className="integration-source-row" key={`${row.id ?? index}`}>
      {row.value ?? row.volume_m3 ?? row.level_m ?? '—'} {row.unit || (row.volume_m3 != null ? 'm³' : row.level_m != null ? 'm' : '')} · {row.source || row.method || 'curva'}
      <small>{row.period_start && `${row.period_start} – ${row.period_end}`} {row.observed_at && `· ${row.observed_at}`} {row.reference && `· ${row.reference}`} {row.curve_id && `· curva ${row.curve_id}`}</small>
    </span>)}</dd></div>)}
  </dl></details>
}

export default function MonthlyCoverage({ history }) {
  const items = (history || []).filter((item) => item.available_records && Array.isArray(item.missing))
  if (!items.length) return null
  return <details className="integration-panel monthly-coverage">
    <summary className="integration-section-summary"><IntegrationHeader title="Dados por período" description="Consulte cobertura, pendências e resultados mensais." /><ChevronDown size={17} aria-hidden="true" /></summary>
    <div className="integration-month-list"><div className="integration-month-heading" aria-hidden="true"><span>Período</span><span>Registros encontrados</span><span>Situação</span><span /></div>
      {items.map((item) => {
        const [year, month] = item.period_start.split('-').map(Number)
        const proven = item.coverage === 'comprovada' && item.loss_residual_mm_day != null
        const declared = item.declared_assessment?.result?.loss_residual_mm_day != null
        const status = proven ? 'Cobertura comprovada' : declared ? 'Cobertura declarada' : item.period_complete ? 'Dados insuficientes' : 'Em andamento'
        return <details className="integration-month" key={`${item.reservoir_id}-${item.period_start}`}>
          <summary><span className="integration-month-date"><strong>{monthNames[month - 1]} de {year}</strong><small>{item.reservoir_name || `Reservatório ${item.reservoir_id}`}</small></span><span className="integration-month-counts">{item.available_records.level_readings} nível · {item.available_records.hydrometer_readings} hidrômetro · {item.available_records.precipitation_observations} chuva</span><span className="integration-month-state"><i className={`integration-month-dot${proven ? ' is-declared' : ''}`} />{status}</span><ChevronDown size={16} /></summary>
          <div className="integration-month-content">
            {proven && <div className="integration-month-result"><strong>{Number(item.loss_residual_mm_day).toLocaleString('pt-BR', { maximumFractionDigits: 2 })}</strong><span>mm/dia · perda residual estimada · cobertura comprovada</span></div>}
            {declared && <div className="integration-month-result is-declared"><strong>{Number(item.declared_assessment.result.loss_residual_mm_day).toLocaleString('pt-BR', { maximumFractionDigits: 2 })}</strong><span>mm/dia · avaliação manual · cobertura declarada</span></div>}
            {item.missing.length > 0 && <div className="integration-month-issues"><strong>Dados pendentes</strong><ul>{item.missing.map((missing, index) => <li key={index}>{label(missing)}</li>)}</ul></div>}
            {item.problems?.length > 0 && <div className="integration-month-issues"><strong>Para revisar</strong><ul>{item.problems.map((problem, index) => <li key={index}>{label(problem)}</li>)}</ul></div>}
            <SourceDetails sources={item.data_sources} />
            {item.declared_assessment?.inputs && <details className="integration-month-sources"><summary>Ver avaliação manual e origens declaradas</summary><dl className="integration-facts">{Object.entries(item.declared_assessment.inputs).map(([name, datum]) => <div key={name}><dt>{labels[name] || name}</dt><dd>{datum.value} {datum.unit} · {datum.source}<br /><small>{datum.reference} · {datum.coverage_complete ? 'cobertura declarada' : 'cobertura incompleta'}</small></dd></div>)}</dl></details>}
            {item.automatic_assessment && <p className="integration-assessment-meta">Último cálculo automático registrado: {new Date(item.automatic_assessment.created_at).toLocaleString('pt-BR')}.</p>}
          </div>
        </details>
      })}
    </div>
  </details>
}
