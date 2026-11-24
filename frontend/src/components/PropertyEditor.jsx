import { useEffect, useState } from 'react'
import DisclosureSummary from './DisclosureSummary'

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

export default function PropertyEditor({ property, busy, onSave }) {
  const [draft, setDraft] = useState(() => valuesFrom(property))
  const saved = valuesFrom(property)
  const changed = fields.some(({ name }) => draft[name] !== saved[name])
  useEffect(() => { setDraft(valuesFrom(property)) }, [property])

  return <details className="edit-property"><DisclosureSummary>Editar dados da propriedade</DisclosureSummary>
    <form className="form-content" onSubmit={onSave}>
      <div className="form-grid">{fields.map(({ label, name, ...attributes }) => <label className="field" key={name}><span>{label}</span><input name={name} {...attributes} value={draft[name]} onChange={(event) => setDraft((current) => ({ ...current, [name]: event.target.value }))} /></label>)}</div>
      <div className="property-edit-actions">{changed && <button type="button" className="button secondary" disabled={busy} onClick={() => setDraft(valuesFrom(property))}>Cancelar</button>}<button className="button primary" disabled={busy || !changed}>Salvar alteração</button></div>
    </form>
  </details>
}
