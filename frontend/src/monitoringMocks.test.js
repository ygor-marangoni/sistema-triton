import { after, before, test } from 'node:test'
import assert from 'node:assert/strict'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'
import { createPropertyRequestGuard } from './services/propertyRequestGuard.js'

// Fixtures sintéticas: não usam a API nem gravam no banco da aplicação.
let server, GrantTab, LevelTab, EnergyTab, HydrometerTab, WorkspaceSummary, ReservoirBanner, PropertyEditor, ResidualHistoryChart, validMonthlyResiduals
before(async () => {
  server = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' })
  ;({ GrantTab, LevelTab, EnergyTab } = await server.ssrLoadModule('/src/App.jsx'))
  ;({ default: HydrometerTab } = await server.ssrLoadModule('/src/components/HydrometerTab.jsx'))
  ;({ default: WorkspaceSummary } = await server.ssrLoadModule('/src/components/WorkspaceSummary.jsx'))
  ;({ default: ReservoirBanner } = await server.ssrLoadModule('/src/components/ReservoirBanner.jsx'))
  ;({ default: PropertyEditor } = await server.ssrLoadModule('/src/components/PropertyEditor.jsx'))
  ;({ default: ResidualHistoryChart, validMonthlyResiduals } = await server.ssrLoadModule('/src/components/ResidualHistoryChart.jsx'))
})
after(async () => { await server?.close() })

const render = (component, props) => renderToStaticMarkup(React.createElement(component, props))
const noop = () => {}
const reservoir = { id: 1, name: 'Reservatório de teste' }
const meter = { id: 2, name: 'Medidor de teste', kind: 'entrada', reservoir_id: 1, outorga_id: null, rated_power_kw: 2 }
const station = { id: 3, name: 'Régua de teste', reservoir_id: 1, minimum_m: 0, maximum_m: 5 }
const dashboard = { reservoirs: [reservoir], recent_hydrometers: [{ hydrometer: meter, readings: [{ volume_m3: 12, source: 'simulada' }] }], latest_levels: [{ reservoir_id: 1, latest: { level_m: 2, source: 'manual' }, volume_m3: null }] }

test('estados vazios levam ao próximo cadastro adequado', () => {
  assert.match(render(GrantTab, { outorgas: [], comparisons: [] }), /Cadastrar outorga/)
  assert.match(render(HydrometerTab, { meters: [], outorgas: [], dashboard, onAddReservoir: noop }), /Cadastrar hidrômetro/)
  assert.match(render(LevelTab, { propertyId: 1, reservoirs: [], stations: [], onAddReservoir: noop }), /Cadastrar reservatório/)
  assert.match(render(LevelTab, { propertyId: 1, reservoirs: [reservoir], stations: [] }), /Cadastrar estação/)
})

test('medições simuladas e manuais conservam origem e ausência de volume', () => {
  const meters = render(HydrometerTab, { meters: [meter], outorgas: [], dashboard })
  assert.match(meters, /Medidor de teste/)
  assert.match(meters, /12 m³ · simulada/)
  assert.match(meters, /Pendente/)
  const levels = render(LevelTab, { propertyId: 1, reservoirs: [reservoir], stations: [station], dashboard })
  assert.match(levels, /2 m · manual/)
  assert.match(levels, /Indisponível/)
})

test('cadastro de estação fica recolhido quando já existe estação', () => {
  const withStation = render(LevelTab, { propertyId: 1, reservoirs: [reservoir], stations: [station], dashboard, onAddReservoir: noop })
  assert.match(withStation, /Cadastrar estação/)
  assert.match(withStation, /Registrar leitura/)
  assert.doesNotMatch(withStation, /Salvar estação/)
  const withoutStation = render(LevelTab, { propertyId: 1, reservoirs: [reservoir], stations: [], dashboard, onAddReservoir: noop })
  assert.match(withoutStation, /Cadastrar estação/)
  assert.doesNotMatch(withoutStation, /Salvar estação/)
})

test('listas de equipamentos exibem apenas dez registros por página', () => {
  const manyStations = Array.from({ length: 100 }, (_, index) => ({ ...station, id: index + 1, reservoir_id: index + 1, name: `Estação teste ${String(index + 1).padStart(3, '0')}` }))
  const manyReservoirs = Array.from({ length: 100 }, (_, index) => ({ id: index + 1, name: `Reservatório ${index + 1}` }))
  const levelHtml = render(LevelTab, { propertyId: 1, reservoirs: manyReservoirs, stations: manyStations, dashboard, onAddReservoir: noop })
  assert.match(levelHtml, /<b>Estação teste 010<\/b>/)
  assert.doesNotMatch(levelHtml, /<b>Estação teste 011<\/b>/)
  assert.match(levelHtml, /página 1 de 10/)
  const manyMeters = Array.from({ length: 100 }, (_, index) => ({ ...meter, id: index + 1, name: `Hidrômetro teste ${String(index + 1).padStart(3, '0')}` }))
  const meterHtml = render(HydrometerTab, { meters: manyMeters, outorgas: [], dashboard, onAddReservoir: noop })
  assert.match(meterHtml, /Hidrômetro teste 010/)
  assert.doesNotMatch(meterHtml, /Hidrômetro teste 011/)
  assert.match(meterHtml, /página 1 de 10/)
})

test('energia incompleta não inventa tarifa ou custo e tolera período parcial', () => {
  const html = render(EnergyTab, { tariffs: [], energy: { period: { start: '2026-11-01' }, energy_kwh: 10, tariff_brl_kwh: null, estimated_cost_brl: null, pumps: [] } })
  assert.match(html, /10 kWh/)
  assert.match(html, /Sem tarifa para o período/)
  assert.match(html, /Nenhuma tarifa cadastrada/)
})

test('outorga com dados simulados apresenta o total registrado como parcial', () => {
  const grant = { id: 4, name: 'Outorga de teste', valid_until: '2030-12-31', water_body: 'Córrego de teste', permit_number: '123', municipality: 'Cidade', state: 'MG', irrigated_area_ha: 2, demands: Array.from({ length: 12 }, (_, i) => ({ month: i + 1, max_flow_m3_h: 5, daily_hours: 2, authorized_days: 10, monthly_volume_m3: 100 })) }
  const comparison = { outorga_id: 4, year: 2026, month: 1, measured_volume_m3: 12, monthly_reference_limit_m3: 100, operating_days_used: 1, operating_days_authorized: 10, non_transferable_surplus_m3: 0, extrapolated_m3: 2, missing_days: 30, daily: [{ date: '2026-01-01', volume_m3: 12, status: 'extrapolado', extrapolated_m3: 2, non_transferable_surplus_m3: 0 }], notes: 'Leituras registradas não comprovam cobertura contínua.' }
  const html = render(GrantTab, { outorgas: [grant], comparisons: [comparison] })
  assert.match(html, /12 m³ registrados/)
  assert.match(html, /Cobertura incompleta/)
  assert.match(html, /Extrapolado/)
})

test('respostas antigas ou de outra propriedade são descartadas', () => {
  let selected = 1
  const guard = createPropertyRequestGuard(() => selected)
  const first = guard.start(1)
  const newer = guard.start(1)
  assert.equal(first(), false)
  assert.equal(newer(), true)
  selected = 2
  assert.equal(newer(), false)
  const other = guard.start(2)
  assert.equal(other(), true)
  guard.invalidate()
  assert.equal(other(), false)
})

test('resumo mostra os dados da propriedade e preserva a origem da leitura', () => {
  const html = render(WorkspaceSummary, { properties: [{ id: 1, latitude: -18, longitude: -47 }], selectedProperty: { id: 1 }, dashboard, meters: [meter], outorgas: [], alerts: [], latestActivity: { label: 'Nível do reservatório', value: '2 m', observedAt: '2026-11-24T12:00:00Z', source: 'simulada' }, onNavigate: noop })
  assert.match(html, /Reservatórios/)
  assert.match(html, /2 m/)
  assert.match(html, /simulado/)
  assert.match(html, /Alertas abertos/)
  assert.doesNotMatch(html, /Ainda não há medições/)
})

test('resumo sem propriedade ou com falha não exibe dados antigos', () => {
  const props = { properties: [], selectedProperty: null, dashboard, meters: [meter], outorgas: [], alerts: [], latestActivity: { label: 'Leitura antiga', value: '2 m' }, onNavigate: noop }
  assert.match(render(WorkspaceSummary, props), /Selecione uma propriedade/)
  assert.doesNotMatch(render(WorkspaceSummary, props), /Leitura antiga/)
  assert.match(render(WorkspaceSummary, { ...props, selectedProperty: { id: 1 }, error: 'Erro' }), /Dados indisponíveis/)
})

test('card de reservatório permanece disponível antes e depois do cadastro', () => {
  assert.match(render(ReservoirBanner, { hasReservoirs: false }), /Comece pelo reservatório/)
  const html = render(ReservoirBanner, { hasReservoirs: true })
  assert.match(html, /Seus reservatórios/)
  assert.match(html, /Cadastrar reservatório/)
})

test('edição inicia com os valores salvos e sem alterações pendentes', () => {
  const html = render(PropertyEditor, { property: { id: 1, name: 'Fazenda de teste', cep: '00000-000', city: 'Cidade', state: 'MG', latitude: null, longitude: null }, busy: false, onSave: noop })
  assert.match(html, /Fazenda de teste/)
  assert.match(html, /Salvar alteração/)
  assert.doesNotMatch(html, />Cancelar</)
})

test('gráfico não transforma lacunas, duplicidades ou períodos parciais em dados válidos', () => {
  const status = 'perda residual estimada pelo balanço hídrico'
  const jan = { reservoir_id: 1, period_start: '2026-01-01', period_end: '2026-01-31', status, coverage: 'completa', origin: 'simulada', loss_residual_mm_day: 2.5 }
  const feb = { period_start: '2026-02-01', period_end: '2026-02-28', status, coverage: 'completa', loss_residual_mm_day: null }
  const march = { period_start: '2026-03-01', period_end: '2026-03-15', status, coverage: 'completa', loss_residual_mm_day: 3 }
  assert.deepEqual(validMonthlyResiduals([jan, feb, march]), [{ month: '2026-01', value: 2.5, origin: 'simulada' }])
  assert.deepEqual(validMonthlyResiduals([jan, jan]), [])
  assert.match(render(ResidualHistoryChart, { history: [] }), /Sem histórico calculado/)
  assert.match(render(ResidualHistoryChart, { history: [jan] }), /2,5/)
  assert.match(render(ResidualHistoryChart, { history: [jan] }), /simulada/)
  assert.deepEqual(validMonthlyResiduals([{ ...jan, loss_residual_mm_day: '' }]), [])
  assert.deepEqual(validMonthlyResiduals([jan, { ...jan, reservoir_id: 2, period_start: '2026-02-01', period_end: '2026-02-28' }]), [])
})

test('tabelas de equipamentos expõem ações e rótulos para dispositivos móveis', () => {
  const html = render(LevelTab, { propertyId: 1, reservoirs: [reservoir], stations: [station], dashboard, onAddReservoir: noop })
  assert.match(html, /data-label="Reservatório"/)
  assert.match(html, /aria-label="Ações para Régua de teste"/)
  assert.match(html, /Excluir/)
})
