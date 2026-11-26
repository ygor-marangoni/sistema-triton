import { useCallback, useEffect, useState } from 'react'
import { ArrowDownToLine, Check, FileSearch, FileText, History, LockKeyhole, Paperclip, UploadCloud, X } from 'lucide-react'
import { waterService } from '../services/triton'
import { IntegrationEmpty, IntegrationField, IntegrationHeader, IntegrationNotice, IntegrationPagination } from './IntegrationUI'

const labels = { holder: 'Titular', permit_number: 'Número da outorga', water_body: 'Corpo hídrico', valid_from: 'Início da vigência', valid_until: 'Fim da vigência', monthly_demands: 'Demandas mensais' }
const statuses = { pending_review: 'Aguardando revisão', approved: 'Revisão aprovada', ocr_unavailable: 'Texto não localizado', pendente: 'Pendente' }
export const documentErrorMessage = (error) => {
  const detail = error?.response?.data?.detail
  if (error?.response?.status === 404 && detail === 'Not Found') return 'A API em execução não reconhece a rota de documentos. Reinicie a API com o código atual.'
  if (!error?.response) return 'Não foi possível conectar à API. Confira se ela está em execução e tente novamente.'
  if (typeof detail === 'string') return detail
  return error?.message || 'Falha ao processar documento.'
}
const message = documentErrorMessage
const formatDate = (value) => value ? new Date(value).toLocaleDateString('pt-BR') : 'Data não informada'

export default function PermitDocuments({ propertyId }) {
  const [docs, setDocs] = useState([]), [page, setPage] = useState(0), [loading, setLoading] = useState(true)
  const [error, setError] = useState(''), [loadError, setLoadError] = useState(''), [notice, setNotice] = useState(''), [busy, setBusy] = useState(false), [fileName, setFileName] = useState('')
  const [selected, setSelected] = useState(null), [fields, setFields] = useState({}), [history, setHistory] = useState([]), [historyPage, setHistoryPage] = useState(0)
  const load = useCallback(async () => {
    setLoading(true)
    try { const { data } = await waterService.permitDocuments(propertyId, { skip: page * 20, limit: 20 }); setDocs(data); setLoadError('') }
    catch (e) { setDocs([]); setLoadError(message(e)) } finally { setLoading(false) }
  }, [propertyId, page])
  useEffect(() => { load() }, [load])
  async function upload(event) {
    event.preventDefault(); const form = event.currentTarget; const file = new FormData(form).get('pdf'); setBusy(true); setNotice('')
    try { await waterService.uploadPermitDocument(propertyId, file); form.reset(); setFileName(''); if (page) setPage(0); else await load(); setNotice('Documento enviado para revisão.'); setError('') } catch (e) { setError(message(e)) } finally { setBusy(false) }
  }
  async function open(doc, nextPage = 0) {
    try { const { data } = await waterService.permitDocumentHistory(doc.id, { skip: nextPage * 50, limit: 50 }); setSelected(doc); setFields(doc.reviewed_fields || {}); setHistory(data); setHistoryPage(nextPage); setError('') } catch (e) { setError(message(e)) }
  }
  async function review(event) {
    event.preventDefault(); setBusy(true)
    try { const values = Object.fromEntries(Object.keys(labels).map((key) => [key, fields[key]?.trim() || null])); const { data } = await waterService.reviewPermitDocument(selected.id, { fields: values, approve: event.nativeEvent.submitter.value === 'approve' }); await load(); await open(data); setNotice(data.processing_status === 'approved' ? 'Revisão aprovada. Os valores continuam separados das demandas.' : 'Revisão salva.') } catch (e) { setError(message(e)) } finally { setBusy(false) }
  }
  async function download(doc) {
    try { const { data } = await waterService.permitDocumentFile(doc.id); const url = URL.createObjectURL(data); const link = document.createElement('a'); link.href = url; link.download = doc.original_name; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000) } catch (e) { setError(message(e)) }
  }
  async function extract(event) {
    event.preventDefault(); const form = event.currentTarget; const values = new FormData(form); setBusy(true)
    try { const { data } = await waterService.extractPermitField(selected.id, { field: values.get('field'), exact_text: values.get('exact_text') }); form.reset(); await load(); await open(data); setNotice('Trecho registrado para conferência.') } catch (e) { setError(message(e)) } finally { setBusy(false) }
  }
  return <section className="integration-panel permit-documents">
    <IntegrationHeader icon={FileText} eyebrow="DOCUMENTAÇÃO" title="Documentos de outorga" description="Guarde o documento original e confira as informações antes de aprová-las." badge="Acesso privado" />
    <form className="integration-upload" onSubmit={upload}><div className="integration-upload-copy"><strong>Adicionar documento</strong><span>PDF de até 10 MB. O arquivo ficará acessível apenas nesta propriedade.</span></div><div className="integration-upload-controls"><label className="integration-file-pick"><Paperclip size={16} aria-hidden="true" /><span>Escolher PDF</span><input name="pdf" type="file" accept="application/pdf" onChange={(event) => setFileName(event.target.files?.[0]?.name || '')} /></label><span className="integration-file-name" title={fileName}>{fileName || 'Nenhum arquivo selecionado'}</span><button className="button primary integration-action" disabled={busy || !fileName}><UploadCloud size={15} aria-hidden="true" />Enviar</button></div></form>
    <IntegrationNotice type="error">{error}</IntegrationNotice><IntegrationNotice type="success">{notice}</IntegrationNotice>
    <div className="integration-list-heading"><div><h4>Documentos enviados</h4><p>Confira o texto extraído e acompanhe a revisão de cada arquivo.</p></div><LockKeyhole size={16} aria-label="Acesso restrito" /></div>
    {loading ? <div className="integration-loading"><span className="spinner" />Carregando documentos…</div> : loadError ? <div className="integration-load-error" role="alert"><span>{loadError}</span><button type="button" className="text-button" onClick={load}>Tentar novamente</button></div> : docs.length === 0 ? <IntegrationEmpty icon={FileText} title="Nenhum documento enviado">Envie um PDF para iniciar a conferência.</IntegrationEmpty> : <div className="integration-list">{docs.map((doc) => <article className={`integration-list-row${selected?.id === doc.id ? ' is-selected' : ''}`} key={doc.id}><span className="integration-row-icon"><FileText size={18} aria-hidden="true" /></span><div className="integration-row-main"><strong>{doc.original_name}</strong><small>Enviado em {formatDate(doc.created_at)} · {Math.ceil(doc.size_bytes / 1024)} KB</small></div><span className={`integration-status ${doc.processing_status === 'approved' ? 'is-success' : 'is-pending'}`}>{statuses[doc.processing_status] || doc.processing_status}</span><div className="integration-row-actions"><button type="button" className="integration-text-button" onClick={() => open(doc)}><FileSearch size={15} />Revisar</button><button type="button" className="integration-icon-button" aria-label={`Baixar ${doc.original_name}`} title="Baixar PDF" onClick={() => download(doc)}><ArrowDownToLine size={17} /></button></div></article>)}</div>}
    {!loading && !loadError && (docs.length > 0 || page > 0) && <IntegrationPagination page={page} count={docs.length} size={20} onPage={setPage} />}
    {selected && <div className="integration-review"><div className="integration-review-heading"><div><p className="integration-eyebrow">CONFERÊNCIA DO DOCUMENTO</p><h4>{selected.original_name}</h4><p>Enviado em {formatDate(selected.created_at)} · {statuses[selected.processing_status] || selected.processing_status}</p></div><button type="button" className="integration-icon-button" onClick={() => setSelected(null)} aria-label="Fechar revisão"><X size={18} /></button></div>
      <div className="integration-notice info"><LockKeyhole size={16} aria-hidden="true" /><span>{selected.processing_status === 'ocr_unavailable' ? 'O texto não foi localizado. OCR não está disponível; confira o arquivo original manualmente.' : 'Compare o texto com o documento original. Os valores não são aplicados automaticamente às demandas.'}</span></div>
      <div className="integration-document-grid"><details className="integration-subpanel"><summary>Texto extraído <span>{selected.extracted_text ? 'Disponível' : 'Não localizado'}</span></summary><pre className="integration-document-text">{selected.extracted_text || 'Nenhum texto foi localizado neste arquivo.'}</pre></details><details className="integration-subpanel"><summary>Campos extraídos <span>Conferência pendente</span></summary><dl className="integration-facts">{Object.entries(labels).map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{selected.extracted_fields?.[key]?.value ?? 'Não localizado'}</dd></div>)}</dl></details></div>
      {selected.extracted_text && <form className="integration-inline-form" onSubmit={extract}><IntegrationField label="Associar trecho a um campo"><select name="field">{Object.entries(labels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></IntegrationField><IntegrationField label="Trecho exato do texto"><input name="exact_text" required placeholder="Cole um trecho do texto extraído" /></IntegrationField><button className="button secondary" disabled={busy}>Registrar trecho</button></form>}
      <form className="integration-review-form" onSubmit={review}><div className="integration-section-title"><div><h5>Campos conferidos</h5><p>Preencha apenas o que conseguiu localizar no documento.</p></div></div><div className="integration-form-grid">{Object.entries(labels).map(([key, label]) => <IntegrationField key={key} label={label}><input value={fields[key] || ''} onChange={(e) => setFields({ ...fields, [key]: e.target.value })} placeholder="Não localizado" /></IntegrationField>)}</div><div className="integration-form-actions"><span>Os campos vazios permanecem sem valor.</span><div><button className="button secondary" type="submit" value="save" disabled={busy}>Salvar revisão</button><button className="button primary" type="submit" value="approve" disabled={busy}><Check size={15} />Aprovar revisão</button></div></div></form>
      <details className="integration-history"><summary><History size={16} /> Histórico de revisões <span>{history.length} nesta página</span></summary>{history.length ? <ol>{history.map((entry) => <li key={entry.id}><strong>{({ upload: 'Documento enviado', extract: 'Trecho registrado', review: 'Revisão salva', approve: 'Revisão aprovada' })[entry.action] || entry.action}</strong><span>{formatDate(entry.created_at)} · usuário {entry.user_id}</span><details><summary>Ver alterações</summary><dl className="integration-history-values"><div><dt>Antes</dt><dd>{JSON.stringify(entry.previous_values)}</dd></div><div><dt>Depois</dt><dd>{JSON.stringify(entry.new_values)}</dd></div></dl></details></li>)}</ol> : <p>Sem alterações nesta página.</p>}<IntegrationPagination page={historyPage} count={history.length} size={50} onPage={(value) => open(selected, value)} /></details>
    </div>}
  </section>
}
