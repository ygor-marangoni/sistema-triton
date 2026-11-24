export default function BrandMark({ small = false }) {
  return (
    <span className={`brand-mark${small ? ' small' : ''}`} aria-hidden="true">
      <img src={small ? '/logoicon.svg?v=20261124' : '/logo%20vertical.svg?v=20261124'} alt="" />
    </span>
  )
}
