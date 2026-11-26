import { useState } from 'react'
import { Check, X } from 'lucide-react'
import { waterService } from '../services/triton'
import { IntegrationField, IntegrationNotice } from './IntegrationUI'

export default function HydrometerReadingReview({ meter, reading, onCancel, onComplete }) {
  const [note, setNote] = useState(''), [confirmed, setConfirmed] = useState(false), [error, setError] = useState(''), [busy, setBusy] = useState(false)
  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    try {
      await waterService.reviewMeterReading(reading.id, { approved: true, note: note.trim() })
      await onComplete()
    } catch (e) { setError(e.response?.data?.detail || 'Não foi possível revisar esta leitura.') }
    finally { setBusy(false) }
  }
  return <section className="integration-reading-review" aria-label="Revisar leitura de hidrômetro">
    <header><div><p className="integration-eyebrow">REVISÃO DE LEITURA</p><h4>{meter.name}</h4></div><button type="button" className="integration-icon-button" aria-label="Fechar revisão" onClick={onCancel}><X size={16} /></button></header>
    <dl><div><dt>Volume</dt><dd>{reading.volume_m3 == null ? 'Indisponível' : `${Number(reading.volume_m3).toLocaleString('pt-BR')} m³`}</dd></div><div><dt>Intervalo</dt><dd>{reading.interval_start_at ? `${new Date(reading.interval_start_at).toLocaleString('pt-BR')} – ${new Date(reading.observed_at).toLocaleString('pt-BR')}` : 'Sem início registrado'}</dd></div><div><dt>Origem</dt><dd>{reading.source} · {reading.quality}</dd></div></dl>
    <IntegrationNotice type="error">{error}</IntegrationNotice>
    <form onSubmit={submit}><IntegrationField label="Observação da revisão"><textarea value={note} onChange={(event) => setNote(event.target.value)} rows={2} required placeholder="Registre como o valor e o intervalo foram conferidos." /></IntegrationField><label className="integration-review-confirm"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} required /><span>Conferi a origem, a unidade, o volume e os horários deste intervalo.</span></label><div><button type="button" className="button secondary" onClick={onCancel}>Cancelar</button><button className="button primary" disabled={busy || !confirmed || !note.trim()}><Check size={15} />Aprovar leitura</button></div></form>
  </section>
}
