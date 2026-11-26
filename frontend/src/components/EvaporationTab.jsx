import { ArrowRight, ChevronDown } from 'lucide-react'
import { lazy, Suspense, useState } from 'react'
import ResidualHistoryChart from './ResidualHistoryChart'
import BalanceEntry from './BalanceEntry'
import MonthlyCoverage from './MonthlyCoverage'
import { IntegrationNotice } from './IntegrationUI'
import { waterService } from '../services/triton'
const BalanceMap = lazy(() => import('./BalanceMap'))

export default function EvaporationTab({ balance, onNavigate, onUpdated, propertyId, property, meters, reservoirs, metersError, reservoirsError }) {
  const currentYear = Number(new Intl.DateTimeFormat('en', { timeZone: 'America/Sao_Paulo', year: 'numeric' }).format(new Date()))
  const [year, setYear] = useState(String(currentYear)), [historical, setHistorical] = useState(null), [historyError, setHistoryError] = useState(''), [historyLoading, setHistoryLoading] = useState(false)
  const history = historical?.history || balance?.history
  const years = Array.from({ length: Math.max(1, Math.min(currentYear, 2100) - 2000 + 1) }, (_, index) => Math.min(currentYear, 2100) - index)
  async function loadYear(nextYear) {
    const previousYear = historical?.year ?? currentYear
    setYear(nextYear); setHistoryLoading(true); setHistoryError('')
    try { const { data } = await waterService.balanceHistory(propertyId, nextYear); setHistorical(data) }
    catch (e) { setYear(String(previousYear)); setHistoryError(e.response?.status === 404 ? 'Não foi possível acessar o histórico. Confira se a API está atualizada e se a propriedade continua disponível.' : e.response?.data?.detail || 'Falha ao carregar o histórico.') } finally { setHistoryLoading(false) }
  }
  async function refreshHistory() {
    if (onUpdated) await onUpdated()
    if (historical) { const { data } = await waterService.balanceHistory(propertyId, historical.year); setHistorical(data) }
  }
  const volume = balance?.status === 'perda residual estimada pelo balanço hídrico' && balance.loss_residual_m3 != null && Number.isFinite(Number(balance.loss_residual_m3)) && Number(balance.loss_residual_m3) >= 0 ? Number(balance.loss_residual_m3) : null
  const period = balance?.period_start && balance?.period_end ? `${balance.period_start.split('-').reverse().join('/')} a ${balance.period_end.split('-').reverse().join('/')}` : null
  return <div className="monitor-page water-balance-page">
    <header className="monitor-heading"><div><p className="eyebrow">BALANÇO HÍDRICO</p><h2>Perda residual do reservatório</h2><p>Entradas, saídas e variação de volume no período.</p></div></header>
    <div className="balance-latest"><span>Perda residual estimada{balance?.is_demo ? ' · simulação' : ''}{period ? ` · ${period}` : ''}</span><strong>{volume == null ? 'Dados insuficientes' : `${volume.toLocaleString('pt-BR', { maximumFractionDigits: 2 })} m³`}</strong></div>
    <Suspense fallback={<div className="balance-map-placeholder">Carregando mapa…</div>}><BalanceMap property={property} meters={meters} reservoirs={reservoirs} metersError={metersError} reservoirsError={reservoirsError} /></Suspense>
    <ResidualHistoryChart history={history} loading={historyLoading} toolbar={!balance?.is_demo && <label className="residual-year-filter"><span>Ano</span><span className="residual-year-select"><select aria-label="Ano do histórico" value={year} onChange={(event) => loadYear(event.target.value)} disabled={historyLoading}>{years.map((option) => <option key={option} value={option}>{option}</option>)}</select><ChevronDown size={15} aria-hidden="true" /></span></label>} />
    <IntegrationNotice type="error">{typeof historyError === 'string' ? historyError : 'Falha ao carregar o histórico.'}</IntegrationNotice>
    {!balance?.is_demo && <BalanceEntry history={history} onUpdated={refreshHistory} propertyId={propertyId} />}
    {!balance?.is_demo && <MonthlyCoverage history={history} />}
    <div className="balance-overview-heading"><div><h3>Informações para o balanço</h3><p>Reúna os registros abaixo para o mesmo intervalo de tempo.</p></div></div>
    <div className="balance-requirements">
      <article><span className="balance-requirement-art"><img src="/images/balance-reservoir.png" alt="" /></span><div><h4>Reservatório e nível</h4><p>Área superficial média e variação do volume armazenado.</p><button type="button" onClick={() => onNavigate('Estação / nível')}>Ver estação e nível <ArrowRight size={15} aria-hidden="true" /></button></div></article>
      <article><span className="balance-requirement-art"><img src="/images/balance-flow.png" alt="" /></span><div><h4>Entradas e saídas</h4><p>Volumes medidos e outras saídas quantificadas no período.</p><button type="button" onClick={() => onNavigate('Hidrômetros')}>Ver hidrômetros <ArrowRight size={15} aria-hidden="true" /></button></div></article>
      <article><span className="balance-requirement-art"><img src="/images/balance-rain.png" alt="" /></span><div><h4>Precipitação</h4><p>Chuva acumulada e duração correspondente ao intervalo.</p><button type="button" onClick={() => onNavigate('Meteorologia')}>Ver meteorologia <ArrowRight size={15} aria-hidden="true" /></button></div></article>
    </div>
    <section className="balance-method"><div><h3>Como interpretar</h3><p>Comparamos a água que entrou e saiu com a mudança de volume do reservatório. A diferença é uma perda estimada, não uma medição direta de evaporação.</p></div></section>
  </div>
}
