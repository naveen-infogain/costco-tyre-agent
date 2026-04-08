export default function SharedHeader({ activePage, member, onSwitchToAgent, onSwitchToStore, onSwitchToDashboard, stage }) {
  const initials = member?.name
    ? member.name.slice(0, 2).toUpperCase()
    : '?'

  return (
    <header className="sh-header">

      {/* ── Logo ─────────────────────────────────────────────────── */}
      <div className="sh-logo">
        <div className="sh-logo-mark">
          <span className="material-symbols-rounded" style={{ fontSize: 20, color: '#fff' }}>tire_repair</span>
        </div>
        <div className="sh-logo-text">
          <span className="sh-logo-costco">Costco</span>
          <span className="sh-logo-sub"> Wholesale</span>
        </div>
      </div>

      {/* ── Page toggle ──────────────────────────────────────────── */}
      <div className="sh-toggle">
        <button
          className={`sh-toggle-btn${activePage === 'agent' ? ' sh-toggle-active' : ''}`}
          onClick={onSwitchToAgent}
        >
          <span className="material-symbols-rounded" style={{ fontSize: 15 }}>smart_toy</span>
          Agentic Agent
        </button>
        <button
          className={`sh-toggle-btn${activePage === 'store' ? ' sh-toggle-active' : ''}`}
          onClick={onSwitchToStore}
        >
          <span className="material-symbols-rounded" style={{ fontSize: 15 }}>store</span>
          Actual Site
        </button>
      </div>

      {/* ── Search (store only) ───────────────────────────────────── */}
      {activePage === 'store' && (
        <div className="sh-search">
          <span className="material-symbols-rounded sh-search-icon">search</span>
          <input type="text" placeholder="Search by tyre size, brand or vehicle…" />
        </div>
      )}

      {/* ── Stage pill (agent only) ───────────────────────────────── */}
      {activePage === 'agent' && stage && (
        <div className="sh-stage-pill">{stage}</div>
      )}

      {/* ── Right: dashboard + member chip + cart ────────────────── */}
      <div className="sh-right">

        {/* Dashboard icon button */}
        {onSwitchToDashboard && (
          <button
            className={`sh-dashboard-btn${activePage === 'dashboard' ? ' active' : ''}`}
            onClick={onSwitchToDashboard}
            title="Live Dashboard"
          >
            <span className="material-symbols-rounded" style={{ fontSize: 18 }}>analytics</span>
            Dashboard
          </button>
        )}

        <div className="sh-member-chip">
          <div className="sh-member-avatar">{initials}</div>
          <div className="sh-member-info">
            <span className="sh-member-name">{member?.name || 'Member'}</span>
            <span className="sh-member-id">{member?.id}</span>
          </div>
        </div>

        <button className="sh-cart-btn">
          <span className="material-symbols-rounded" style={{ fontSize: 17 }}>shopping_cart</span>
          Cart
        </button>
      </div>

    </header>
  )
}
