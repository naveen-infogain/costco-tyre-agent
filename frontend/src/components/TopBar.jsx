export default function TopBar({ stage, onSwitchToStore }) {
  const label = stage ? stage.charAt(0).toUpperCase() + stage.slice(1) : 'Enter'
  return (
    <header className="topbar">
      <span className="material-symbols-rounded logo">tire_repair</span>
      <h1>Costco Tyre Assistant</h1>
      <span className="stage-chip">{label}</span>

      <button className="topbar-store-toggle" onClick={onSwitchToStore} title="Go to Costco Tyre Store">
        <span className="material-symbols-rounded" style={{ fontSize: 18 }}>store</span>
        Browse Tyres
      </button>

      <a href="/dashboard" target="_blank" rel="noreferrer">
        <span className="material-symbols-rounded">dashboard</span>
        Dashboard
      </a>
    </header>
  )
}
