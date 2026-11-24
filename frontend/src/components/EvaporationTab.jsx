import { ArrowRight, Droplets } from 'lucide-react'
import ResidualHistoryChart from './ResidualHistoryChart'

export default function EvaporationTab({ balance, onNavigate }) {
  return <div className="monitor-page water-balance-page">
    <header className="monitor-heading"><div><p className="eyebrow">BALANÇO HÍDRICO</p><h2>Perda residual do reservatório</h2><p>Uma visão do que entra, sai e permanece armazenado no mesmo período.</p></div><span className="monitor-status">{balance?.is_demo ? 'Dados simulados' : balance?.status || 'Dados insuficientes'}</span></header>
    <section className="balance-hero">
      <div className="balance-hero-copy"><span className="balance-hero-label"><Droplets size={17} aria-hidden="true" /> PERDA RESIDUAL ESTIMADA{balance?.is_demo ? ' · SIMULAÇÃO' : ''}</span><h3>{balance?.loss_residual_mm_day == null ? 'Ainda não é possível calcular' : `${Number(balance.loss_residual_mm_day).toLocaleString('pt-BR', { maximumFractionDigits: 2 })} mm/dia`}</h3><p>{balance?.loss_residual_mm_day == null ? 'O cálculo depende de medições e informações compatíveis para o mesmo intervalo.' : balance?.is_demo ? 'Exemplo calculado com valores inteiramente simulados para o último mês completo.' : 'Resultado estimado para o intervalo informado.'}</p><span className="balance-hero-caption">{balance?.is_demo ? 'Demonstração: não representa uma medição real.' : 'O resultado depende das premissas e da cobertura dos registros.'}</span></div>
      <div className="balance-hero-art"><img src="/images/reservoir-onboarding.png" alt="" /></div>
    </section>
    <ResidualHistoryChart history={balance?.history} />
    <div className="balance-overview-heading"><div><h3>Informações para o balanço</h3><p>Reúna os registros abaixo para o mesmo intervalo de tempo.</p></div></div>
    <div className="balance-requirements">
      <article><span className="balance-requirement-art"><img src="/images/balance-reservoir.png" alt="" /></span><div><h4>Reservatório e nível</h4><p>Área superficial média e variação do volume armazenado.</p><button type="button" onClick={() => onNavigate('Estação / nível')}>Ver estação e nível <ArrowRight size={15} aria-hidden="true" /></button></div></article>
      <article><span className="balance-requirement-art"><img src="/images/balance-flow.png" alt="" /></span><div><h4>Entradas e saídas</h4><p>Volumes medidos e outras saídas quantificadas no período.</p><button type="button" onClick={() => onNavigate('Hidrômetros')}>Ver hidrômetros <ArrowRight size={15} aria-hidden="true" /></button></div></article>
      <article><span className="balance-requirement-art"><img src="/images/balance-rain.png" alt="" /></span><div><h4>Precipitação</h4><p>Chuva acumulada e duração correspondente ao intervalo.</p><button type="button" onClick={() => onNavigate('Meteorologia')}>Ver meteorologia <ArrowRight size={15} aria-hidden="true" /></button></div></article>
    </div>
    <section className="balance-method"><div><h3>Como interpretar</h3><p>O balanço considera entradas, chuva, saídas e variação do armazenamento. A perda residual não é uma medição direta de evaporação.</p></div><div className="balance-equation"><span>RELAÇÃO ENTRE OS VOLUMES</span><strong>Entradas + chuva − saídas − variação do volume</strong><small>O nível é convertido em volume apenas com uma relação geométrica aplicável.</small></div></section>
  </div>
}
