import { useState } from 'react'

const SLOT_ICONS = {
  'Top Pick': 'workspace_premium',
  'Best Repurchase': 'refresh',
  'Best Upgrade': 'trending_up',
  'Most Popular': 'local_fire_department',
  'Runner-up': 'thumb_up',
  'Budget Alt': 'savings',
}

function stars(rating) {
  const full = Math.round(rating || 0)
  return '★'.repeat(full) + '☆'.repeat(5 - full)
}

function fmt(p) {
  return '$' + parseFloat(p || 0).toFixed(2)
}

export default function TyreCard({ card, idx, selected, active = true, onAddToCart, onDetails, onThumb }) {
  const t = card.tyre || {}
  const inStock = (card.stock_badge || '').toLowerCase().includes('in stock')
  const icon = SLOT_ICONS[card.slot_tag] || 'tire_repair'

  const [thumbState, setThumbState] = useState(null) // 'up' | 'down' | null

  function handleThumb(signal) {
    setThumbState(signal === 'thumbs_up' ? 'up' : 'down')
    onThumb(t.id, signal)
  }

  return (
    <div className={`tyre-card${selected ? ' selected' : ''}`}>
      <div className="card-header">
        <div className="slot-tag">
          <span className="material-symbols-rounded">{icon}</span>
          {card.slot_tag || 'Pick'}
        </div>
        <div className="card-brand">{t.brand || ''}</div>
        <div className="card-model">{t.model || ''}</div>
        <div className="card-size">{t.size || ''} &nbsp;·&nbsp; {t.season || ''} &nbsp;·&nbsp; {t.terrain || ''}</div>
      </div>

      <div className="card-body">
        <div className="price-row">
          <div className="member-price">{fmt(t.member_price)}</div>
          <div className="retail-price">{fmt(t.price)}</div>
          <div className="price-label">/tyre member price</div>
        </div>

        <div className="rating-row">
          <span className="stars">{stars(t.rating)}</span>
          <span className="review-count">{(t.review_count || 0).toLocaleString()} reviews</span>
        </div>

        <span className={`stock-badge ${inStock ? 'in' : 'out'}`}>
          <span className="material-symbols-rounded" style={{ fontSize: 13 }}>
            {inStock ? 'check_circle' : 'remove_circle'}
          </span>
          {card.stock_badge || ''}
        </span>

        {t.active_promotion && (
          <div className="promo-chip">
            <span className="material-symbols-rounded" style={{ fontSize: 12 }}>local_offer</span>
            {' '}{t.active_promotion}
          </div>
        )}

        {card.personalised_msg && (
          <div className="personalised-msg personalised-msg-clamp" title={card.personalised_msg}>
            {card.personalised_msg}
          </div>
        )}

        {card.punch_line && (
          <div className="punch-line">"{card.punch_line}"</div>
        )}

        <div className="tread-info">
          Tread life: {(t.tread_life_km || 0).toLocaleString()} km &nbsp;·&nbsp; {t.warranty_years || 0}yr warranty
        </div>
      </div>

      {active && <div className="card-actions">
        <button className="btn-primary" onClick={() => onAddToCart(t.id, card.slot_tag, idx)}>
          <span className="material-symbols-rounded" style={{ fontSize: 18 }}>shopping_cart</span>
          Add to Cart
        </button>
        <button className="btn-secondary" onClick={() => onDetails(t.id, card.slot_tag, idx)}>
          <span className="material-symbols-rounded" style={{ fontSize: 16 }}>info</span>
          Details
        </button>
        <button
          className={`btn-icon${thumbState === 'up' ? ' liked' : ''}`}
          title="Good pick"
          onClick={() => handleThumb('thumbs_up')}
        >
          <span className="material-symbols-rounded">thumb_up</span>
        </button>
        <button
          className={`btn-icon${thumbState === 'down' ? ' disliked' : ''}`}
          title="Not for me"
          onClick={() => handleThumb('thumbs_down')}
        >
          <span className="material-symbols-rounded">thumb_down</span>
        </button>
      </div>}

      {/* Tap hint on non-active side cards */}
      {!active && (
        <div className="cc-tap-hint">
          <span className="material-symbols-rounded" style={{ fontSize: 16 }}>touch_app</span>
          Tap to view
        </div>
      )}
    </div>
  )
}
