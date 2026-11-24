import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Check, UploadCloud } from 'lucide-react'
import DisclosureSummary from './DisclosureSummary'
import { errorMessage } from '../api/client'
import { rulerImageService } from '../services/triton'

const localDateTime = () => {
  const value = new Date()
  value.setMinutes(value.getMinutes() - value.getTimezoneOffset())
  return value.toISOString().slice(0, 16)
}

const coordinateNames = {
  reference_1: 'Graduação 1',
  reference_2: 'Graduação 2',
  waterline: 'Linha d’água',
}

const methodLabels = {
  opencv_edges_manual_calibration: 'OpenCV · contornos, sem escala automática',
  pillow_decode_manual_calibration: 'Imagem decodificada · leitura manual necessária',
  reviewer_selected_individual_calibration: 'Calibração individual marcada na foto',
  manual_entry: 'Valor informado manualmente',
}

const methodLabel = (method) => methodLabels[method] || method

function StateMessage({ kind = 'info', children }) {
  return children ? <div className={`message ${kind}`} role="status">{children}</div> : null
}

export default function RulerImageReview({ propertyId, stations, onConfirmed }) {
  const [stationId, setStationId] = useState(String(stations[0]?.id || ''))
  const [stationSearch, setStationSearch] = useState('')
  const [reviews, setReviews] = useState([])
  const [active, setActive] = useState(null)
  const [previewUrl, setPreviewUrl] = useState('')
  const [history, setHistory] = useState([])
  const [selectedPoints, setSelectedPoints] = useState({})
  const [pointMode, setPointMode] = useState('reference_1')
  const [manualValue, setManualValue] = useState('')
  const [reference1Level, setReference1Level] = useState('')
  const [reference2Level, setReference2Level] = useState('')
  const [loadingList, setLoadingList] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [fileName, setFileName] = useState('')
  const [dragging, setDragging] = useState(false)
  const imageRef = useRef(null)
  const fileRef = useRef(null)

  const station = useMemo(() => stations.find((item) => String(item.id) === stationId), [stationId, stations])
  const matchingStations = useMemo(() => {
    const normalize = (value) => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
    const matches = stations.filter((item) => normalize(item.name).includes(normalize(stationSearch)))
    return station && !matches.some((item) => item.id === station.id) ? [station, ...matches] : matches
  }, [station, stationSearch, stations])

  const loadReviews = useCallback(async () => {
    if (!stationId) return
    setLoadingList(true)
    try {
      const { data } = await rulerImageService.list(stationId)
      setReviews(data)
      setError('')
    } catch (cause) {
      setError(errorMessage(cause))
    } finally {
      setLoadingList(false)
    }
  }, [stationId])

  useEffect(() => { loadReviews() }, [loadReviews, propertyId])
  useEffect(() => {
    setActive(null)
    setSelectedPoints({})
    setHistory([])
  }, [stationId])
  useEffect(() => {
    let objectUrl = ''
    let cancelled = false
    setPreviewUrl('')
    setHistory([])
    setSelectedPoints({})
    if (!active?.id) return undefined
    Promise.all([rulerImageService.image(active.id), rulerImageService.history(active.id)])
      .then(([imageResult, historyResult]) => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(imageResult.data)
        setPreviewUrl(objectUrl)
        setHistory(historyResult.data)
      })
      .catch((cause) => { if (!cancelled) setError(errorMessage(cause)) })
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [active?.id])

  function applyReview(review) {
    setActive(review)
    const level = review.status === 'confirmed' ? review.confirmed_level_m : review.suggested_level_m
    setManualValue(level == null ? '' : String(level))
    setError('')
    setNotice('')
  }

  async function refreshHistory(reviewId) {
    const { data } = await rulerImageService.history(reviewId)
    setHistory(data)
  }

  async function upload(event) {
    event.preventDefault()
    const formElement = event.currentTarget
    const form = new FormData(formElement)
    const file = form.get('file')
    if (!(file instanceof File) || file.size === 0) {
      setError('Selecione uma imagem para enviar.')
      return
    }
    setBusy(true); setError(''); setNotice('')
    try {
      const { data } = await rulerImageService.upload(stationId, file, new Date(form.get('captured_at')).toISOString())
      applyReview(data)
      await loadReviews()
      setNotice('Imagem original armazenada. A leitura está inconclusiva e aguarda calibração ou entrada manual.')
      formElement.reset()
      setFileName('')
    } catch (cause) {
      setError(errorMessage(cause))
    } finally { setBusy(false) }
  }

  function markPoint(event) {
    if (!imageRef.current || !active) return
    const bounds = imageRef.current.getBoundingClientRect()
    const x = (event.clientX - bounds.left) * (active.width_px / bounds.width)
    const y = (event.clientY - bounds.top) * (active.height_px / bounds.height)
    setSelectedPoints((current) => ({ ...current, [pointMode]: { x: Number(x.toFixed(2)), y: Number(y.toFixed(2)) } }))
  }

  async function calibrate() {
    if (!selectedPoints.reference_1 || !selectedPoints.reference_2 || !selectedPoints.waterline) {
      setError('Marque na imagem as duas graduações e a linha d’água antes de calibrar.')
      return
    }
    setBusy(true); setError(''); setNotice('')
    try {
      const payload = {
        reference_1: { ...selectedPoints.reference_1, level_m: Number(reference1Level) },
        reference_2: { ...selectedPoints.reference_2, level_m: Number(reference2Level) },
        waterline: selectedPoints.waterline,
      }
      const { data } = await rulerImageService.calibrate(active.id, payload)
      applyReview(data)
      await loadReviews()
      await refreshHistory(active.id)
      setNotice('Sugestão calibrada para esta imagem. Revise o valor antes de confirmar.')
    } catch (cause) { setError(errorMessage(cause)) } finally { setBusy(false) }
  }

  async function suggestManual(event) {
    event.preventDefault()
    setBusy(true); setError(''); setNotice('')
    try {
      const { data } = await rulerImageService.suggest(active.id, Number(manualValue))
      applyReview(data)
      await loadReviews()
      await refreshHistory(active.id)
      setNotice('Valor manual salvo como sugestão pendente de revisão. Ele ainda não é uma leitura da estação.')
    } catch (cause) { setError(errorMessage(cause)) } finally { setBusy(false) }
  }

  async function confirm() {
    setBusy(true); setError(''); setNotice('')
    try {
      const { data } = await rulerImageService.confirm(active.id, Number(manualValue))
      applyReview(data.review)
      await loadReviews()
      await refreshHistory(active.id)
      await onConfirmed?.(data.reading)
      setNotice(`Leitura de ${Number(data.reading.level_m).toLocaleString('pt-BR')} m confirmada e vinculada à captura ${new Date(data.reading.observed_at).toLocaleString('pt-BR')}.`)
    } catch (cause) { setError(errorMessage(cause)) } finally { setBusy(false) }
  }

  return <section className="ruler-review-panel" aria-labelledby="ruler-review-title">
    <div className="section-title">
      <div><p className="eyebrow">FOTO DA RÉGUA · REVISÃO HUMANA</p><h2 id="ruler-review-title">Leitura assistida por imagem</h2></div>
      <span className="status-tag warn">Sem escala universal</span>
    </div>
    <StateMessage kind="error">{error}</StateMessage>
    <StateMessage kind="success">{notice}</StateMessage>
    <StateMessage>O Triton guarda a foto original. Pixels só viram metros após calibração individual com duas graduações conhecidas. Nenhuma sugestão entra nas leituras da estação antes da confirmação.</StateMessage>

    <div className="two-column form-columns ruler-workspace">
      <form className="form-card" onSubmit={upload}>
        <h3>Enviar fotografia</h3>
        {stations.length > 10 && <label className="field"><span>Buscar estação</span><input value={stationSearch} onChange={(event) => setStationSearch(event.target.value)} placeholder="Digite o nome da estação" /></label>}
        <label className="field"><span>Estação</span><select value={stationId} onChange={(event) => setStationId(event.target.value)} required>{matchingStations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label className="field"><span>Data e hora observadas</span><input type="datetime-local" name="captured_at" defaultValue={localDateTime()} required /></label>
        <div className="reservoir-upload-field"><span>Imagem original</span><label className={`reservoir-upload ruler-upload${dragging ? ' is-dragging' : ''}`} onDragOver={(event) => { event.preventDefault(); if (!busy) setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); if (busy || !event.dataTransfer.files.length) return; try { fileRef.current.files = event.dataTransfer.files; setFileName(event.dataTransfer.files[0].name); setError('') } catch { setError('Selecione a imagem pelo campo de envio.') } }}><input ref={fileRef} name="file" type="file" accept="image/png,image/jpeg,image/webp" required disabled={busy} onChange={(event) => { setFileName(event.target.files?.[0]?.name || ''); setError('') }} /><span className="reservoir-upload-icon">{fileName ? <Check size={22} aria-hidden="true" /> : <UploadCloud size={22} aria-hidden="true" />}</span><strong>{fileName || 'Clique para selecionar ou arraste a imagem'}</strong><small>PNG, JPEG ou WebP estática · limite definido no servidor</small></label></div>
        <div className="form-actions"><button type="reset" className="button secondary" disabled={busy} onClick={() => { setFileName(''); setError('') }}>Cancelar</button><button className="button primary" disabled={busy || !stationId}>{busy ? 'Enviando e analisando…' : 'Enviar para revisão'}</button></div>
      </form>

      <div className="form-card">
        <h3>Imagens desta estação</h3>
        {loadingList ? <p className="muted">Carregando imagens…</p> : reviews.length === 0 ? <p className="empty-inline">Nenhuma fotografia enviada para esta estação.</p> : <div className="ruler-review-list">{reviews.map((review) => <button className={`ruler-review-row ${active?.id === review.id ? 'selected' : ''}`} type="button" key={review.id} onClick={() => applyReview(review)}><span><b>{review.original_name}</b><small>{new Date(review.captured_at).toLocaleString('pt-BR')} · {review.unit} · {methodLabel(review.method)}</small></span><span className={`status-tag ${review.status === 'confirmed' ? '' : 'warn'}`}>{review.status === 'confirmed' ? 'Confirmada' : review.status === 'pending_review' ? 'Pendente' : 'Inconclusiva'}</span></button>)}</div>}
      </div>
    </div>

    {active && <article className="form-card ruler-active-review">
      <div className="ruler-review-heading"><div><p className="eyebrow">ESTAÇÃO: {station?.name || `#${active.station_id}`}</p><h3>{active.original_name}</h3><p className="muted">Captura {new Date(active.captured_at).toLocaleString('pt-BR')} · {active.width_px} × {active.height_px} px · {active.unit}</p></div><span className={`status-tag ${active.status === 'confirmed' ? '' : 'warn'}`}>{active.status === 'confirmed' ? 'Confirmada' : active.status === 'pending_review' ? 'Pendente de revisão' : 'Inconclusiva'}</span></div>
      <StateMessage kind={active.status === 'inconclusive' ? 'warning' : 'info'}>{active.inconclusive_reason || (active.status === 'pending_review' ? 'Confira a foto, a unidade e a sugestão antes de confirmar.' : `Origem do valor: ${active.method}.`)}</StateMessage>
      {active.confidence != null && <p className="muted">Confiança registrada: {active.confidence} · não substitui a revisão humana.</p>}
      {previewUrl ? <div className="ruler-preview-layout"><div className="ruler-image-wrap"><img ref={imageRef} src={previewUrl} alt={`Imagem original ${active.original_name}`} onClick={markPoint} /><div className="ruler-points-overlay">{Object.entries(selectedPoints).map(([name, point]) => <span key={name} className={`ruler-point ${name}`} style={{ left: `${point.x / active.width_px * 100}%`, top: `${point.y / active.height_px * 100}%` }} title={coordinateNames[name]}>{name === 'reference_1' ? '1' : name === 'reference_2' ? '2' : 'Á'}</span>)}</div></div><div className="plain-panel ruler-calibration">
        <p className="eyebrow">CALIBRAÇÃO DESTA FOTO</p><p>Selecione uma função e clique no ponto correspondente da régua. Marque graduações com valor conhecido; não estime distâncias pela aparência.</p>
        <div className="ruler-point-actions">{Object.entries(coordinateNames).map(([name, label]) => <button type="button" className={`small-button ${pointMode === name ? 'active' : ''}`} key={name} onClick={() => setPointMode(name)}>{label}{selectedPoints[name] && <Check size={13} strokeWidth={2.2} aria-label="Ponto marcado" />}</button>)}</div>
        <div className="form-grid"><label className="field"><span>Graduação 1 (m)</span><input type="number" min="0" step="0.001" value={reference1Level} onChange={(e) => setReference1Level(e.target.value)} /></label><label className="field"><span>Graduação 2 (m)</span><input type="number" min="0" step="0.001" value={reference2Level} onChange={(e) => setReference2Level(e.target.value)} /></label></div>
        <button type="button" className="button secondary" onClick={calibrate} disabled={busy || !reference1Level || !reference2Level}>Calibrar esta imagem</button>
        <form className="ruler-manual-form" onSubmit={suggestManual}><label className="field"><span>Leitura manual/corrigida (m)</span><input type="number" min={station?.minimum_m || 0} max={station?.maximum_m} step="0.001" value={manualValue} onChange={(e) => setManualValue(e.target.value)} required /></label><div className="form-actions"><button type="button" className="button secondary" disabled={busy} onClick={() => setManualValue('')}>Cancelar</button><button className="button primary" disabled={busy}>{active.status === 'confirmed' ? 'Registrar correção pendente' : 'Salvar sugestão manual'}</button></div></form>
        <StateMessage kind="warning">Origem: {methodLabel(active.method)}. Processador: {active.analysis_details?.processor || 'validação Pillow'}. A análise não identifica sozinha a escala nem a linha d’água; revisão humana necessária.</StateMessage>
      </div></div> : <div className="empty-inline loading-inline"><span className="spinner" />Carregando pré-visualização privada…</div>}

      <div className="ruler-confirm-row"><label className="field"><span>Valor que será confirmado (m)</span><input type="number" min={station?.minimum_m || 0} max={station?.maximum_m} step="0.001" value={manualValue} onChange={(e) => setManualValue(e.target.value)} disabled={active.status !== 'pending_review'} /></label><button className="button primary" type="button" disabled={busy || active.status !== 'pending_review' || manualValue === ''} onClick={confirm}>{busy ? 'Salvando…' : 'Confirmar leitura revisada'}</button>{active.status === 'confirmed' && <span className="muted">Confirmada por usuário #{active.reviewed_by_id} em {new Date(active.reviewed_at).toLocaleString('pt-BR')}.</span>}</div>

      <details className="ruler-history"><DisclosureSummary>Histórico de revisão ({history.length})</DisclosureSummary>{history.length ? <ol>{history.map((entry) => <li key={entry.id}><b>{entry.action}</b><time>{new Date(entry.created_at).toLocaleString('pt-BR')}</time><small>Usuário #{entry.user_id} · antes: {JSON.stringify(entry.previous_values)} · depois: {JSON.stringify(entry.corrected_values)}</small></li>)}</ol> : <p className="muted">O histórico será carregado após selecionar a imagem.</p>}</details>
    </article>}
  </section>
}
