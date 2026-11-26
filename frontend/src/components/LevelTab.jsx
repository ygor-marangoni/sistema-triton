import { useState } from 'react'
import { Pencil, Plus, Search, Trash2, Waves } from 'lucide-react'
import MonitoringEmptyState from './MonitoringEmptyState'
import RulerImageReview from './RulerImageReview'
import RowActions from './RowActions'
import AppDialog from './AppDialog'

const number = (n, digits = 1) => n == null ? '—' : Number(n).toLocaleString('pt-BR', { maximumFractionDigits: digits })
const localDateTime = () => { const d = new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 16) }
const PAGE_SIZE = 10
const normalize = (value) => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()

function Field({ label, children }) {
  return <label className="field"><span>{label}</span>{children}</label>
}

export default function LevelTab({ propertyId, reservoirs, stations, dashboard, busy, error, onClearError, onAddReservoir, onCreate, onRead, onConfirmed, onUpdateStation, onDeleteStation }) {
  const [panel, setPanel] = useState(null)
  const [editing, setEditing] = useState(null)
  const [readingId, setReadingId] = useState('')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const available = reservoirs.filter((reservoir) => !stations.some((station) => station.reservoir_id === reservoir.id))
  const showCreate = panel === 'create'
  const filtered = stations.filter((station) => normalize(`${station.name} ${reservoirs.find((r) => r.id === station.reservoir_id)?.name || ''}`).includes(normalize(query)))
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const currentPage = Math.min(page, totalPages)
  const visible = filtered.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE)

  function openPanel(kind, station = null) {
    onClearError?.()
    setEditing(kind === 'edit' || kind === 'delete' ? station : null)
    if (kind === 'read') setReadingId(String(station?.id || stations[0]?.id || ''))
    setPanel(kind)
    if (kind !== 'edit' && kind !== 'delete') window.requestAnimationFrame(() => document.getElementById('level-workspace')?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
  }

  async function saveEdit(event) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    if (await onUpdateStation(editing.id, { name: data.get('name'), minimum_m: Number(data.get('minimum_m')), maximum_m: Number(data.get('maximum_m')) })) closeDialog()
  }

  function closeDialog() { setPanel(null); setEditing(null); onClearError?.() }
  async function confirmDelete() { if (await onDeleteStation(editing.id)) closeDialog() }

  return <div className="monitor-page level-page"><header className="monitor-heading"><div><p className="eyebrow">MONITORAMENTO</p><h2>Estação e nível</h2><p>Acompanhe as leituras de nível dos reservatórios da propriedade.</p></div><div className="level-heading-actions">{stations.length > 0 && <><button type="button" className="button secondary" aria-expanded={panel === 'read'} onClick={() => openPanel('read')}>Registrar leitura</button><button type="button" className="button secondary" aria-expanded={panel === 'create'} onClick={() => openPanel('create')}><Plus size={16} aria-hidden="true" />Cadastrar estação</button></>}</div></header>
    {!stations.length && <MonitoringEmptyState icon={Waves} label="MONITORAMENTO DE NÍVEL" title="Nenhuma estação cadastrada" description={reservoirs.length ? 'Cadastre uma estação para acompanhar as leituras de nível do reservatório.' : 'Cadastre um reservatório para associar uma estação e registrar leituras.'} actionLabel={reservoirs.length ? 'Cadastrar estação' : 'Cadastrar reservatório'} onAction={reservoirs.length ? () => openPanel('create') : onAddReservoir} />}
    {reservoirs.length > 0 && (showCreate || panel === 'read') && <div id="level-workspace" className="level-workspace">
      {showCreate && (editing || available.length ? <form key={editing?.id || 'new'} className="form-card level-form" onSubmit={editing ? saveEdit : onCreate}><div className="level-form-heading"><h3>{editing ? 'Editar estação' : 'Cadastrar estação'}</h3>{stations.length > 0 && <button type="button" className="text-button" onClick={() => { setPanel(null); setEditing(null) }}>Fechar</button>}</div>
        <Field label="Reservatório">{editing ? <input value={reservoirs.find((r) => r.id === editing.reservoir_id)?.name || 'Reservatório'} disabled /> : <select name="reservoir_id">{available.map((r) => <option value={r.id} key={r.id}>{r.name}</option>)}</select>}</Field>
        <Field label="Nome"><input name="name" defaultValue={editing?.name || ''} minLength="2" maxLength="120" required /></Field><div className="form-grid"><Field label="Faixa mínima (m)"><input type="number" name="minimum_m" min="0" step="0.001" defaultValue={editing?.minimum_m ?? '0'} required /></Field><Field label="Faixa máxima (m)"><input type="number" name="maximum_m" min="0.001" step="0.001" defaultValue={editing?.maximum_m ?? ''} required /></Field></div>{editing && <small>A faixa não pode ser alterada se houver leituras ou imagens registradas.</small>}<div className="form-actions"><button type="button" className="button secondary" disabled={busy} onClick={closeDialog}>Cancelar</button><button className="button primary" disabled={busy}>{editing ? 'Salvar alterações' : 'Salvar estação'}</button></div></form> : <div className="level-no-reservoir"><h3>Todos os reservatórios já têm uma estação</h3><p>Cadastre outro reservatório para associar uma nova estação.</p><button type="button" className="button secondary" onClick={onAddReservoir}><Plus size={16} aria-hidden="true" />Cadastrar reservatório</button></div>)}
      {panel === 'read' && stations.length > 0 && <form className="form-card level-form" onSubmit={onRead}><div className="level-form-heading"><h3>Inserir leitura manual/simulada</h3><button type="button" className="text-button" onClick={() => setPanel(null)}>Fechar</button></div><Field label="Estação"><select name="station_id" value={readingId} onChange={(event) => setReadingId(event.target.value)}>{stations.map((s) => <option value={s.id} key={s.id}>{s.name}</option>)}</select></Field><Field label="Nível (m)"><input type="number" name="level_m" min="0" step="0.001" required /></Field><Field label="Data e hora"><input type="datetime-local" name="observed_at" defaultValue={localDateTime()} required /></Field><Field label="Origem"><select name="source"><option value="manual">Manual</option><option value="simulada">Simulada</option></select></Field><div className="form-actions"><button type="button" className="button secondary" disabled={busy} onClick={closeDialog}>Cancelar</button><button className="button primary" disabled={busy}>Salvar leitura</button></div></form>}
    </div>}
    {stations.length > 0 && <section className="level-overview"><div className="monitor-section-heading level-list-heading"><div><h3>Estações cadastradas</h3><p>Última leitura disponível e faixa de cada estação.</p></div><label className="level-search"><Search size={16} aria-hidden="true" /><span className="sr-only">Buscar estação ou reservatório</span><input value={query} onChange={(event) => { setQuery(event.target.value); setPage(1) }} placeholder="Buscar estação ou reservatório" /></label></div>
      <div className="table-wrap equipment-table-wrap"><table className="responsive-equipment-table"><thead><tr><th>Estação</th><th>Reservatório</th><th>Faixa</th><th>Leitura</th><th>Volume estimado</th><th>Ações</th></tr></thead><tbody>{visible.map((s) => { const v = dashboard?.latest_levels?.find((x) => x.reservoir_id === s.reservoir_id); return <tr key={s.id}><td data-label="Estação"><b>{s.name}</b></td><td data-label="Reservatório">{reservoirs.find((r) => r.id === s.reservoir_id)?.name}</td><td data-label="Faixa">{number(s.minimum_m, 2)}–{number(s.maximum_m, 2)} m</td><td data-label="Leitura">{v?.latest ? `${number(v.latest.level_m, 2)} m · ${v.latest.source}` : 'Sem leitura'}</td><td data-label="Volume estimado">{v?.volume_m3 == null ? 'Indisponível' : `${number(v.volume_m3, 0)} m³`}</td><td className="equipment-actions"><RowActions name={s.name} actions={[{ label: 'Registrar leitura', onClick: () => openPanel('read', s) }, { label: 'Editar', Icon: Pencil, onClick: () => openPanel('edit', s) }, { label: 'Excluir', Icon: Trash2, danger: true, onClick: () => openPanel('delete', s) }]} /></td></tr> })}</tbody></table>{!visible.length && <p className="level-no-results">Nenhuma estação encontrada para essa busca.</p>}</div>
      <div className="level-pagination"><span>{filtered.length} {filtered.length === 1 ? 'estação' : 'estações'} · página {currentPage} de {totalPages}</span><div><button type="button" className="small-button" disabled={currentPage <= 1} onClick={() => setPage(currentPage - 1)}>Anterior</button><button type="button" className="small-button" disabled={currentPage >= totalPages} onClick={() => setPage(currentPage + 1)}>Próxima</button></div></div><p className="level-geometry-note">O volume depende das dimensões do modelo retangular inclinado e deve ser conferido em campo. O KML registra o perímetro.</p></section>}
    {editing && panel === 'edit' && <AppDialog title="Editar estação" busy={busy} onClose={closeDialog}><form className="app-dialog-form" onSubmit={saveEdit}><Field label="Reservatório"><input value={reservoirs.find((r) => r.id === editing.reservoir_id)?.name || 'Reservatório'} disabled /></Field><Field label="Nome"><input name="name" defaultValue={editing.name} minLength="2" maxLength="120" required /></Field><div className="form-grid"><Field label="Faixa mínima (m)"><input type="number" name="minimum_m" min="0" step="0.001" defaultValue={editing.minimum_m} required /></Field><Field label="Faixa máxima (m)"><input type="number" name="maximum_m" min="0.001" step="0.001" defaultValue={editing.maximum_m} required /></Field></div><small>A faixa não pode ser alterada se houver leituras ou imagens registradas.</small>{error && <p className="app-dialog-error" role="alert">{error}</p>}<div className="app-dialog-actions"><button type="button" className="button secondary" disabled={busy} onClick={closeDialog}>Cancelar</button><button className="button primary" disabled={busy}>{busy ? 'Salvando…' : 'Salvar alterações'}</button></div></form></AppDialog>}
    {editing && panel === 'delete' && <AppDialog title="Excluir estação" busy={busy} onClose={closeDialog}><div className="app-dialog-form"><p>Deseja excluir <b>{editing.name}</b>? Esta ação não pode ser desfeita.</p><p>Estações com leituras ou imagens são preservadas e não podem ser excluídas.</p>{error && <p className="app-dialog-error" role="alert">{error}</p>}<div className="app-dialog-actions"><button type="button" className="button secondary" disabled={busy} onClick={closeDialog}>Cancelar</button><button type="button" className="button danger-button" disabled={busy} onClick={confirmDelete}>{busy ? 'Excluindo…' : 'Excluir estação'}</button></div></div></AppDialog>}
    {stations.length > 0 && <RulerImageReview key={propertyId} propertyId={propertyId} stations={stations} onConfirmed={onConfirmed} />}
  </div>
}
