import { ArrowLeft } from 'lucide-react'

function Field({ label, children, hint }) {
  return <label className="field"><span>{label}</span>{children}{hint && <small>{hint}</small>}</label>
}

export default function PropertyCreatePage({ busy, onSubmit, onCancel, children }) {
  return <section className="property-create-page">
    <button type="button" className="property-create-back" onClick={onCancel}><ArrowLeft size={16} aria-hidden="true" />Voltar ao início</button>
    <header className="property-create-header"><div><p className="eyebrow">SEU ESPAÇO DE MONITORAMENTO</p><h1>Cadastrar propriedade</h1><p>Informe os dados para começar a acompanhar sua propriedade.</p></div></header>
    <form className="property-create-form" onSubmit={onSubmit}>
      <div className="property-create-section"><div className="property-create-section-title"><h2>Dados da propriedade</h2><p>Você pode atualizar essas informações depois.</p></div><div className="form-grid"><Field label="Nome da propriedade"><input name="name" required minLength="2" placeholder="Ex.: Fazenda Santa Clara" /></Field><Field label="CEP"><input name="cep" required placeholder="00000-000" /></Field><Field label="Cidade"><input name="city" required /></Field><Field label="UF"><input name="state" required maxLength="2" /></Field></div></div>
      <div className="property-create-section"><div className="property-create-section-title"><h2>Localização <span>Opcional</span></h2><p>Informe as coordenadas da propriedade ou marque a posição no mapa depois.</p></div><div className="form-grid"><Field label="Latitude (graus decimais)"><input name="latitude" type="number" min="-90" max="90" step="0.000001" /></Field><Field label="Longitude (graus decimais)"><input name="longitude" type="number" min="-180" max="180" step="0.000001" /></Field></div></div>
      <div className="property-create-actions"><button type="button" className="button secondary" disabled={busy} onClick={onCancel}>Cancelar</button><button className="button primary" disabled={busy}>{busy ? 'Salvando…' : 'Salvar propriedade'}</button></div>
    </form>
    {children}
  </section>
}
