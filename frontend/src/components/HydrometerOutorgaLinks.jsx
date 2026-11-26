import { useEffect, useState } from 'react'
import { Link2, Plus, X } from 'lucide-react'
import { waterService } from '../services/triton'
import { IntegrationField, IntegrationNotice } from './IntegrationUI'

const localDateTime = () => {
  const value = new Date()
  value.setMinutes(value.getMinutes() - value.getTimezoneOffset())
  return value.toISOString().slice(0, 16)
}

export default function HydrometerOutorgaLinks({ meter, outorgas, onUpdated }) {
  const [links, setLinks] = useState([]), [error, setError] = useState(''), [notice, setNotice] = useState(''), [busy, setBusy] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0), [closeAt, setCloseAt] = useState(localDateTime())

  useEffect(() => {
    let active = true
    waterService.meterOutorgaLinks(meter.id).then(({ data }) => { if (active) { setLinks(data); setError('') } })
      .catch((e) => { if (active) setError(e.response?.data?.detail || 'Não foi possível carregar os vínculos.') })
    return () => { active = false }
  }, [meter.id, refreshKey])

  async function create(event) {
    event.preventDefault()
    const values = new FormData(event.currentTarget)
    setBusy(true)
    try {
      await waterService.createMeterOutorgaLink(meter.id, {
        outorga_id: Number(values.get('outorga_id')),
        valid_from_at: new Date(values.get('valid_from_at')).toISOString(),
        valid_until_at: values.get('valid_until_at') ? new Date(values.get('valid_until_at')).toISOString() : null,
      })
      setNotice('Vínculo temporal registrado no histórico.')
      setError(''); setRefreshKey((key) => key + 1); if (onUpdated) await onUpdated()
    } catch (e) { setError(e.response?.data?.detail || 'Não foi possível registrar o vínculo.') }
    finally { setBusy(false) }
  }

  async function close(link) {
    setBusy(true)
    try {
      await waterService.closeMeterOutorgaLink(link.id, { valid_until_at: new Date(closeAt).toISOString() })
      setNotice('Fim da vigência registrado. O histórico das leituras foi preservado.')
      setError(''); setRefreshKey((key) => key + 1); if (onUpdated) await onUpdated()
    } catch (e) { setError(e.response?.data?.detail || 'Não foi possível encerrar o vínculo.') }
    finally { setBusy(false) }
  }

  return <section className="integration-link-management" aria-label={`Vínculos de outorga de ${meter.name}`}>
    <header><span className="integration-row-icon"><Link2 size={17} aria-hidden="true" /></span><div><h4>Vigência da outorga por leitura</h4><p>O vínculo só vale para intervalos inteiramente contidos na vigência.</p></div></header>
    <IntegrationNotice type="error">{error}</IntegrationNotice><IntegrationNotice type="success">{notice}</IntegrationNotice>
    {links.length > 0 ? <ol className="integration-link-list">{links.map((link) => <li key={link.id}><div><strong>{outorgas.find((permit) => permit.id === link.outorga_id)?.name || `Outorga #${link.outorga_id}`}</strong><span>{new Date(link.valid_from_at).toLocaleString('pt-BR')} – {link.valid_until_at ? new Date(link.valid_until_at).toLocaleString('pt-BR') : 'vigente sem data final'}</span><small>Registrado por usuário #{link.created_by_id} · {new Date(link.created_at).toLocaleString('pt-BR')}</small></div>{!link.valid_until_at && <button type="button" className="integration-text-button" disabled={busy} onClick={() => close(link)}><X size={14} />Encerrar neste horário</button>}</li>)}</ol> : <p className="integration-link-empty">Este hidrômetro ainda não tem vínculo temporal confirmado. A associação atual do cadastro não será aplicada a leituras antigas.</p>}
    <form className="integration-link-form" onSubmit={create}><IntegrationField label="Outorga"><select name="outorga_id" required defaultValue=""><option value="" disabled>Selecione a outorga</option>{outorgas.map((permit) => <option value={permit.id} key={permit.id}>{permit.name} · {permit.permit_number}</option>)}</select></IntegrationField><IntegrationField label="Início da vigência"><input type="datetime-local" name="valid_from_at" defaultValue={localDateTime()} required /></IntegrationField><IntegrationField label="Fim da vigência"><input type="datetime-local" name="valid_until_at" /></IntegrationField><button className="button primary" disabled={busy}><Plus size={15} />Registrar vínculo</button></form>
    {links.some((link) => !link.valid_until_at) && <label className="integration-link-close-time"><span>Encerrar vínculo aberto em</span><input type="datetime-local" value={closeAt} onChange={(event) => setCloseAt(event.target.value)} /></label>}
  </section>
}
