import { useCallback, useEffect, useState } from 'react'
import { errorMessage } from '../api/client'
import { meteorologyService } from '../services/triton'

const variableNames = {
  temperature_air: 'Temperatura do ar',
  relative_humidity: 'Umidade relativa',
  wind_speed: 'Velocidade do vento',
  wind_direction: 'Direção do vento',
  precipitation: 'Precipitação',
  solar_radiation: 'Radiação solar',
}
const coreVariables = ['temperature_air', 'relative_humidity', 'wind_speed', 'wind_direction', 'precipitation']

const formatDate = (value) => value ? new Date(value).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short', timeZone: 'UTC' }) + ' UTC' : 'Sem registro'
const formatValue = (value) => value == null ? '—' : Number(value).toLocaleString('pt-BR', { maximumFractionDigits: 3 })

function Message({ kind = 'info', children }) {
  return children ? <div className={`message ${kind}`} role={kind === 'error' ? 'alert' : 'status'}>{children}</div> : null
}

function Field({ label, children, hint }) {
  return <label className="field"><span>{label}</span>{children}{hint && <small>{hint}</small>}</label>
}

export default function MeteorologyTab({ propertyId }) {
  const [weather, setWeather] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [noticeKind, setNoticeKind] = useState('success')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await meteorologyService.get(propertyId)
      setWeather(data)
      setError('')
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setLoading(false)
    }
  }, [propertyId])

  useEffect(() => { load() }, [load])

  async function saveStation(event) {
    event.preventDefault(); setSaving(true); setError(''); setNotice(''); setNoticeKind('success')
    const form = new FormData(event.currentTarget)
    const data = Object.fromEntries(form.entries())
    try {
      await meteorologyService.setStation(propertyId, {
        station_code: data.station_code.trim(), name: data.name.trim(),
        city: data.city.trim() || null, state: data.state.trim().toUpperCase() || null,
        latitude: data.latitude ? Number(data.latitude) : null,
        longitude: data.longitude ? Number(data.longitude) : null,
      })
      setNotice('Estação associada.')
      await load()
    } catch (e) { setError(errorMessage(e)) } finally { setSaving(false) }
  }

  async function sync(event) {
    event.preventDefault(); setSyncing(true); setError(''); setNotice('')
    const year = Number(new FormData(event.currentTarget).get('year'))
    try {
      const { data } = await meteorologyService.sync(propertyId, year)
      setNotice(data.status === 'success' ? `${data.message} ${data.imported_count} observação(ões) nova(s).` : data.message)
      setNoticeKind(data.status === 'success' ? 'success' : 'warning')
      await load()
    } catch (e) { setError(errorMessage(e)) } finally { setSyncing(false) }
  }

  const station = weather?.station
  const isDemo = weather?.is_demo === true
  const latest = weather?.latest_observations || []
  const latestByVariable = new Map(latest.map((item) => [item.variable, item]))
  const displayVariables = [...coreVariables, ...(weather?.configured_variables?.includes('solar_radiation') ? ['solar_radiation'] : [])]
  const latestCollected = weather?.last_collection?.finished_at || weather?.last_collected_at

  return <div className="monitor-page weather-page">
    <header className="monitor-heading"><div><p className="eyebrow">METEOROLOGIA</p><h2>{isDemo ? 'Meteorologia demonstrativa' : 'Dados do INMET'}</h2><p>{isDemo ? 'Visualização com dados sintéticos, sem coleta oficial.' : 'Consulte as observações da estação associada à propriedade.'}</p></div></header>
    <Message kind="error">{error}</Message><Message kind={noticeKind}>{notice}</Message>
    {loading ? <div className="empty-inline loading-inline"><span className="spinner" />Consultando dados meteorológicos…</div> : <>
      <div className="weather-section-heading"><div><h3>Visão da estação</h3><p>Fonte e datas dos registros disponíveis.</p></div><span>{isDemo ? 'Demonstração · dados simulados' : 'INMET · arquivo anual'}</span></div>
      <div className="weather-summary">
        <div><span className="metric-label">ESTAÇÃO ASSOCIADA</span><strong>{station?.name || 'Nenhuma estação'}</strong><small>{station ? `Código informado: ${station.station_code} · fonte ${station.source}` : 'Associe o código da estação usada pela propriedade.'}</small></div>
        <div><span className="metric-label">ÚLTIMA OBSERVAÇÃO</span><strong>{formatDate(weather?.last_observation_at)}</strong><small>{isDemo ? 'Horário de referência simulado em UTC.' : 'Horário da medição, armazenado em UTC.'}</small></div>
        <div><span className="metric-label">{isDemo ? 'GERAÇÃO DOS DADOS' : 'ÚLTIMA COLETA REGISTRADA'}</span><strong>{formatDate(latestCollected)}</strong><small>{isDemo ? 'Valores sintéticos; nenhuma coleta externa.' : weather?.last_collection ? `Arquivo ${weather.last_collection.requested_year || '—'} · coleta ${weather.last_collection.status} · ${weather.last_collection.imported_count} novo(s)` : 'Nenhuma coleta registrada.'}</small></div>
      </div>
      {station && <div className="weather-variable-grid">{displayVariables.map((variable) => { const item = latestByVariable.get(variable); return <article className={`weather-variable ${item ? '' : 'missing'}`} key={variable}><span className="metric-label">{variableNames[variable]}</span>{item ? <><strong>{formatValue(item.value)} <small>{item.unit}</small></strong><span>Observado {formatDate(item.observed_at)}</span></> : <><strong>Sem observação</strong><span>Ausência de registro; nenhum zero foi presumido.</span></>}</article> })}</div>}
      {weather?.last_collection?.status === 'failed' && <Message kind="warning">A consulta mais recente falhou. Os registros anteriormente armazenados foram preservados. {weather.last_collection.message}</Message>}
      {isDemo ? <div className="weather-disclosure"><p><b>Modo demonstração.</b> Todos os valores desta página são simulados para visualizar a interface. Nenhuma informação foi coletada do INMET.</p></div> : <>
      <div className="weather-section-heading weather-setup-heading"><div><h3>Estação e coleta</h3><p>Associe uma estação e importe as observações do arquivo oficial.</p></div></div>
      <div className="two-column weather-forms">
        <form className="form-card" onSubmit={saveStation}><h3>{station ? 'Atualizar estação associada' : 'Associar estação'}</h3><Field label="Código exato da estação"><input name="station_code" required pattern="[A-Za-z0-9._-]+" defaultValue={station?.station_code || ''} /></Field><Field label="Nome para exibição"><input name="name" required minLength="2" defaultValue={station?.name || ''} /></Field><div className="form-grid"><Field label="Município (opcional)"><input name="city" defaultValue={station?.city || ''} /></Field><Field label="UF (opcional)"><input name="state" maxLength="2" defaultValue={station?.state || ''} /></Field></div><div className="form-grid"><Field label="Latitude decimal (opcional)"><input name="latitude" type="number" min="-90" max="90" step="0.000001" defaultValue={station?.latitude ?? ''} /></Field><Field label="Longitude decimal (opcional)"><input name="longitude" type="number" min="-180" max="180" step="0.000001" defaultValue={station?.longitude ?? ''} /></Field></div><div className="form-actions"><button type="reset" className="button secondary" disabled={saving}>Cancelar</button><button className="button primary" disabled={saving}>{saving ? 'Salvando…' : 'Salvar estação'}</button></div></form>
        <form className="form-card" onSubmit={sync}><h3>Importar arquivo anual</h3><Field label="Ano do arquivo oficial"><select name="year" defaultValue={new Date().getUTCFullYear()}>{Array.from({ length: new Date().getUTCFullYear() - 1999 }, (_, i) => new Date().getUTCFullYear() - i).map((year) => <option key={year} value={year}>{year}</option>)}</select></Field><button className="button primary" disabled={syncing || !station}>{syncing ? 'Consultando INMET…' : 'Sincronizar arquivo oficial'}</button></form>
      </div>
      </>}
      {weather?.recent_observations?.length > 0 && <div className="plain-panel weather-history"><div className="section-title compact"><div><p className="eyebrow">{isDemo ? 'HISTÓRICO SIMULADO' : 'HISTÓRICO IMPORTADO'}</p><h2>Observações recentes</h2></div><span className="status-tag">{isDemo ? 'UTC · simulação' : 'UTC · INMET · bruto'}</span></div><div className="table-wrap responsive-data-wrap"><table className="responsive-data-table"><thead><tr><th>Variável</th><th>Valor</th><th>Observado (UTC)</th><th>{isDemo ? 'Gerado (UTC)' : 'Coletado (UTC)'}</th><th>Qualidade</th></tr></thead><tbody>{weather.recent_observations.map((item) => <tr key={item.id}><td data-label="Variável">{variableNames[item.variable] || item.variable}</td><td data-label="Valor">{formatValue(item.value)} {item.unit}</td><td data-label="Observado (UTC)">{formatDate(item.observed_at)}</td><td data-label={isDemo ? 'Gerado (UTC)' : 'Coletado (UTC)'}>{formatDate(item.collected_at)}</td><td data-label="Qualidade">{item.quality}</td></tr>)}</tbody></table></div></div>}
    </>}
  </div>
}
