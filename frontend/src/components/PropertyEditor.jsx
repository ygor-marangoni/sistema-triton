import { useEffect, useRef, useState } from 'react'
import { Trash2 } from 'lucide-react'
import DisclosureSummary from './DisclosureSummary'
import AppDialog from './AppDialog'
import { errorMessage } from '../api/client'

const fields = [
  { name: 'name', label: 'Nome', required: true },
  { name: 'cep', label: 'CEP', required: true },
  { name: 'city', label: 'Cidade', required: true },
  { name: 'state', label: 'UF', required: true, maxLength: 2 },
  { name: 'latitude', label: 'Latitude (graus decimais)', type: 'number', min: -90, max: 90, step: '0.000001' },
  { name: 'longitude', label: 'Longitude (graus decimais)', type: 'number', min: -180, max: 180, step: '0.000001' },
]

function valuesFrom(property) {
  return Object.fromEntries(fields.map(({ name }) => [name, String(property[name] ?? '')]))
}

export default function PropertyEditor({ property, busy, onSave, onArchive, open = false, onOpenChange }) {
  const [draft, setDraft] = useState(() => valuesFrom(property))
  const [confirmArchive, setConfirmArchive] = useState(false)
  const [archiveError, setArchiveError] = useState('')
  const disclosureRef = useRef(null)
  const saved = valuesFrom(property)
  const changed = fields.some(({ name }) => draft[name] !== saved[name])
  useEffect(() => { setDraft(valuesFrom(property)) }, [property])
  useEffect(() => {
    if (open) requestAnimationFrame(() => disclosureRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }))
  }, [open])

  async function archive() {
    setArchiveError('')
    try { await onArchive(); setConfirmArchive(false) }
    catch (error) { setArchiveError(errorMessage(error)) }
  }

  return <>
  <details ref={disclosureRef} className="edit-property" open={open} onToggle={(event) => onOpenChange?.(event.currentTarget.open)}><DisclosureSummary>Editar dados da propriedade</DisclosureSummary>
    <form className="form-content" onSubmit={onSave}>
      <div className="form-grid">{fields.map(({ label, name, ...attributes }) => <label className="field" key={name}><span>{label}</span><input name={name} {...attributes} value={draft[name]} onChange={(event) => setDraft((current) => ({ ...current, [name]: event.target.value }))} /></label>)}</div>
      <div className="property-edit-actions">{changed && <button type="button" className="button secondary" disabled={busy} onClick={() => setDraft(valuesFrom(property))}>Cancelar</button>}<button className="button primary" disabled={busy || !changed}>Salvar alteração</button><button type="button" className="button danger-button property-archive-button" disabled={busy} onClick={() => { setArchiveError(''); setConfirmArchive(true) }}><Trash2 size={15} aria-hidden="true" />Excluir propriedade</button></div>
    </form>
  </details>
  {confirmArchive && <AppDialog title="Excluir propriedade" busy={busy} onClose={() => setConfirmArchive(false)}><div className="app-dialog-form"><p>A propriedade sairá da lista. Leituras, vínculos e histórico serão preservados e ela poderá ser restaurada em “Arquivadas”.</p>{archiveError && <p className="app-dialog-error" role="alert">{archiveError}</p>}<div className="app-dialog-actions"><button type="button" className="button secondary" disabled={busy} onClick={() => setConfirmArchive(false)}>Cancelar</button><button type="button" className="button danger-button" disabled={busy} onClick={archive}>{busy ? 'Excluindo…' : 'Excluir propriedade'}</button></div></div></AppDialog>}
  </>
}
