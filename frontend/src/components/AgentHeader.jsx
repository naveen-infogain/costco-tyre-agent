export default function AgentHeader({ onSwitchToStore }) {
  return (
    <header className="ah-header">
      {/* Logo */}
      <div className="ah-logo">
        <div className="ah-logo-star">
          <span className="material-symbols-rounded" style={{ fontSize: 22, color: '#fff' }}>tire_repair</span>
        </div>
        <div>
          <span className="ah-logo-costco">Costco</span>
          <span className="ah-logo-wholesale"> Wholesale</span>
        </div>
      </div>

      {/* Center — toggle + shipping note */}
      <div className="ah-center">
        <div className="ah-toggle">
          <button className="ah-toggle-btn ah-toggle-active">
            <span className="material-symbols-rounded" style={{ fontSize: 15 }}>smart_toy</span>
            Agentic Agent
          </button>
          <button className="ah-toggle-btn" onClick={onSwitchToStore}>
            <span className="material-symbols-rounded" style={{ fontSize: 15 }}>language</span>
            Actual Site
          </button>
        </div>
        <div className="ah-shipping-note">
          Tyres will be shipped to and installed at&nbsp;
          <span className="ah-shipping-link">Select Tyre Centre</span>
        </div>
      </div>

      {/* Right actions */}
      <div className="ah-right">
        <div className="ah-lang">
          <span>English</span>
          <span className="ah-lang-sep">|</span>
          <span style={{ opacity: 0.6 }}>Français</span>
        </div>
        <button className="ah-action-btn">
          <span className="material-symbols-rounded" style={{ fontSize: 17 }}>person</span>
          Sign In / Register
        </button>
        <button className="ah-action-btn ah-cart-btn">
          <span className="material-symbols-rounded" style={{ fontSize: 17 }}>shopping_cart</span>
          Cart
        </button>
      </div>
    </header>
  )
}
