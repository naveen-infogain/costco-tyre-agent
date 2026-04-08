import { useState } from 'react'
import TyreCard from './TyreCard'
import CompareCard from './CompareCard'

// Reorder cards: Runner-up first, Top Pick at centre (index 1), rest after
function reorderCards(cards) {
  if (!cards || cards.length < 2) return cards || []
  const topPickTags = ['Top Pick', 'Best Repurchase']
  const topIdx = cards.findIndex(c => topPickTags.includes(c.slot_tag))
  if (topIdx <= 0) {
    // Top Pick already at 0 — move it to index 1, shift others left
    const reordered = [...cards]
    const [top] = reordered.splice(0, 1)
    reordered.splice(1, 0, top)
    return reordered
  }
  return cards
}

export default function CardsGrid({ cards, onSendMessage, onFeedback }) {
  const orderedCards = reorderCards(cards)
  const [activeIdx, setActiveIdx] = useState(1) // Top Pick starts at centre
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

  // Circular distance — wraps so carousel is infinite
  function posClass(idx) {
    const n = orderedCards.length
    let d = idx - activeIdx
    if (d > Math.floor(n / 2))  d -= n
    if (d < -Math.floor(n / 2)) d += n
    if (d === 0)  return 'cc-center'
    if (d === -1) return 'cc-left1'
    if (d === 1)  return 'cc-right1'
    if (d < -1)   return 'cc-left2'
    return 'cc-right2'
  }

  function prev() {
    setActiveIdx(i => (i - 1 + orderedCards.length) % orderedCards.length)
  }
  function next() {
    setActiveIdx(i => (i + 1) % orderedCards.length)
  }

  return (
    <div className="full-width">
      <div className="section-label">Your Recommendations</div>

      {/* Carousel — click a side card to bring it to centre */}
      <div className="cc-wrapper">
        <div className="cc-track">
          {orderedCards.map((card, idx) => (
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

      {/* Dots — tap to navigate */}
      <div className="cc-dots">
        {orderedCards.map((_, idx) => (
          <button
            key={idx}
            className={`cc-dot${idx === activeIdx ? ' active' : ''}`}
            onClick={() => setActiveIdx(idx)}
          />
        ))}
      </div>

      {/* Compare toggle */}
      {orderedCards.length >= 2 && (
        <div className="compare-toggle-row">
          <button className="btn-compare" onClick={() => setShowCompare(v => !v)}>
            <span className="material-symbols-rounded">
              {showCompare ? 'expand_less' : 'compare_arrows'}
            </span>
            {showCompare ? 'Hide comparison' : 'Compare side by side'}
          </button>
        </div>
      )}
      {showCompare && <CompareCard cards={orderedCards} />}
    </div>
  )
}
