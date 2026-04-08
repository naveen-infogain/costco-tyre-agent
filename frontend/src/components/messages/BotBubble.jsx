import { useState } from 'react'

export default function BotBubble({ text, onFeedback }) {
  const [voted, setVoted] = useState(null)

  // Don't render empty bubbles
  if (!text?.trim()) return null

  function vote(v) {
    setVoted(v)
    onFeedback(v === 'up' ? 'thumbs_up' : 'thumbs_down')
  }

  return (
    <div className="ta-msg-row ta-msg-bot">
      <div className="ta-bubble ta-bubble-bot">
        <p className="ta-bubble-text">{text}</p>
        <div className="ta-bubble-actions">
          <button
            className={`ta-thumb${voted === 'up' ? ' active' : ''}`}
            onClick={() => vote('up')}
            title="Helpful"
          >
            <span className="material-symbols-rounded">thumb_up</span>
          </button>
          <button
            className={`ta-thumb${voted === 'down' ? ' active' : ''}`}
            onClick={() => vote('down')}
            title="Not helpful"
          >
            <span className="material-symbols-rounded">thumb_down</span>
          </button>
        </div>
      </div>
    </div>
  )
}
