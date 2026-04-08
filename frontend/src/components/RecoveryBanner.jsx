export default function RecoveryBanner({ recovery }) {
  if (!recovery?.message || recovery.action === 'none') return null
  return (
    <div className="recovery-banner">
      <span className="material-symbols-rounded">info</span>
      {recovery.message}
    </div>
  )
}
