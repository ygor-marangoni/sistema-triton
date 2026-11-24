import { Activity, FileText, Waves } from 'lucide-react'

const features = [
  { Icon: Waves, label: 'Nível do reservatório' },
  { Icon: FileText, label: 'Limite da outorga' },
  { Icon: Activity, label: 'Histórico de medições' },
]

export default function AuthHero() {
  return <aside className="auth-hero">
    <div className="auth-hero-stage" aria-hidden="true">
      <span className="auth-hero-orbit auth-hero-orbit-one" />
      <span className="auth-hero-orbit auth-hero-orbit-two" />
      <span className="auth-hero-orbit auth-hero-orbit-three" />
      <img className="auth-hero-art" src="/images/reservoir-hero.png" alt="" />
      <div className="auth-hero-features">
        {features.map(({ Icon, label }) => <span className="auth-hero-feature" key={label}>
          <Icon size={15} strokeWidth={1.8} />{label}
        </span>)}
      </div>
    </div>
    <div className="auth-hero-copy">
      <h2>Acompanhe a água da sua propriedade.</h2>
      <p>Veja níveis, medições e limites de outorga em um só lugar.</p>
    </div>
  </aside>
}
