import { useRef, useEffect } from 'react'

export default function ChatInput({
  onSend, onSendImage, isTyping,
  sttSupported, isListening, isTtsPlaying, interimText,
  onToggleMic,
}) {
  const textareaRef = useRef(null)
  const fileInputRef = useRef(null)

  // Show interim transcript while speaking; clear when STT finalises and sends
  useEffect(() => {
    if (!textareaRef.current) return
    if (interimText) {
      textareaRef.current.value = interimText
      autoResize()
    } else {
      textareaRef.current.value = ''
      textareaRef.current.style.height = 'auto'
    }
  }, [interimText])

  function autoResize() {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 100) + 'px'
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  function submit() {
    const val = textareaRef.current?.value.trim()
    if (!val || isTyping || isListening) return
    textareaRef.current.value = ''
    textareaRef.current.style.height = 'auto'
    onSend(val)
  }

  function handleFileChange(e) {
    const file = e.target.files?.[0]
    if (file) onSendImage(file)
    e.target.value = ''
  }

  return (
    <div className={`ta-input-bar${isListening ? ' listening-active' : ''}${isTtsPlaying ? ' tts-active' : ''}`}>
      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        style={{ display: 'none' }}
        onChange={handleFileChange}
      />

      <textarea
        ref={textareaRef}
        className={`ta-input-textarea${isListening ? ' interim' : ''}`}
        placeholder={isListening ? 'Listening…' : isTtsPlaying ? 'Speaking…' : 'Type your message…'}
        rows={1}
        aria-label="Message input"
        autoComplete="off"
        onKeyDown={handleKeyDown}
        onInput={autoResize}
        disabled={isTyping}
        readOnly={isListening}   // prevent manual typing while mic is on
      />

      <div className="ta-input-pill">
        {/* Image search */}
        <button
          className="ta-pill-btn ta-pill-image"
          onClick={() => fileInputRef.current?.click()}
          disabled={isTyping || isListening}
          title="Upload tyre image"
        >
          <span className="material-symbols-rounded">image_search</span>
        </button>

        {/* Mic — only when browser supports Web Speech API */}
        {sttSupported && (
          <button
            className={`ta-pill-btn ta-pill-mic${isListening ? ' listening' : ''}`}
            onClick={onToggleMic}
            disabled={isTyping || isTtsPlaying}
            title={isListening ? 'Stop listening' : 'Voice input'}
          >
            <span className="material-symbols-rounded">
              {isListening ? 'mic' : 'mic'}
            </span>
            {isListening && <span className="mic-pulse" />}
          </button>
        )}

        {/* Send */}
        <button
          className="ta-pill-btn ta-pill-send"
          onClick={submit}
          disabled={isTyping || isListening}
          title="Send"
        >
          <span className="material-symbols-rounded">send</span>
        </button>
      </div>

      {/* TTS playing indicator — subtle wave below the bar */}
      {isTtsPlaying && (
        <div className="tts-wave-bar" aria-label="Speaking…">
          {[...Array(5)].map((_, i) => (
            <span key={i} className="tts-wave-dot" style={{ animationDelay: `${i * 0.12}s` }} />
          ))}
        </div>
      )}
    </div>
  )
}
