export default function DetailActions({ tyreId, slotTag, onSendMessage, onBack }) {
  return (
    <div className="detail-actions">
      <button
        className="btn-primary detail-actions-cart"
        onClick={() => onSendMessage(`add to cart ${tyreId}`)}
      >
        <span className="material-symbols-rounded" style={{ fontSize: 18 }}>shopping_cart</span>
        Add to Cart
      </button>
      <button
        className="btn-secondary detail-actions-back"
        onClick={onBack}
      >
        <span className="material-symbols-rounded" style={{ fontSize: 16 }}>arrow_back</span>
        Back to Recommendations
      </button>
    </div>
  )
}
