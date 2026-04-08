import { useRef } from 'react'

export default function ChatInput({ onSend, onSendImage, isTyping, voiceEnabled, isListening, isTtsPlaying, onToggleMic, onTts }) {
  const textareaRef = useRef(null)
  const fileInputRef = useRef(null)

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  function handleInput() {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 100) + 'px'
  }

  function submit() {
    const val = textareaRef.current?.value.trim()
    if (!val || isTyping) return
    textareaRef.current.value = ''
    textareaRef.current.style.height = 'auto'
    onSend(val)
  }

  function handleFileChange(e) {
    const file = e.target.files?.[0]
    if (file) onSendImage(file)
    e.target.value = ''   // reset so same file can be re-selected
  }

  return (
    <div className="ta-input-bar">
      {/* Hidden file input for image uploads */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        style={{ display: 'none' }}
        onChange={handleFileChange}
      />
      <textarea
        ref={textareaRef}
        className="ta-input-textarea"
        placeholder="Type your message…"
        rows={1}
        aria-label="Message input"
        autoComplete="off"
        onKeyDown={handleKeyDown}
        onInput={handleInput}
        disabled={isTyping}
      />

      {/* Action pill — image + mic + send */}
      <div className="ta-input-pill">
        <button
          className="ta-pill-btn ta-pill-image"
          onClick={() => fileInputRef.current?.click()}
          disabled={isTyping}
          title="Upload tyre image for analysis"
        >
          <span className="material-symbols-rounded">image_search</span>
        </button>
        {voiceEnabled && isTtsPlaying && (
          <button className="ta-pill-btn" onClick={onTts} title="Stop reading">
            <span className="material-symbols-rounded">stop_circle</span>
          </button>
        )}
        {voiceEnabled && !isTtsPlaying && (
          <button className="ta-pill-btn" onClick={onTts} title="Read aloud">
            <span className="material-symbols-rounded">volume_up</span>
          </button>
        )}
        <button
          className={`ta-pill-btn ta-pill-mic${isListening ? ' listening' : ''}`}
          onClick={onToggleMic}
          title={isListening ? 'Stop listening' : 'Voice input'}
        >
          <span className="material-symbols-rounded">
            {isListening ? 'mic_off' : 'mic'}
          </span>
        </button>
        <button
          className="ta-pill-btn ta-pill-send"
          onClick={submit}
          disabled={isTyping}
          title="Send"
        >
          <span className="material-symbols-rounded">send</span>
        </button>
      </div>
    </div>
  )
}
