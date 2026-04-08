import { useState } from 'react'
import TyreCard from './TyreCard'
import CompareCard from './CompareCard'

export default function CardsGrid({ cards, onSendMessage, onFeedback }) {
  const [activeIdx, setActiveIdx] = useState(0)
  const [showCompare, setShowCompare] = useState(false)

  function handleAddToCart(tyreId, slotTag) {
    onSendMessage(`add to cart ${tyreId}`)
  }
  function handleDetails(tyreId, slotTag) {
    onSendMessage(`I'd like to view details for the ${slotTag} option (${tyreId})`)
  }
  function handleThumb(tyreId, signal) {
    onFeedback(signal, tyreId, 'rec_ranking')
  }

  // Returns CSS class based on distance from active index
  function posClass(idx) {
    const d = idx - activeIdx
    if (d === 0)  return 'cc-center'
    if (d === -1) return 'cc-left1'
    if (d === 1)  return 'cc-right1'
    if (d < -1)   return 'cc-left2'
    return 'cc-right2'
  }

  return (
    <div className="full-width">
      <div className="section-label">Your Recommendations</div>

      {/* Carousel — no arrows, Top Pick stays center by default */}
      <div className="cc-wrapper">
        <div className="cc-track">
          {cards.map((card, idx) => (
            <div
              key={card.tyre?.id || idx}
              className={`cc-card ${posClass(idx)}`}
              onClick={() => idx !== activeIdx && setActiveIdx(idx)}
            >
              <TyreCard
                card={card}
                idx={idx}
                selected={idx === activeIdx}
                active={idx === activeIdx}
                onAddToCart={handleAddToCart}
                onDetails={handleDetails}
                onThumb={handleThumb}
              />
            </div>
          ))}
        </div>
      </div>

      {/* Dots */}
      <div className="cc-dots">
        {cards.map((_, idx) => (
          <button
            key={idx}
            className={`cc-dot${idx === activeIdx ? ' active' : ''}`}
            onClick={() => setActiveIdx(idx)}
          />
        ))}
      </div>

      {/* Compare toggle */}
      {cards.length >= 2 && (
        <div className="compare-toggle-row">
          <button className="btn-compare" onClick={() => setShowCompare(v => !v)}>
            <span className="material-symbols-rounded">
              {showCompare ? 'expand_less' : 'compare_arrows'}
            </span>
            {showCompare ? 'Hide comparison' : 'Compare side by side'}
          </button>
        </div>
      )}
      {showCompare && <CompareCard cards={cards} />}
    </div>
  )
}
