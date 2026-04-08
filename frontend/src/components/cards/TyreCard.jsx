import { useState } from 'react'

const SLOT_ICONS = {
  'Top Pick': 'workspace_premium',
  'Best Repurchase': 'refresh',
  'Best Upgrade': 'trending_up',
  'Most Popular': 'local_fire_department',
  'Runner-up': 'thumb_up',
  'Budget Alt': 'savings',
  'In Cart': 'shopping_cart_checkout',
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
  const [msgExpanded, setMsgExpanded] = useState(false)

  function handleThumb(signal) {
    setThumbState(signal === 'thumbs_up' ? 'up' : 'down')
    onThumb(t.id, signal)
  }

  return (
    <div className={`tyre-card${selected ? ' selected' : ''}`}>

      {/* All content in one uniform area — no coloured header */}
      <div className="card-content">

        {/* Slot tag pill */}
        <div className={`slot-tag${card.slot_tag === 'In Cart' ? ' in-cart' : ''}`}>
          <span className="material-symbols-rounded">{icon}</span>
          {card.slot_tag || 'Pick'}
        </div>

        {/* Brand / Model / Size */}
        <div className="card-brand">{t.brand || ''}</div>
        <div className="card-model">{t.model || ''}</div>
        <div className="card-size">
          {t.size || ''}&nbsp;·&nbsp;{t.season || ''}&nbsp;·&nbsp;{t.terrain || ''}
        </div>

        {/* Price */}
        <div className="price-row">
          <span className="member-price">{fmt(t.member_price)}</span>
          <span className="retail-price">{fmt(t.price)}</span>
        </div>

        {/* Rating */}
        <div className="rating-row">
          <span className="stars">{stars(t.rating)}</span>
          <span className="review-count">{(t.review_count || 0).toLocaleString()} reviews</span>
        </div>

        {/* Stock — inline, no pill background */}
        <div className={`stock-inline ${inStock ? 'in' : 'out'}`}>
          <span className="material-symbols-rounded" style={{ fontSize: 16 }}>
            {inStock ? 'check_circle' : 'cancel'}
          </span>
          {card.stock_badge || ''}
        </div>

        {/* Punch line with icon + attribution */}
        {card.punch_line && (
          <div className="punch-row">
            <span className="material-symbols-rounded punch-icon">check_circle</span>
            <div>
              <div className="punch-line">"{card.punch_line}"</div>
              <div className="punch-line-attribution">The {t.brand} {t.model}</div>
            </div>
          </div>
        )}

        {/* Personalised message — click to expand/collapse */}
        {!card.punch_line && card.personalised_msg && (
          <div
            className={`personalised-msg personalised-msg-clamp${msgExpanded ? ' expanded' : ''}`}
            onClick={e => { e.stopPropagation(); setMsgExpanded(v => !v) }}
            title={msgExpanded ? '' : card.personalised_msg}
          >
            {card.personalised_msg}
            <span className="msg-toggle-hint">{msgExpanded ? ' ▲' : ' ▼'}</span>
          </div>
        )}

        <div className="tread-info">
          Tread life: {(t.tread_life_km || 0).toLocaleString()} km &nbsp;·&nbsp; {t.warranty_years || 0}yr warranty
        </div>
      </div>

      {/* Action buttons */}
      {active && (
        <div className="card-actions">
          {card.slot_tag !== 'In Cart' && (
            <button className="btn-cart" title="Add to Cart" onClick={() => onAddToCart(t.id, card.slot_tag, idx)}>
              <span className="material-symbols-rounded">shopping_cart</span>
            </button>
          )}
          <button className="btn-info" title="Details" disabled>
            <span className="material-symbols-rounded">info</span>
          </button>
          <div style={{ flex: 1 }} />
          <button
            className={`btn-icon${thumbState === 'up' ? ' liked' : ''}`}
            title="Good pick"
            onClick={() => handleThumb('thumbs_up')}
          >
            <span className="material-symbols-rounded" style={{ fontSize: 18 }}>thumb_up</span>
          </button>
          <button
            className={`btn-icon${thumbState === 'down' ? ' disliked' : ''}`}
            title="Not for me"
            onClick={() => handleThumb('thumbs_down')}
          >
            <span className="material-symbols-rounded" style={{ fontSize: 18 }}>thumb_down</span>
          </button>
        </div>
      )}

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
