import { useState } from 'react'
import SharedHeader from '../components/SharedHeader'

/* ── Featured tyre data (matches our catalogue) ──────────────────────── */
const FEATURED = [
  {
    id: 1, brand: 'Michelin', model: 'Primacy 4', size: '205/55R16',
    season: 'All-Season', price: 189.99, member_price: 169.99,
    rating: 4.8, review_count: 1240, tread_life: '80,000 km',
    badge: 'Best Seller', wet_grip: 'A', tag_color: '#1B6B2C',
    img_icon: 'workspace_premium',
  },
  {
    id: 2, brand: 'Bridgestone', model: 'Turanza EL42', size: '215/55R17',
    season: 'All-Season', price: 174.99, member_price: 154.99,
    rating: 4.6, review_count: 890, tread_life: '75,000 km',
    badge: 'Top Rated', wet_grip: 'A', tag_color: '#005CA9',
    img_icon: 'star',
  },
  {
    id: 3, brand: 'Goodyear', model: 'Assurance WeatherReady', size: '225/65R17',
    season: 'All-Weather', price: 165.00, member_price: 145.00,
    rating: 4.7, review_count: 1105, tread_life: '72,000 km',
    badge: 'All-Weather', wet_grip: 'A+', tag_color: '#7B5800',
    img_icon: 'thunderstorm',
  },
  {
    id: 4, brand: 'MRF', model: 'ZLX', size: '185/65R15',
    season: 'All-Season', price: 99.99, member_price: 89.99,
    rating: 4.5, review_count: 620, tread_life: '60,000 km',
    badge: 'Best Value', wet_grip: 'B', tag_color: '#E31837',
    img_icon: 'savings',
  },
  {
    id: 5, brand: 'CEAT', model: 'Milaze X3', size: '195/65R15',
    season: 'All-Season', price: 109.99, member_price: 94.99,
    rating: 4.4, review_count: 430, tread_life: '65,000 km',
    badge: 'Member Pick', wet_grip: 'B', tag_color: '#005CA9',
    img_icon: 'thumb_up',
  },
  {
    id: 6, brand: 'Apollo', model: 'Alnac 4G', size: '205/55R16',
    season: 'All-Season', price: 119.99, member_price: 104.99,
    rating: 4.5, review_count: 380, tread_life: '68,000 km',
    badge: 'Great Grip', wet_grip: 'A', tag_color: '#1B6B2C',
    img_icon: 'directions_car',
  },
]

const CATEGORIES = [
  { label: 'All-Season',   icon: 'wb_sunny',           desc: 'Year-round performance' },
  { label: 'Winter',       icon: 'ac_unit',             desc: 'Snow & ice rated' },
  { label: 'All-Weather',  icon: 'thunderstorm',        desc: '3-peak mountain rated' },
  { label: 'Performance',  icon: 'speed',               desc: 'High-speed rated' },
  { label: 'Truck / SUV',  icon: 'local_shipping',      desc: 'Light truck rated' },
  { label: 'Eco / Green',  icon: 'eco',                 desc: 'Low rolling resistance' },
]

const BRANDS = ['Michelin', 'Bridgestone', 'Goodyear', 'Pirelli', 'Yokohama',
                'Continental', 'Dunlop', 'MRF', 'CEAT', 'Apollo']

const BENEFITS = [
  { icon: 'build',          title: 'Free Installation',    desc: 'Complimentary installation on all tyre purchases including valve stems and lifetime rotation.' },
  { icon: 'verified',       title: 'Member Pricing',       desc: 'Exclusive savings on top brands — only available to Costco members.' },
  { icon: 'schedule',       title: 'Easy Scheduling',      desc: 'Book your appointment online or with our AI assistant. Same-week slots available.' },
]

const MAKES = {
  Toyota: ['Camry', 'Corolla', 'RAV4', 'Fortuner', 'Innova', 'Prius'],
  Honda:  ['Accord', 'Civic', 'CR-V', 'City', 'Jazz', 'WR-V'],
  Ford:   ['Endeavour', 'EcoSport', 'Bronco', 'F-150', 'Escape'],
  Hyundai:['Creta', 'Venue', 'i20', 'Tucson', 'Verna', 'Alcazar'],
  Kia:    ['Seltos', 'Sonet', 'Carens', 'Sportage'],
  Tata:   ['Nexon', 'Punch', 'Harrier', 'Safari', 'Tiago', 'Altroz'],
  Mahindra:['Scorpio-N', 'XUV700', 'Thar', 'XUV300', 'Bolero'],
  Maruti: ['Swift', 'Baleno', 'Brezza', 'Dzire', 'Ertiga', 'Alto'],
}

const YEARS = Array.from({ length: 15 }, (_, i) => 2025 - i)

function stars(r) {
  const f = Math.round(r)
  return '★'.repeat(f) + '☆'.repeat(5 - f)
}

/* ── Store nav (below shared header) ─────────────────────────────────── */
function StoreNav() {
  return (
    <nav className="cs-nav">
      <a href="#shop"     className="cs-nav-link active">Shop Tyres</a>
      <a href="#install"  className="cs-nav-link">Tyre Installation</a>
      <a href="#brands"   className="cs-nav-link">Brands</a>
      <a href="#benefits" className="cs-nav-link">Why Costco</a>
      <a href="#contact"  className="cs-nav-link">Contact</a>
    </nav>
  )
}

/* ── Hero banner ─────────────────────────────────────────────────────── */
function HeroBanner({ year, make, model, setYear, setMake, setModel, onFindTyres }) {
  const models = make ? (MAKES[make] || []) : []

  return (
    <section className="cs-hero">
      <div className="cs-hero-content">
        <div className="cs-hero-badge">
          <span className="material-symbols-rounded" style={{ fontSize: 14 }}>verified</span>
          Exclusive Member Pricing — Up to 30% Off
        </div>
        <h1 className="cs-hero-title">Find the Perfect Tyres<br />for Your Vehicle</h1>
        <p className="cs-hero-sub">
          Top brands. Free installation. Easy online booking.<br />
          Only at Costco Tyre Centre.
        </p>

        {/* Vehicle form */}
        <div className="cs-vehicle-form">
          <div className="cs-vehicle-form-title">
            <span className="material-symbols-rounded" style={{ fontSize: 16 }}>directions_car</span>
            Shop by Vehicle
          </div>
          <div className="cs-vehicle-selects">
            <select value={year} onChange={e => setYear(e.target.value)}>
              <option value="">Year</option>
              {YEARS.map(y => <option key={y} value={y}>{y}</option>)}
            </select>
            <select value={make} onChange={e => { setMake(e.target.value); setModel('') }}>
              <option value="">Make</option>
              {Object.keys(MAKES).map(m => <option key={m} value={m}>{m}</option>)}
            </select>
            <select value={model} onChange={e => setModel(e.target.value)} disabled={!make}>
              <option value="">Model</option>
              {models.map(m => <option key={m} value={m}>{m}</option>)}
            </select>
            <button
              className="cs-find-btn"
              disabled={!year || !make || !model}
              onClick={onFindTyres}
            >
              <span className="material-symbols-rounded" style={{ fontSize: 18 }}>search</span>
              Find Tyres
            </button>
          </div>
          <div className="cs-hero-or">
            <span>or</span>
          </div>
          <button className="cs-tyre-size-link" onClick={onFindTyres}>
            <span className="material-symbols-rounded" style={{ fontSize: 16 }}>tire_repair</span>
            Search by Tyre Size (e.g. 205/55R16)
          </button>
        </div>
      </div>

      {/* Hero visual */}
      <div className="cs-hero-visual">
        <div className="cs-hero-tyre-ring">
          <span className="material-symbols-rounded" style={{ fontSize: 96, color: 'rgba(255,255,255,0.15)' }}>tire_repair</span>
        </div>
        <div className="cs-hero-stats">
          <div className="cs-hero-stat"><strong>30+</strong><span>Top Brands</span></div>
          <div className="cs-hero-stat"><strong>100+</strong><span>Tyre Models</span></div>
          <div className="cs-hero-stat"><strong>Free</strong><span>Installation</span></div>
        </div>
      </div>
    </section>
  )
}

/* ── Category row ─────────────────────────────────────────────────────── */
function CategorySection({ onSwitchToAgent }) {
  return (
    <section className="cs-section" id="shop">
      <div className="cs-section-inner">
        <h2 className="cs-section-title">Shop by Category</h2>
        <div className="cs-categories">
          {CATEGORIES.map(cat => (
            <button key={cat.label} className="cs-cat-card" onClick={onSwitchToAgent}>
              <span className="material-symbols-rounded cs-cat-icon">{cat.icon}</span>
              <div className="cs-cat-label">{cat.label}</div>
              <div className="cs-cat-desc">{cat.desc}</div>
            </button>
          ))}
        </div>
      </div>
    </section>
  )
}

/* ── Featured tyres ───────────────────────────────────────────────────── */
function FeaturedSection({ onSwitchToAgent }) {
  return (
    <section className="cs-section cs-section-alt">
      <div className="cs-section-inner">
        <div className="cs-section-header">
          <h2 className="cs-section-title">Featured Tyres</h2>
          <button className="cs-view-all" onClick={onSwitchToAgent}>
            View all with AI recommendations
            <span className="material-symbols-rounded" style={{ fontSize: 16 }}>arrow_forward</span>
          </button>
        </div>
        <div className="cs-product-grid">
          {FEATURED.map(tyre => (
            <div key={tyre.id} className="cs-product-card" onClick={onSwitchToAgent}>
              {/* Badge */}
              <div className="cs-product-badge" style={{ background: tyre.tag_color }}>
                <span className="material-symbols-rounded" style={{ fontSize: 12 }}>{tyre.img_icon}</span>
                {tyre.badge}
              </div>

              {/* Tyre visual */}
              <div className="cs-product-img">
                <span className="material-symbols-rounded" style={{ fontSize: 64, color: '#DFE2EB' }}>tire_repair</span>
              </div>

              {/* Info */}
              <div className="cs-product-info">
                <div className="cs-product-brand">{tyre.brand}</div>
                <div className="cs-product-model">{tyre.model}</div>
                <div className="cs-product-size">{tyre.size} &nbsp;·&nbsp; {tyre.season}</div>
                <div className="cs-product-rating">
                  <span className="cs-stars">{stars(tyre.rating)}</span>
                  <span className="cs-review-count">({tyre.review_count.toLocaleString()})</span>
                </div>
                <div className="cs-product-price-row">
                  <div className="cs-product-member-price">${tyre.member_price.toFixed(2)}</div>
                  <div className="cs-product-retail-price">${tyre.price.toFixed(2)}</div>
                  <div className="cs-product-per">/tyre</div>
                </div>
                <div className="cs-product-meta">
                  <span>Tread life: {tyre.tread_life}</span>
                  <span>Wet grip: {tyre.wet_grip}</span>
                </div>
              </div>

              <button className="cs-product-cta" onClick={e => { e.stopPropagation(); onSwitchToAgent() }}>
                <span className="material-symbols-rounded" style={{ fontSize: 16 }}>shopping_cart</span>
                Add to Cart
              </button>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

/* ── Brands section ───────────────────────────────────────────────────── */
function BrandsSection() {
  return (
    <section className="cs-section" id="brands">
      <div className="cs-section-inner">
        <h2 className="cs-section-title">Top Brands Available</h2>
        <div className="cs-brands-grid">
          {BRANDS.map(brand => (
            <div key={brand} className="cs-brand-chip">
              <span className="material-symbols-rounded" style={{ fontSize: 20, color: 'var(--cs-blue)' }}>tire_repair</span>
              {brand}
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

/* ── Why Costco ───────────────────────────────────────────────────────── */
function WhyCostcoSection() {
  return (
    <section className="cs-section cs-section-blue" id="benefits">
      <div className="cs-section-inner">
        <h2 className="cs-section-title cs-title-white">Why Choose Costco Tyre Centre?</h2>
        <div className="cs-benefits-grid">
          {BENEFITS.map(b => (
            <div key={b.title} className="cs-benefit-card">
              <div className="cs-benefit-icon">
                <span className="material-symbols-rounded" style={{ fontSize: 32 }}>{b.icon}</span>
              </div>
              <h3 className="cs-benefit-title">{b.title}</h3>
              <p className="cs-benefit-desc">{b.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

/* ── Banner CTA ───────────────────────────────────────────────────────── */
function AgentBanner({ onSwitchToAgent }) {
  return (
    <section className="cs-agent-banner">
      <div className="cs-agent-banner-inner">
        <span className="material-symbols-rounded" style={{ fontSize: 40, color: '#D3E4FF' }}>smart_toy</span>
        <div>
          <h3>Not sure which tyre is right for you?</h3>
          <p>Our AI Tyre Assistant guides you through personalised recommendations in minutes.</p>
        </div>
        <button className="cs-agent-banner-btn" onClick={onSwitchToAgent}>
          <span className="material-symbols-rounded" style={{ fontSize: 18 }}>smart_toy</span>
          Get AI Recommendations
        </button>
      </div>
    </section>
  )
}

/* ── Footer ───────────────────────────────────────────────────────────── */
function StoreFooter() {
  return (
    <footer className="cs-footer">
      <div className="cs-footer-inner">
        <div className="cs-footer-brand">
          <div className="cs-footer-logo">
            <span className="material-symbols-rounded" style={{ fontSize: 22 }}>tire_repair</span>
            COSTCO TYRE CENTRE
          </div>
          <p>Exclusive tyre pricing for Costco members.<br />Free installation on every purchase.</p>
        </div>
        <div className="cs-footer-links">
          <div>
            <h4>Shop</h4>
            <a href="#">All Tyres</a>
            <a href="#">By Vehicle</a>
            <a href="#">By Size</a>
            <a href="#">By Brand</a>
          </div>
          <div>
            <h4>Services</h4>
            <a href="#">Installation</a>
            <a href="#">Tyre Rotation</a>
            <a href="#">Alignment</a>
            <a href="#">Booking</a>
          </div>
          <div>
            <h4>Support</h4>
            <a href="#">Contact Us</a>
            <a href="#">Find a Store</a>
            <a href="#">FAQ</a>
            <a href="#">Returns</a>
          </div>
        </div>
      </div>
      <div className="cs-footer-bottom">
        <span>© 2025 Costco Wholesale Corporation. All Rights Reserved.</span>
        <span>Member Exclusive Pricing</span>
      </div>
    </footer>
  )
}

/* ── Main page ────────────────────────────────────────────────────────── */
export default function CostcoStorePage({ member, onSwitchToAgent, onSwitchToStore }) {
  const [year, setYear]   = useState('')
  const [make, setMake]   = useState('')
  const [model, setModel] = useState('')

  function handleFindTyres() {
    const context = (year && make && model) ? `${year} ${make} ${model}` : null
    onSwitchToAgent(context)
  }

  return (
    <div className="cs-page">
      <SharedHeader
        activePage="store"
        member={member}
        onSwitchToAgent={() => onSwitchToAgent(null)}
        onSwitchToStore={onSwitchToStore}
      />
      <StoreNav />
      <HeroBanner
        year={year} make={make} model={model}
        setYear={setYear} setMake={setMake} setModel={setModel}
        onFindTyres={handleFindTyres}
      />
      <CategorySection onSwitchToAgent={() => onSwitchToAgent(null)} />
      <FeaturedSection onSwitchToAgent={() => onSwitchToAgent(null)} />
      <AgentBanner onSwitchToAgent={() => onSwitchToAgent(null)} />
      <BrandsSection />
      <WhyCostcoSection />
      <StoreFooter />
    </div>
  )
}
