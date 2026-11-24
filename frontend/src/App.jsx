import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Activity, AlertCircle, AlertTriangle, ArrowLeftToLine, ArrowRight, ArrowRightToLine, ArrowUpRight, Bell, Check, CloudSun, Droplets, FileText, Gauge, Home, Info, LayoutDashboard, LogOut, MapPin, Plus, RefreshCw, Search, Waves, Zap } from 'lucide-react'
import { adminService, alertService, authService, propertyService, waterService } from './services/triton'
import { errorMessage } from './api/client'
import BrandMark from './components/BrandMark'
import AuthHero from './components/AuthHero'
import DisclosureSummary from './components/DisclosureSummary'
import PropertySwitcher from './components/PropertySwitcher'
import AlertStatusSelect from './components/AlertStatusSelect'
import ReservoirForm from './components/ReservoirForm'
import EvaporationTab from './components/EvaporationTab'
import HydrometerTab from './components/HydrometerTab'
import LevelTab from './components/LevelTab'
import MonitoringEmptyState from './components/MonitoringEmptyState'
import ReservoirBanner from './components/ReservoirBanner'
import PropertyEditor from './components/PropertyEditor'
import PropertyCreatePage from './components/PropertyCreatePage'
import Toast from './components/Toast'
import MeteorologyTab from './components/MeteorologyTab'
import RulerImageReview from './components/RulerImageReview'
import { findMapProperty } from './map/mapUtils'
import { restorePropertySelection, savePropertySelection } from './map/propertySelection'
import { restoreNavigation, saveNavigation } from './map/navigationState'
import { createPropertyRequestGuard } from './services/propertyRequestGuard'

const PropertyMapPage = lazy(() => import('./components/PropertyMapPage'))

const months = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
const brl = (n) => n == null ? '—' : Number(n).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
const number = (n, digits = 1) => n == null ? '—' : Number(n).toLocaleString('pt-BR', { maximumFractionDigits: digits })
const localDateTime = () => { const d = new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 16) }
const localSelectionStorage = () => { try { return window.localStorage } catch { return null } }
const sessionNavigationStorage = () => { try { return window.sessionStorage } catch { return null } }

function Field({ label, children, hint }) {
  return <label className="field"><span>{label}</span>{children}{hint && <small>{hint}</small>}</label>
}

function Message({ kind = 'info', children }) {
  if (!children) return null
  return <div className={`message ${kind}`} role="status">{children}</div>
}

function AlertSeverityIcon({ severity }) {
  const Icon = severity === 'critical' ? AlertCircle : severity === 'warning' ? AlertTriangle : Info
  return <Icon className="alert-glyph" size={17} strokeWidth={2} aria-hidden="true" />
}

function dashboardActivity(dashboard) {
  const levels = (dashboard?.latest_levels || []).filter((entry) => entry.latest?.observed_at).map((entry) => ({
    key: `level-${entry.reservoir_id}`,
    label: 'Nível do reservatório',
    equipment: entry.station?.name || entry.reservoir_name,
    value: entry.latest.level_m == null ? '—' : `${number(entry.latest.level_m, 2)} m`,
    source: entry.latest.source,
    observedAt: entry.latest.observed_at,
  }))
  const meters = (dashboard?.recent_hydrometers || []).flatMap(({ hydrometer, readings }) => (readings || []).slice(0, 1).filter((reading) => reading.observed_at).map((reading) => ({
    key: `meter-${hydrometer.id}`,
    label: hydrometer.kind === 'entrada' ? 'Hidrômetro de entrada' : 'Hidrômetro de saída',
    equipment: hydrometer.name,
    value: reading.volume_m3 == null ? '—' : `${number(reading.volume_m3, 2)} m³`,
    source: reading.source,
    observedAt: reading.observed_at,
  })))
  return [...levels, ...meters].sort((a, b) => new Date(b.observedAt) - new Date(a.observedAt))
}

function dataSourceLabel(source) {
  return ({ manual: 'informado manualmente', simulada: 'simulado', dispositivo: 'dispositivo', imagem_revisada: 'imagem revisada' })[source] || source || 'origem não informada'
}

function formatObservedAt(value) {
  return new Date(value).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

function formatLatestMeasurement(value) {
  const date = new Date(value)
  if (!Number.isFinite(date.getTime())) return 'Horário indisponível'
  const today = new Date()
  const isToday = date.getFullYear() === today.getFullYear() && date.getMonth() === today.getMonth() && date.getDate() === today.getDate()
  const dateLabel = isToday ? 'hoje' : date.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' })
  const timeLabel = date.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
  return `${dateLabel}, ${timeLabel}`
}

function App() {
  const [user, setUser] = useState(null)
  const [authReady, setAuthReady] = useState(false)
  const [navigationReady, setNavigationReady] = useState(false)
  const [properties, setProperties] = useState([])
  const [selected, setSelected] = useState(null)
  const [dashboard, setDashboard] = useState(null)
  const [outorgas, setOutorgas] = useState([])
  const [meters, setMeters] = useState([])
  const [stations, setStations] = useState([])
  const [tariffs, setTariffs] = useState([])
  const [energy, setEnergy] = useState(null)
  const [balance, setBalance] = useState(null)
  const [recentAlerts, setRecentAlerts] = useState([])
  const [propertyLoading, setPropertyLoading] = useState(false)
  const [propertyLoadError, setPropertyLoadError] = useState('')
  const [propertyDataId, setPropertyDataId] = useState(null)
  const [tab, setTab] = useState('Início')
  const [busy, setBusy] = useState(false)
  const [reservoirFormOpen, setReservoirFormOpen] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [authMode, setAuthMode] = useState('login')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const selectedPropertyId = selected?.id
  const selectedPropertyRef = useRef(selectedPropertyId)
  selectedPropertyRef.current = selectedPropertyId
  const propertyRequestRef = useRef(null)
  if (!propertyRequestRef.current) propertyRequestRef.current = createPropertyRequestGuard(() => selectedPropertyRef.current)

  const refreshProperties = useCallback(async (keepId, restoreForUserId) => {
    const response = await propertyService.list()
    setProperties(response.data)
    const found = restoreForUserId == null ? findMapProperty(response.data, keepId) : restorePropertySelection(localSelectionStorage(), restoreForUserId, response.data)
    if (restoreForUserId != null || keepId == null || selectedPropertyRef.current === keepId) setSelected(found)
    return found
  }, [])

  const refreshProperty = useCallback(async (id) => {
    if (!id || selectedPropertyRef.current !== id) return
    const isCurrent = propertyRequestRef.current.start(id)
    setPropertyLoading(true)
    setPropertyLoadError('')
    setDashboard(null); setOutorgas([]); setMeters([]); setStations([]); setTariffs([]); setEnergy(null); setBalance(null)
    try {
      const [overview, grants, pumps, levels, rates, energyResult, waterResult, alertResult] = await Promise.all([
        propertyService.dashboard(id), waterService.outorgas(id), waterService.meters(id), waterService.stations(id), waterService.tariffs(id), waterService.energy(id), waterService.evaporation(id), alertService.list(id, 'open'),
      ])
      if (!isCurrent()) return
      setDashboard(overview.data); setOutorgas(grants.data); setMeters(pumps.data); setStations(levels.data); setTariffs(rates.data); setEnergy(energyResult.data); setBalance(waterResult.data); setRecentAlerts(alertResult.data); setPropertyDataId(id)
    } catch (requestError) {
      if (!isCurrent()) return
      setPropertyLoadError(errorMessage(requestError))
      throw requestError
    } finally {
      if (isCurrent()) setPropertyLoading(false)
    }
  }, [])

  useEffect(() => { authService.session().then(async ({ data }) => {
    if (!data.authenticated) return
    setUser(data.user)
    const property = await refreshProperties(null, data.user.id)
    const state = restoreNavigation(sessionNavigationStorage(), data.user.id, property?.id)
    setTab(state.tab); setReservoirFormOpen(state.reservoirFormOpen)
  }).catch(() => {}).finally(() => { setNavigationReady(true); setAuthReady(true) }) }, [refreshProperties])
  useEffect(() => {
    if (!user?.id || !selected?.id) return
    savePropertySelection(localSelectionStorage(), user.id, selected.id)
  }, [user?.id, selected?.id])
  useEffect(() => {
    setRecentAlerts([])
    if (selectedPropertyId) refreshProperty(selectedPropertyId).catch(() => {})
    else setPropertyLoading(false)
    return () => { propertyRequestRef.current.invalidate() }
  }, [selectedPropertyId, refreshProperty])
  useEffect(() => {
    if (!navigationReady || !user?.id) return
    saveNavigation(sessionNavigationStorage(), user.id, selected?.id, tab, reservoirFormOpen)
  }, [navigationReady, user?.id, selected?.id, tab, reservoirFormOpen])
  const setReservoirModalOpen = useCallback((value) => { if (value) setError(''); setReservoirFormOpen(value) }, [])

  async function submitAuth(event) {
    event.preventDefault(); setBusy(true); setError(''); setNavigationReady(false)
    const form = new FormData(event.currentTarget)
    const data = Object.fromEntries(form.entries())
    try {
      const response = authMode === 'login' ? await authService.login({ email: data.email, password: data.password }) : await authService.register(data)
      setUser(response.data); const property = await refreshProperties(null, response.data.id); const state = restoreNavigation(sessionNavigationStorage(), response.data.id, property?.id); setTab(state.tab); setReservoirFormOpen(state.reservoirFormOpen); setNotice(authMode === 'login' ? 'Sessão iniciada.' : 'Conta criada. Cadastre sua primeira propriedade.'); setError('')
    } catch (e) { setError(errorMessage(e)) } finally { setBusy(false); setNavigationReady(true) }
  }

  async function signOut() {
    try { await authService.logout() } finally { setUser(null); setSelected(null); setProperties([]); setDashboard(null); setRecentAlerts([]) }
  }

  async function saveReservoir(data) {
    setBusy(true); setError(''); setNotice('')
    try {
      await propertyService.createReservoir(selected.id, data)
    } catch (e) {
      setError(errorMessage(e)); setBusy(false); return false
    }
    setNotice('Reservatório cadastrado; volume será calculado pela geometria retangular inclinada.')
    try { await refreshProperty(selected.id); await refreshProperties(selected.id) }
    catch (e) { setError(`Reservatório salvo, mas não foi possível atualizar os dados: ${errorMessage(e)}`) }
    finally { setBusy(false) }
    return true
  }

  async function action(fn, success, event) {
    event?.preventDefault(); setBusy(true); setError(''); setNotice('')
    try { await fn(new FormData(event?.currentTarget)); if (selected) await refreshProperty(selected.id); await refreshProperties(selected?.id); if (!selected && tab === 'Cadastro') setTab('Início'); setNotice(success); event?.currentTarget?.reset() }
    catch (e) { setError(errorMessage(e)) } finally { setBusy(false) }
  }

  const submit = (fn, success) => (event) => action(fn, success, event)

  async function changeStation(request, success) {
    setBusy(true); setError(''); setNotice('')
    try { await request() } catch (e) { setError(errorMessage(e)); setBusy(false); return false }
    setNotice(success)
    try { await refreshProperty(selected.id) } catch (e) { setError(`Alteração salva, mas não foi possível atualizar a tela: ${errorMessage(e)}`) }
    finally { setBusy(false) }
    return true
  }

  const navGroups = [
    { label: 'Propriedade', items: [{ label: 'Início', Icon: Home }] },
    { label: 'Monitoramento', items: [
      { label: 'Evaporação', Icon: Droplets },
      { label: 'Meteorologia', Icon: CloudSun },
    ] },
    { label: 'Registros', items: [
      { label: 'Outorga', Icon: FileText },
      { label: 'Hidrômetros', Icon: Gauge },
      { label: 'Estação / nível', Icon: Waves },
    ] },
    { label: 'Gestão', items: [
      { label: 'Energia', Icon: Zap },
      { label: 'Alertas', Icon: Bell },
    ] },
  ]
  const navigateTo = (label) => {
    setTab(label)
    setError('')
    setNotice('')
  }

  if (!authReady) return <div className="loading-screen"><span className="spinner" />Conectando ao Sistema Triton…</div>
  if (!user) return <main className={`auth-page${authMode === 'register' ? ' auth-page-register' : ''}`}>
    <section className="auth-panel">
      <BrandMark />
      <div className="auth-copy">
        <h1>{authMode === 'login' ? 'Acesse sua conta' : 'Crie sua conta'}</h1>
        <p className="muted">{authMode === 'login' ? 'Entre para acompanhar os dados das suas propriedades.' : 'Cadastre seus dados para começar a organizar sua operação.'}</p>
      </div>
      <form className="auth-form" onSubmit={submitAuth}>
        {authMode === 'register' && <div className="auth-register-fields"><Field label="Nome"><input required name="name" autoComplete="name" /></Field><Field label="CPF"><input required name="cpf" inputMode="numeric" placeholder="Somente os números" /></Field><Field label="Endereço comercial"><input required name="business_address" autoComplete="street-address" /></Field></div>}
        <Field label="E-mail"><input required name="email" type="email" autoComplete="email" placeholder="voce@exemplo.com" /></Field>
        <Field label="Senha" hint={authMode === 'register' ? 'Mínimo de 12 caracteres.' : null}><input required name="password" type="password" autoComplete={authMode === 'login' ? 'current-password' : 'new-password'} minLength={authMode === 'register' ? 12 : 1} /></Field>
        <Message kind="error">{error}</Message>
        <button className="button primary full" disabled={busy}>{busy ? 'Aguarde…' : authMode === 'login' ? 'Entrar' : 'Criar conta'}</button>
      </form>
      <p className="auth-switch">{authMode === 'login' ? 'Primeiro acesso?' : 'Já tem conta?'} <button className="text-button" type="button" onClick={() => { setAuthMode(authMode === 'login' ? 'register' : 'login'); setError('') }}>{authMode === 'login' ? 'Criar conta' : 'Entrar'}</button></p>
      <p className="privacy-note">Precisa recuperar o acesso? Fale com o administrador do sistema.</p>
    </section>
    <AuthHero />
  </main>

  if (reservoirFormOpen && selected) return <ReservoirForm userId={user.id} propertyId={selected.id} onOpenChange={setReservoirModalOpen} busy={busy} error={error} onSave={saveReservoir} />

  const propertyDataPending = propertyLoading || propertyDataId !== selectedPropertyId
  const propertyDataReady = !propertyDataPending && !propertyLoadError
  const recentActivity = dashboardActivity(dashboard)
  const latestActivity = recentActivity[0] || null

  return <div className={`app-shell${sidebarCollapsed ? " sidebar-collapsed" : ""}`}><aside className="sidebar"><button type="button" className="sidebar-toggle" onClick={() => setSidebarCollapsed((value) => !value)} aria-label={sidebarCollapsed ? "Expandir menu" : "Recolher menu"} aria-expanded={!sidebarCollapsed}>{sidebarCollapsed ? <ArrowRightToLine size={18} strokeWidth={1.7} /> : <ArrowLeftToLine size={18} strokeWidth={1.7} />}</button><a className="brand brand-wordmark" href="#top" aria-label="Sistema Triton" onClick={() => setTab('Início')}><BrandMark /></a><a className="brand brand-compact" href="#top" aria-label="Sistema Triton — início" onClick={() => setTab('Início')}><BrandMark small /></a><PropertySwitcher properties={properties} selected={selected} collapsed={sidebarCollapsed} onExpand={() => setSidebarCollapsed(false)} onSelect={(property) => { setSelected(property); setTab('Início'); setError(''); setNotice('') }} onCreate={() => { setSelected(null); setTab('Cadastro'); setError(''); setNotice('') }} /><nav className="side-nav" aria-label="Navegação principal">{navGroups.map((group) => <div className="nav-group" key={group.label}><span className="nav-group-label">{group.label}</span>{group.items.map(({ label, Icon }) => { const active = tab === label || (label === 'Início' && tab === 'Cadastro'); return <button key={label} title={label} aria-label={label} className={active ? 'active' : ''} aria-current={active ? 'page' : undefined} disabled={!selected && label !== 'Início'} onClick={() => navigateTo(label)}><Icon className="nav-icon" size={17} strokeWidth={1.8} aria-hidden="true" /><span>{label}</span></button> })}</div>)}</nav><div className="sidebar-bottom"><div className="sidebar-source" title={user.email === 'demo@example.com' ? 'Dados meteorológicos simulados' : 'Fonte meteorológica: INMET'}><CloudSun size={17} aria-hidden="true" /><span><b>Dados meteorológicos</b><small>{user.email === 'demo@example.com' ? 'Demonstração · simulação' : 'INMET · arquivo oficial'}</small></span></div><div className="sidebar-account"><span className="sidebar-account-avatar" aria-hidden="true">{user.name.slice(0, 1).toUpperCase()}</span><span className="sidebar-account-copy"><b>{user.name}</b><small>Minha conta</small></span><button type="button" className="sidebar-sign-out" title="Sair da conta" aria-label="Sair da conta" onClick={signOut}><LogOut size={17} strokeWidth={1.8} aria-hidden="true" /></button></div></div></aside>
  <main className="main-area" id="top"><header className={selected ? 'topbar topbar-property' : 'topbar'}>
  <div className="mobile-brand"><BrandMark /></div>
  {selected ? <div className="property-header-context"><h1>{selected.name}</h1><p>{selected.city} / {selected.state} <span aria-hidden="true">·</span> {tab}{user.email === 'demo@example.com' && <span className="demo-context-label">Dados de demonstração</span>}</p></div> : <div className="breadcrumb">{tab === 'Início' ? 'Início' : 'Seu espaço de trabalho'}</div>}
  {selected && <div className="property-header-reading" aria-live="polite"><span className="header-reading-label"><span className="header-reading-dot" aria-hidden="true" />Última medição</span>{propertyLoadError ? <span className="header-reading-value">Dados indisponíveis</span> : propertyDataPending ? <span className="header-reading-value">Carregando…</span> : latestActivity ? <time className="header-reading-value" dateTime={latestActivity.observedAt}>{formatLatestMeasurement(latestActivity.observedAt)}</time> : <span className="header-reading-value">Nenhuma leitura registrada</span>}</div>}
  <div className="profile"><span className="avatar">{user.name.slice(0, 1).toUpperCase()}</span><span className="profile-name">{user.name}</span><button className="text-button sign-out-button" onClick={signOut}><LogOut size={15} strokeWidth={1.9} aria-hidden="true" />Sair</button></div>
</header>
  <div className="content"><div className="toast-stack"><Toast kind="error" message={error} onDismiss={setError} /><Toast message={notice} onDismiss={setNotice} /></div>
  <div className="mobile-workspace-switcher"><PropertySwitcher properties={properties} selected={selected} collapsed={false} onSelect={(property) => { setSelected(property); setTab('Início'); setError(''); setNotice('') }} onCreate={() => { setSelected(null); setTab('Cadastro'); setError(''); setNotice('') }} /></div>
  <nav className="mobile-navigation" aria-label="Navegação principal"><div className="mobile-nav-scroll">{navGroups.flatMap((group) => group.items).map(({ label, Icon }) => { const active = tab === label || (label === 'Início' && tab === 'Cadastro'); return <button type="button" key={label} className={active ? 'active' : ''} aria-current={active ? 'page' : undefined} disabled={!selected && label !== 'Início'} onClick={() => navigateTo(label)}><Icon size={18} aria-hidden="true" /><span>{label}</span></button> })}</div></nav>
  {tab === 'Início' && <Suspense fallback={<div className="overview-loading"><span className="spinner" />Carregando início…</div>}><PropertyMapPage isDemo={user.email === "demo@example.com"} properties={properties} selectedProperty={selected} dashboard={dashboard} meters={meters} outorgas={outorgas} alerts={recentAlerts} latestActivity={latestActivity} propertyDataPending={propertyDataPending} propertyLoadError={propertyLoadError} onNavigate={navigateTo} onOpenProperty={(property) => { setSelected(property); setTab('Início') }} onAddProperty={() => { setSelected(null); setTab('Cadastro') }} onPropertyUpdated={(updated) => { setProperties((items) => items.map((item) => item.id === updated.id ? { ...item, ...updated } : item)); setSelected((current) => current?.id === updated.id ? { ...current, ...updated } : current) }} /></Suspense>}
  {!selected && tab === 'Cadastro' ? <PropertyCreatePage busy={busy} onCancel={() => { setSelected(restorePropertySelection(localSelectionStorage(), user.id, properties)); setTab('Início') }} onSubmit={submit((f) => propertyService.create({ name: f.get('name'), cep: f.get('cep'), city: f.get('city'), state: f.get('state').toUpperCase(), latitude: f.get('latitude') === '' ? null : Number(f.get('latitude')), longitude: f.get('longitude') === '' ? null : Number(f.get('longitude')) }), 'Propriedade cadastrada.')}>
    {user.role === 'admin' && <AdminPanel busy={busy} />}
  </PropertyCreatePage> : selected ? <>

    <section className="panel-section">
    {tab === 'Início' && <>
      <PropertyEditor key={selected.id} property={selected} busy={busy} onSave={submit((f) => propertyService.update(selected.id, { name: f.get('name'), cep: f.get('cep'), city: f.get('city'), state: f.get('state').toUpperCase(), latitude: f.get('latitude') === '' ? null : Number(f.get('latitude')), longitude: f.get('longitude') === '' ? null : Number(f.get('longitude')) }), 'Dados da propriedade atualizados.')} />
      {!propertyLoadError && propertyDataPending ? <div className="dashboard-loading"><span className="spinner" />Carregando registros desta propriedade…</div> : propertyLoadError ? <div className="dashboard-error" role="alert"><div><b>Não foi possível carregar o painel</b><p>{propertyLoadError}</p></div><button className="button secondary" onClick={() => refreshProperty(selected.id).catch(() => {})}>Tentar novamente</button></div> : <ReservoirBanner hasReservoirs={Boolean(dashboard?.reservoirs?.length)} onAddReservoir={() => setReservoirModalOpen(true)} />}
    </>}
    {tab !== 'Início' && !['Meteorologia', 'Alertas'].includes(tab) && (!propertyDataReady && (propertyLoadError ? <div className="dashboard-error" role="alert"><div><b>Não foi possível carregar os dados</b><p>{propertyLoadError}</p></div><button className="button secondary" onClick={() => refreshProperty(selected.id).catch(() => {})}>Tentar novamente</button></div> : <div className="dashboard-loading"><span className="spinner" />Carregando registros desta propriedade…</div>))}
    {propertyDataReady && tab === 'Evaporação' && <EvaporationTab balance={balance} onNavigate={navigateTo} />}
    {tab === 'Meteorologia' && <MeteorologyTab key={selected.id} propertyId={selected.id} />}
    {propertyDataReady && tab === 'Outorga' && <GrantTab outorgas={outorgas} comparisons={dashboard?.monthly_comparisons || []} selected={selected} busy={busy} onCreate={submit((f) => { const demands = months.map((_, i) => ({ month: i + 1, max_flow_m3_h: Number(f.get(`flow_${i}`)), daily_hours: Number(f.get(`hours_${i}`)), authorized_days: Number(f.get(`days_${i}`)), monthly_volume_m3: Number(f.get(`volume_${i}`)) })); return waterService.createOutorga({ property_id: selected.id, name: f.get('outorga_name'), permit_number: f.get('permit_number'), issued_on: f.get('issued_on'), valid_from: f.get('valid_from'), valid_until: f.get('valid_until'), water_body: f.get('water_body'), municipality: f.get('municipality'), coordinates_gms: f.get('coordinates_gms'), state: f.get('state').toUpperCase(), irrigated_area_ha: Number(f.get('irrigated_area_ha')), demands }) }, 'Outorga com 12 demandas cadastrada.')} onUpdate={async (outorgaId, month, data) => { setBusy(true); setError(''); try { await waterService.updateDemand(outorgaId, month, data); await refreshProperty(selected.id); setNotice('Limite mensal atualizado; revisão registrada no histórico.') } catch (e) { setError(errorMessage(e)) } finally { setBusy(false) } }} />}
    {propertyDataReady && tab === 'Hidrômetros' && <HydrometerTab meters={meters} outorgas={outorgas} dashboard={dashboard} busy={busy} onAddReservoir={() => setReservoirModalOpen(true)} onCreateMeter={submit((f) => waterService.createMeter({ reservoir_id: Number(f.get('reservoir_id')), outorga_id: f.get('outorga_id') ? Number(f.get('outorga_id')) : null, name: f.get('name'), kind: f.get('kind'), rated_power_kw: f.get('rated_power_kw') ? Number(f.get('rated_power_kw')) : null, rated_power_cv: f.get('rated_power_cv') ? Number(f.get('rated_power_cv')) : null }), 'Hidrômetro cadastrado.')} onRead={submit((f) => waterService.readMeter(Number(f.get('hydrometer_id')), { volume_m3: Number(f.get('volume_m3')), flow_m3_h: f.get('flow_m3_h') ? Number(f.get('flow_m3_h')) : null, observed_at: new Date(f.get('observed_at')).toISOString(), source: f.get('source'), quality: 'não revisada' }), 'Leitura de hidrômetro armazenada.')} />}
    {propertyDataReady && tab === 'Estação / nível' && <LevelTab propertyId={selected.id} error={error} onClearError={() => setError('')} reservoirs={dashboard?.reservoirs || []} stations={stations} dashboard={dashboard} busy={busy} onAddReservoir={() => setReservoirModalOpen(true)} onConfirmed={() => refreshProperty(selected.id)} onUpdateStation={(id, data) => changeStation(() => waterService.updateStation(id, data), 'Estação atualizada.')} onDeleteStation={(id) => changeStation(() => waterService.deleteStation(id), 'Estação excluída.')} onCreate={submit((f) => waterService.createStation({ reservoir_id: Number(f.get('reservoir_id')), name: f.get('name'), minimum_m: Number(f.get('minimum_m')), maximum_m: Number(f.get('maximum_m')) }), 'Estação cadastrada.')} onRead={submit((f) => waterService.readLevel(Number(f.get('station_id')), { level_m: Number(f.get('level_m')), observed_at: new Date(f.get('observed_at')).toISOString(), source: f.get('source'), quality: 'não revisada' }), 'Leitura de nível armazenada.')} />}
    {propertyDataReady && tab === 'Energia' && <EnergyTab tariffs={tariffs} energy={energy} selected={selected} busy={busy} onCreate={submit((f) => waterService.createTariff({ property_id: selected.id, distributor: f.get('distributor'), tariff_class: f.get('tariff_class'), modality: f.get('modality'), locality: f.get('locality') || null, value_brl_kwh: Number(f.get('value_brl_kwh')), valid_from: f.get('valid_from'), valid_until: f.get('valid_until') || null, source: 'manual' }), 'Tarifa manual cadastrada.')} />}
    {tab === 'Alertas' && <AlertsTab propertyId={selected.id} onUpdated={refreshProperty} />}
    </section>
  </> : null}
  <footer className="footer">Triton organiza informações para conferência. Estimativas dependem da qualidade e cobertura dos dados.</footer></div></main></div>
}

function AdminPanel({ busy }) {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState('')
  const [open, setOpen] = useState(false)
  const load = useCallback(() => { setLoading(true); adminService.users().then(({ data }) => { setUsers(data); setError('') }).catch((e) => setError(errorMessage(e))).finally(() => setLoading(false)) }, [])
  useEffect(() => { load() }, [load])
  async function create(event) {
    event.preventDefault(); setLoading(true); setError(''); setSaved('')
    const form = event.currentTarget
    const data = Object.fromEntries(new FormData(form).entries())
    try { await adminService.createUser(data); form.reset(); setSaved('Usuário criado.'); load() }
    catch (e) { setError(errorMessage(e)) } finally { setLoading(false) }
  }
  return <details className="form-disclosure admin-panel" open={open} onToggle={(e) => setOpen(e.currentTarget.open)}><DisclosureSummary>Administração de contas · {users.length} usuário(s)</DisclosureSummary><div className="form-content"><Message kind="error">{error}</Message><Message kind="success">{saved}</Message>{loading && users.length === 0 ? <p className="muted">Carregando contas…</p> : <div className="table-wrap responsive-data-wrap"><table className="responsive-data-table"><thead><tr><th>Nome</th><th>E-mail</th><th>CPF</th><th>Papel</th><th>Estado</th></tr></thead><tbody>{users.map(u => <tr key={u.id}><td data-label="Nome">{u.name}</td><td data-label="E-mail">{u.email}</td><td data-label="CPF">{u.cpf_masked}</td><td data-label="Papel">{u.role}</td><td data-label="Estado">{u.is_active ? 'Ativa' : 'Inativa'}</td></tr>)}</tbody></table></div>}<form className="form-card admin-create" onSubmit={create}><h3>Criar conta</h3><div className="form-grid"><Field label="Nome"><input name="name" required minLength="2" /></Field><Field label="CPF"><input name="cpf" required inputMode="numeric" /></Field><Field label="Endereço comercial"><input name="business_address" required /></Field><Field label="E-mail"><input name="email" type="email" required /></Field><Field label="Senha"><input name="password" type="password" minLength="12" required /></Field><Field label="Papel"><select name="role"><option value="user">Usuário</option><option value="admin">Administrador</option></select></Field></div><div className="form-actions"><button type="button" className="button secondary" disabled={busy || loading} onClick={(event) => { event.currentTarget.form.reset(); setOpen(false) }}>Cancelar</button><button className="button primary" disabled={busy || loading}>Criar conta</button></div><small>CPF é armazenado cifrado e listado mascarado; a senha recebe hash Argon2id.</small></form></div></details>
}

function GrantTab({ outorgas, comparisons, selected, busy, onCreate, onUpdate }) {
  const [editing, setEditing] = useState({})
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const normalize = (value) => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
  const filtered = outorgas.filter((item) => normalize(`${item.name} ${item.permit_number} ${item.water_body}`).includes(normalize(query)))
  const pages = Math.max(1, Math.ceil(filtered.length / 3))
  const current = Math.min(page, pages)
  const visible = filtered.slice((current - 1) * 3, current * 3)
  const formRef = useRef(null)
  const openForm = () => { if (formRef.current) { formRef.current.open = true; formRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' }) } }
  return <div className="monitor-page permit-page"><header className="monitor-heading"><div><p className="eyebrow">CAPTAÇÃO DE ÁGUA</p><h2>Outorgas da propriedade</h2><p>Organize os documentos e acompanhe os limites de captação cadastrados.</p></div><div className="level-heading-actions"><span className="monitor-status">{outorgas.length} {outorgas.length === 1 ? 'outorga cadastrada' : 'outorgas cadastradas'}</span>{outorgas.length > 0 && <button type="button" className="button secondary" onClick={openForm}><Plus size={16} aria-hidden="true" />Cadastrar outorga</button>}</div></header>
    <details ref={formRef} className="form-disclosure"><DisclosureSummary>Cadastrar outorga e 12 limites mensais</DisclosureSummary><form className="form-content" autoComplete="off" onSubmit={onCreate}><div className="form-grid"><Field label="Nome"><input name="outorga_name" autoComplete="off" placeholder="Ex.: Captação do Córrego São Bento" required /></Field><Field label="Número da portaria"><input name="permit_number" required /></Field><Field label="Data de emissão"><input type="date" name="issued_on" required /></Field><Field label="Início da vigência"><input type="date" name="valid_from" required /></Field><Field label="Fim da vigência"><input type="date" name="valid_until" required /></Field><Field label="Corpo hídrico"><input name="water_body" required /></Field><Field label="Município"><input name="municipality" required /></Field><Field label="Coordenadas (GMS)"><input name="coordinates_gms" required placeholder="18° 00′ 00″ S, 47° 00′ 00″ O" /></Field><Field label="UF"><input name="state" maxLength="2" required /></Field><Field label="Área irrigada (ha)"><input type="number" step="0.001" min="0.001" name="irrigated_area_ha" required /></Field></div><p className="eyebrow table-eyebrow">DEMANDAS MENSAIS</p><div className="table-wrap responsive-data-wrap"><table className="responsive-data-table"><thead><tr><th>Mês</th><th>Vazão m³/h</th><th>Horas/dia</th><th>Dias/mês</th><th>Volume máx. m³</th></tr></thead><tbody>{months.map((month, i) => <tr key={month}><td data-label="Mês">{month}</td><td data-label="Vazão m³/h"><input className="table-input" type="number" name={`flow_${i}`} min="0" step="0.001" required /></td><td data-label="Horas/dia"><input className="table-input" type="number" name={`hours_${i}`} min="0" max="24" step="0.1" required /></td><td data-label="Dias/mês"><input className="table-input" type="number" name={`days_${i}`} min="0" max="31" required /></td><td data-label="Volume máx. m³"><input className="table-input" type="number" name={`volume_${i}`} min="0" step="0.001" required /></td></tr>)}</tbody></table></div><Message kind="info">Cada linha precisa conferir vazão × horas × dias. Os dados extraídos de documento não são ativados automaticamente; confira e digite os valores.</Message><div className="form-actions"><button type="button" className="button secondary" disabled={busy} onClick={(event) => { event.currentTarget.form.reset(); event.currentTarget.closest("details").open = false }}>Cancelar</button><button className="button primary" disabled={busy}>Salvar outorga</button></div></form></details>
    {outorgas.length > 0 && <label className="level-search"><Search size={16} aria-hidden="true" /><span className="sr-only">Buscar outorga</span><input value={query} onChange={(event) => { setQuery(event.target.value); setPage(1) }} placeholder="Buscar outorga ou portaria" /></label>}
    {visible.map((o) => { const compare = comparisons.find((c) => c.outorga_id === o.id); return <article className="grant-panel" key={o.id}><div className="grant-head"><div><span className={`status-tag ${new Date(`${o.valid_until}T23:59:59`) >= new Date() ? '' : 'warn'}`}>{new Date(`${o.valid_until}T23:59:59`) >= new Date() ? 'Vigência cadastrada' : 'Vencida'}</span><h3>{o.name}</h3><p>{o.water_body} · Portaria {o.permit_number} · {o.municipality}/{o.state}</p></div><div className="grant-total"><span>Área irrigada declarada</span><b>{number(o.irrigated_area_ha)} ha</b></div></div>{compare && <div className="grant-month"><div className="section-title compact"><div><p className="eyebrow">COMPARAÇÃO / {months[compare.month-1].toUpperCase()} {compare.year}</p><h2>{compare.daily.length ? `${number(compare.measured_volume_m3)} m³ ${compare.is_demo ? "simulados até hoje" : "registrados"}` : "Sem volume medido"} · limite {number(compare.monthly_reference_limit_m3)} m³</h2></div><span className={`status-tag ${compare.is_demo ? '' : 'warn'}`}>{compare.is_demo ? 'Dados simulados' : 'Cobertura incompleta'}</span></div><div className="grant-breakdown"><span>Dias usados/autorizados <b>{compare.operating_days_used}/{compare.operating_days_authorized}</b></span><span>Sobra não transferível <b>{number(compare.non_transferable_surplus_m3)} m³</b></span><span>Extrapolado <b>{number(compare.extrapolated_m3)} m³</b></span><span>{compare.is_demo ? 'Dias sem leitura até hoje' : 'Dias sem leitura'} <b>{compare.missing_days}</b></span></div>{compare.daily.length > 0 && <div className="daily-lines">{compare.daily.map(d => <div key={d.date}><span>{d.date}</span><span>{number(d.volume_m3)} m³</span><span>{d.status}</span><span>Excesso {number(d.extrapolated_m3)} m³ · sobra {number(d.non_transferable_surplus_m3)} m³</span></div>)}</div>}<p className="table-note">{compare.notes}</p></div>}<div className="table-wrap responsive-data-wrap"><table className="responsive-data-table"><thead><tr><th>Mês</th><th>Vazão máx. m³/h</th><th>Horas/dia</th><th>Dias autorizados</th><th>Limite m³/mês</th><th /></tr></thead><tbody>{[...o.demands].sort((a,b) => a.month-b.month).map((d) => <tr key={d.month}><td data-label="Mês">{months[d.month-1]}</td><td data-label="Vazão máx. m³/h"><input className="table-input" type="number" min="0" step="0.001" defaultValue={d.max_flow_m3_h} onChange={(e) => setEditing({ ...editing, [`${o.id}_${d.month}`]: { ...(editing[`${o.id}_${d.month}`] || d), max_flow_m3_h: e.target.value } })} /></td><td data-label="Horas/dia"><input className="table-input" type="number" min="0" max="24" step="0.1" defaultValue={d.daily_hours} onChange={(e) => setEditing({ ...editing, [`${o.id}_${d.month}`]: { ...(editing[`${o.id}_${d.month}`] || d), daily_hours: e.target.value } })} /></td><td data-label="Dias autorizados"><input className="table-input" type="number" min="0" max="31" defaultValue={d.authorized_days} onChange={(e) => setEditing({ ...editing, [`${o.id}_${d.month}`]: { ...(editing[`${o.id}_${d.month}`] || d), authorized_days: e.target.value } })} /></td><td data-label="Limite m³/mês"><input className="table-input" type="number" min="0" step="0.001" defaultValue={d.monthly_volume_m3} onChange={(e) => setEditing({ ...editing, [`${o.id}_${d.month}`]: { ...(editing[`${o.id}_${d.month}`] || d), monthly_volume_m3: e.target.value } })} /></td><td data-label="Ação"><button className="small-button" disabled={busy} onClick={() => { const v = editing[`${o.id}_${d.month}`] || d; onUpdate(o.id, d.month, { max_flow_m3_h: Number(v.max_flow_m3_h), daily_hours: Number(v.daily_hours), authorized_days: Number(v.authorized_days), monthly_volume_m3: Number(v.monthly_volume_m3) }) }}>Salvar</button></td></tr>)}</tbody></table></div><p className="table-note">O limite mensal deve ser igual a vazão × horas × dias autorizados. Sobra diária não é transferida.</p></article>})}
    {outorgas.length > 0 && <div className="level-pagination"><span>{filtered.length} {filtered.length === 1 ? 'outorga' : 'outorgas'} · página {current} de {pages}</span><div><button type="button" className="small-button" disabled={current <= 1} onClick={() => setPage(current - 1)}>Anterior</button><button type="button" className="small-button" disabled={current >= pages} onClick={() => setPage(current + 1)}>Próxima</button></div></div>}
    {outorgas.length === 0 && <MonitoringEmptyState icon={FileText} label="OUTORGA" title="Comece pela outorga" description="Reúna a portaria e os limites mensais para acompanhar a captação da propriedade." note="A comparação depende de hidrômetros associados e leituras elegíveis." actionLabel="Cadastrar outorga" onAction={openForm} />}

  </div>
}

function EnergyTab({ tariffs, energy, selected, busy, onCreate }) {
  return (
    <div className="monitor-page energy-page">
      <header className="monitor-heading energy-heading">
        <div>
          <p className="eyebrow">ENERGIA</p>
          <h2>Cobrança de energia</h2>
          <p>Acompanhe a estimativa de bombeamento e as tarifas cadastradas.</p>
        </div>
        <span className="monitor-status">Tarifas informadas manualmente</span>
      </header>
      <div className="monitor-section-heading energy-summary-heading"><div><h3>Resumo do período</h3><p>Consumo e custo dependem dos registros e da tarifa aplicável.</p></div>{energy?.period?.start && energy?.period?.end && <span>{energy.period.start.split('-').reverse().join('/')} a {energy.period.end.split('-').reverse().join('/')}</span>}</div>
      <div className="energy-kpis">
        <article className="energy-kpi"><span className="energy-icon"><Zap size={18} strokeWidth={1.9} aria-hidden="true" /></span><div><span className="metric-label">ENERGIA ESTIMADA</span><strong>{energy?.energy_kwh == null ? 'Dados insuficientes' : `${number(energy.energy_kwh, 2)} kWh`}</strong><small>{energy?.energy_kwh == null ? 'Faltam dados compatíveis de operação.' : 'Consumo calculado no período.'}</small></div></article>
        <article className="energy-kpi"><span className="energy-icon"><FileText size={18} strokeWidth={1.9} aria-hidden="true" /></span><div><span className="metric-label">CUSTO ENERGÉTICO ESTIMADO</span><strong>{brl(energy?.estimated_cost_brl)}</strong><small>Energia estimada × tarifa aplicável.</small></div></article>
        <article className="energy-kpi"><span className="energy-icon"><Gauge size={18} strokeWidth={1.9} aria-hidden="true" /></span><div><span className="metric-label">TARIFA APLICÁVEL</span><strong>{!energy ? 'Indisponível' : energy.tariff_brl_kwh == null ? 'Sem tarifa para o período' : `${brl(energy.tariff_brl_kwh)} / kWh`}</strong><small>O valor depende da unidade consumidora e da vigência.</small></div></article>
      </div>
      <div className="energy-columns">
        <section className="plain-panel energy-panel">
          <div className="energy-panel-heading"><span className="energy-panel-icon"><Activity size={17} strokeWidth={1.9} aria-hidden="true" /></span><div><p className="eyebrow">MEMÓRIA DE CÁLCULO</p><h3>Premissas da estimativa</h3></div></div>
          <p className="energy-premise">{energy?.premises || 'Potência elétrica nominal × horas estimadas de operação.'}</p>
          {energy?.pumps?.length ? <div className="energy-pump-list">{energy.pumps.map((pump) => <div className="energy-pump-row" key={pump.hydrometer_id}><span><b>{pump.name}</b><small>{pump.status}</small></span><strong>{pump.kwh == null ? '—' : `${number(pump.kwh, 2)} kWh`}</strong></div>)}</div> : <div className="energy-empty"><Gauge size={17} strokeWidth={1.8} aria-hidden="true" /><span><b>Nenhuma bomba com estimativa disponível</b><small>Cadastre a potência e registre dados de operação para calcular o consumo.</small></span></div>}
          <Message kind="warning">Sem rendimento ou fator de carga conhecido, esses fatores não são presumidos. O custo não inclui cobrança pelo uso da água.</Message>
        </section>
        <section className="plain-panel energy-panel">
          <div className="energy-panel-heading"><span className="energy-panel-icon"><FileText size={17} strokeWidth={1.9} aria-hidden="true" /></span><div><p className="eyebrow">TARIFAS CADASTRADAS</p><h3>Origem e vigência</h3></div></div>
          {tariffs.length ? <div className="energy-tariff-list">{tariffs.map((tariff) => <div key={tariff.id} className="energy-tariff-row"><div><b>{tariff.distributor} · {tariff.tariff_class}</b><span>{tariff.modality}{tariff.locality ? ` · ${tariff.locality}` : ''}</span><small>Vigência {tariff.valid_from} a {tariff.valid_until || 'sem fim cadastrado'} · origem {tariff.source}</small></div><strong>{brl(tariff.value_brl_kwh)}<small>por kWh</small></strong></div>)}</div> : <div className="energy-empty"><FileText size={17} strokeWidth={1.8} aria-hidden="true" /><span><b>Nenhuma tarifa cadastrada</b><small>Informe o valor da unidade consumidora e o período aplicável.</small></span></div>}
        </section>
      </div>
      <details className="form-disclosure energy-disclosure"><DisclosureSummary><Plus size={15} strokeWidth={2} aria-hidden="true" />Cadastrar tarifa manual</DisclosureSummary><form className="form-content" onSubmit={onCreate}><div className="form-grid"><Field label="Distribuidora"><input name="distributor" required defaultValue="CEMIG (cadastro manual)" /></Field><Field label="Classe / subclasse"><input name="tariff_class" required placeholder="Informe conforme sua fatura" /></Field><Field label="Modalidade"><input name="modality" required placeholder="Convencional, horária etc." /></Field><Field label="Localidade"><input name="locality" /></Field><Field label="Valor R$/kWh"><input type="number" name="value_brl_kwh" min="0.000001" step="0.000001" required /></Field><Field label="Início da vigência"><input type="date" name="valid_from" required /></Field><Field label="Fim da vigência"><input type="date" name="valid_until" /></Field></div><Message kind="info">O Triton não consulta tarifa pública ainda. Insira o valor da unidade consumidora e informe o período aplicável.</Message><div className="form-actions"><button type="button" className="button secondary" disabled={busy} onClick={(event) => { event.currentTarget.form.reset(); event.currentTarget.closest("details").open = false }}>Cancelar</button><button className="button primary" disabled={busy}>Salvar tarifa</button></div></form></details>
    </div>
  )
}

function AlertsTab({ propertyId, onUpdated }) {
  const [alerts, setAlerts] = useState([])
  const [filter, setFilter] = useState('open')
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const load = useCallback(async () => {
    setLoading(true)
    try { const { data } = await alertService.list(propertyId, filter); setAlerts(data); setError('') }
    catch (e) { setError(errorMessage(e)) } finally { setLoading(false) }
  }, [filter, propertyId])
  useEffect(() => { load() }, [load])

  async function evaluate() {
    setBusy(true); setError(''); setNotice('')
    try {
      const { data } = await alertService.evaluate(propertyId)
      setNotice(`Avaliação concluída: ${data.created} novo(s), ${data.reopened} reaberto(s), ${data.automatically_resolved} condição(ões) resolvida(s) automaticamente.`)
      await onUpdated(propertyId)
      await load()
    } catch (e) { setError(errorMessage(e)) } finally { setBusy(false) }
  }

  async function resolve(alertId) {
    setBusy(true); setError(''); setNotice('')
    try { await alertService.resolve(alertId); setNotice('Alerta marcado como resolvido.'); await onUpdated(propertyId); await load() }
    catch (e) { setError(errorMessage(e)) } finally { setBusy(false) }
  }

  return <div className="monitor-page alerts-page"><header className="monitor-heading"><div><p className="eyebrow">ACOMPANHAMENTO</p><h2>Alertas e pendências</h2><p>Consulte as condições identificadas nos registros da propriedade.</p></div><button className="button primary" onClick={evaluate} disabled={busy}><RefreshCw size={16} strokeWidth={1.9} aria-hidden="true" />{busy ? 'Avaliando…' : 'Avaliar dados atuais'}</button></header>
    <div className="alerts-context"><span className="alerts-context-icon"><Bell size={19} aria-hidden="true" /></span><div><strong>Avaliação sob demanda</strong><p>Os alertas são avaliados manualmente com os dados já salvos. A avaliação não consulta fontes externas nem confirma regularidade oficial.</p></div></div>
    <div className="alerts-toolbar"><div className="alerts-filter-label"><span>Exibir</span><AlertStatusSelect value={filter} onChange={setFilter} /></div><span className="monitor-status">Atualização manual</span></div>
    <Message kind="error">{error}</Message><div className="toast-stack"><Toast message={notice} onDismiss={setNotice} /></div>
    {loading ? <div className="empty-inline loading-inline"><span className="spinner" />Carregando alertas…</div> : error && alerts.length === 0 ? null : alerts.length === 0 ? <div className="empty-state alerts-empty"><div className="empty-icon"><Check size={20} strokeWidth={2} aria-hidden="true" /></div><h2>{filter === 'open' ? 'Nenhum alerta em aberto' : 'Nenhum alerta resolvido'}</h2><p>{filter === 'open' ? 'Avalie os dados atuais para procurar medições atrasadas, captação pendente ou extrapolações diárias.' : 'Alertas resolvidos aparecerão aqui com seu histórico.'}</p></div> : <div className="alert-list">{alerts.map((alert) => <article className="alert-item" key={alert.id}><div className={`alert-severity ${alert.severity}`}><AlertSeverityIcon severity={alert.severity} /></div><div className="alert-content"><div className="alert-heading"><div><span className={`severity-label ${alert.severity}`}>{alert.severity === 'critical' ? 'Crítico' : alert.severity === 'warning' ? 'Atenção' : 'Informativo'}</span><h3>{alert.rule}</h3></div></div><p className="alert-origin">{alert.origin} · registrado {new Date(alert.occurred_at).toLocaleString('pt-BR')}</p><AlertDetails details={alert.details} />{alert.resolution_history?.length > 0 && <ol className="resolution-history" aria-label="Histórico do alerta">{alert.resolution_history.map((entry, index) => <li key={`${entry.at}-${index}`}><span>{entry.event === 'reopened' ? 'Reaberto' : entry.event === 'resolved_automatically' ? 'Resolvido automaticamente' : 'Marcado como resolvido'}</span><time dateTime={entry.at}>{new Date(entry.at).toLocaleString('pt-BR')}</time>{(entry.note || entry.reason) && <p>{entry.note || entry.reason}</p>}</li>)}</ol>}</div><div className="alert-actions"><span className={`status-tag ${alert.status === 'resolved' ? '' : 'warn'}`}>{alert.status === 'resolved' && <Check size={13} aria-hidden="true" />}{alert.status === 'resolved' ? 'Resolvido' : 'Em aberto'}</span>{alert.status === 'open' && <button className="small-button resolve-button" disabled={busy} onClick={() => resolve(alert.id)}>Marcar resolvido</button>}</div></article>)}</div>}
  </div>
}

function AlertDetails({ details = {} }) {
  if (details.operating_date) return <p className="alert-detail">{details.operating_date}: {number(details.measured_volume_m3)} m³ medidos; {number(details.extrapolated_m3)} m³ extrapolados · {details.operating_days_used}/{details.operating_days_authorized} dias autorizados usados.</p>
  if (details.last_observed_at) return <p className="alert-detail">{details.component_name}: última observação {new Date(details.last_observed_at).toLocaleString('pt-BR')} · limite {details.threshold_hours} h.</p>
  if (details.reading_id) return <p className="alert-detail">{details.component_name}: {details.quality} · origem {details.source} · observado {new Date(details.observed_at).toLocaleString('pt-BR')}.</p>
  if (details.threshold_hours) return <p className="alert-detail">{details.component_name}: sem leitura válida há {number(details.hours_without_valid_reading, 1)} h · limite {details.threshold_hours} h.</p>
  return <p className="alert-detail">{details.message || details.component_name || 'Confira o registro relacionado.'}</p>
}

export { GrantTab, LevelTab, EnergyTab, AlertsTab }
export default App
