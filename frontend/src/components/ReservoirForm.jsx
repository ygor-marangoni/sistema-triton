import { useEffect, useRef, useState } from 'react'
import { Check, UploadCloud } from 'lucide-react'
import { clearReservoirDraft, restoreReservoirDraft, saveReservoirDraft } from '../map/navigationState'

const sessionStorageOrNull = () => { try { return window.sessionStorage } catch { return null } }

function Field({ label, children }) {
  return <label className="reservoir-modal-field"><span>{label}</span>{children}</label>
}

export default function ReservoirForm({ userId, propertyId, busy, error, onSave, onOpenChange }) {
  const [draft, setDraft] = useState(() => restoreReservoirDraft(sessionStorageOrNull(), userId, propertyId))
  const [geometry, setGeometry] = useState(() => typeof draft.geometry === 'string' ? draft.geometry : '')
  const [fileName, setFileName] = useState(() => typeof draft.fileName === 'string' ? draft.fileName : '')
  const [fileError, setFileError] = useState('')
  const [reading, setReading] = useState(false)
  const [dragging, setDragging] = useState(false)
  const fileRef = useRef(null)
  const readerRef = useRef(null)
  const busyRef = useRef(busy)
  busyRef.current = busy

  function closeModal() {
    if (busyRef.current) return
    readerRef.current?.abort()
    readerRef.current = null
    clearReservoirDraft(sessionStorageOrNull(), userId, propertyId)
    onOpenChange(false)
  }

  useEffect(() => () => { readerRef.current?.abort() }, [])
  useEffect(() => { saveReservoirDraft(sessionStorageOrNull(), userId, propertyId, { ...draft, geometry, fileName }) }, [draft, geometry, fileName, userId, propertyId])

  function updateDraft(event) {
    const { name, value } = event.target
    setDraft((current) => ({ ...current, [name]: value }))
  }

  function loadFile(file) {
    setFileError('')
    if (!file) return
    setGeometry(''); setFileName('')
    if (file.size > 1_000_000 || !file.name.toLowerCase().endsWith('.kml')) {
      setFileError('Selecione um arquivo .kml de até 1 MB. KMZ não é aceito nesta versão.')
      if (fileRef.current) fileRef.current.value = ''
      return
    }
    const reader = new FileReader()
    readerRef.current = reader
    setReading(true)
    reader.onload = () => { if (readerRef.current !== reader) return; readerRef.current = null; setGeometry(String(reader.result || '')); setFileName(file.name); setReading(false) }
    reader.onerror = () => { if (readerRef.current !== reader) return; readerRef.current = null; setFileError('Não foi possível ler o arquivo KML.'); setReading(false) }
    reader.readAsText(file)
  }

  async function submit(event) {
    event.preventDefault()
    if (reading || busy) return
    if (geometry.trim().length < 20) { setFileError('Envie um KML válido ou cole a geometria antes de salvar.'); return }
    setFileError('')
    const form = new FormData(event.currentTarget)
    const saved = await onSave({ name: form.get('name'), base_width_m: form.get('base_width_m'), base_length_m: form.get('base_length_m'), top_width_m: form.get('top_width_m'), top_length_m: form.get('top_length_m'), height_m: form.get('height_m'), geometry_kml: geometry })
    if (saved) { clearReservoirDraft(sessionStorageOrNull(), userId, propertyId); onOpenChange(false) }
  }

  return <main className="reservoir-page" aria-labelledby="reservoir-modal-title">
        <header className="reservoir-modal-header"><div className="reservoir-modal-art"><img src="/images/property-switcher.png" alt="" /></div><span>Cadastrar reservatório</span><h2 id="reservoir-modal-title">Dados do reservatório</h2><p>Informe as dimensões em metros e o perímetro da área.</p></header>
        <form className="reservoir-modal-form" onSubmit={submit}>
          <div className="reservoir-modal-body">
            <Field label="Nome do reservatório"><input name="name" value={draft.name || ''} onChange={updateDraft} required minLength="2" placeholder="Ex.: Reservatório principal" /></Field>
            <div className="reservoir-dimensions"><div className="reservoir-dimensions-heading"><strong>Dimensões</strong></div><div className="reservoir-dimension-grid"><Field label="Largura da base"><input type="number" name="base_width_m" value={draft.base_width_m || ''} onChange={updateDraft} step="0.001" min="0.001" placeholder="0,00 m" required /></Field><Field label="Comprimento da base"><input type="number" name="base_length_m" value={draft.base_length_m || ''} onChange={updateDraft} step="0.001" min="0.001" placeholder="0,00 m" required /></Field><Field label="Largura do topo"><input type="number" name="top_width_m" value={draft.top_width_m || ''} onChange={updateDraft} step="0.001" min="0.001" placeholder="0,00 m" required /></Field><Field label="Comprimento do topo"><input type="number" name="top_length_m" value={draft.top_length_m || ''} onChange={updateDraft} step="0.001" min="0.001" placeholder="0,00 m" required /></Field><Field label="Altura total"><input type="number" name="height_m" value={draft.height_m || ''} onChange={updateDraft} step="0.001" min="0.001" placeholder="0,00 m" required /></Field></div></div>
            <div className="reservoir-upload-field"><span>Perímetro do reservatório</span><label className={`reservoir-upload${dragging ? ' is-dragging' : ''}`} onDragOver={(event) => { event.preventDefault(); if (!busy && !reading) setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); if (!busy && !reading) loadFile(event.dataTransfer.files?.[0]) }}><input ref={fileRef} type="file" disabled={busy || reading} accept=".kml,application/vnd.google-earth.kml+xml" onChange={(event) => loadFile(event.target.files?.[0])} /><span className="reservoir-upload-icon">{fileName ? <Check size={22} aria-hidden="true" /> : <UploadCloud size={22} aria-hidden="true" />}</span><strong>{reading ? 'Lendo arquivo…' : fileName || 'Clique para selecionar ou arraste o arquivo'}</strong><small>Arquivo KML · até 1 MB</small></label><small>O arquivo deve conter o perímetro do reservatório. KMZ não é aceito nesta versão.</small></div>
            <details className="reservoir-manual-kml"><summary>Colar geometria KML manualmente</summary><label className="reservoir-modal-field"><span>Geometria KML</span><textarea rows="5" value={geometry} onChange={(event) => { setGeometry(event.target.value); setFileName(''); setFileError(''); if (fileRef.current) fileRef.current.value = '' }} placeholder="Cole o conteúdo do arquivo KML" /></label></details>
            {fileError && <p className="reservoir-modal-error" role="alert">{fileError}</p>}
            {error && <p className="reservoir-modal-error" role="alert">{error}</p>}
            <p className="reservoir-modal-note">O volume usa o modelo retangular com paredes planas. O perímetro, por si só, não define a relação entre nível e volume.</p>
          </div>
          <footer className="reservoir-modal-actions"><button type="button" className="button secondary" onClick={closeModal} disabled={busy}>Cancelar</button><button type="submit" className="button primary" disabled={busy || reading}>{busy ? 'Salvando…' : 'Salvar reservatório'}</button></footer>
        </form>
  </main>
}
