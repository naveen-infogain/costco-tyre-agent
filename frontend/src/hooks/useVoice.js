import { useState, useRef, useEffect } from 'react'

export function useVoice(onTranscript, lastBotText, sessionId) {
  const [voiceEnabled, setVoiceEnabled] = useState(false)
  const [isListening, setIsListening] = useState(false)
  const [isTtsPlaying, setIsTtsPlaying] = useState(false)
  const recognitionRef = useRef(null)
  const ttsAudioRef = useRef(null)

  useEffect(() => {
    fetch('/voice/status')
      .then(r => r.json())
      .then(d => setVoiceEnabled(d.enabled))
      .catch(() => {})
  }, [])

  function initSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) return null

    const recognition = new SpeechRecognition()
    recognition.lang = 'en-US'
    recognition.interimResults = true
    recognition.maxAlternatives = 1

    recognition.onresult = (e) => {
      const transcript = Array.from(e.results).map(r => r[0].transcript).join('')
      if (e.results[e.results.length - 1].isFinal) {
        stopListening()
        onTranscript(transcript)
      }
    }
    recognition.onerror = () => stopListening()
    recognition.onend = () => stopListening()

    return recognition
  }

  function stopListening() {
    setIsListening(false)
    if (recognitionRef.current) {
      try { recognitionRef.current.stop() } catch { /* ignore */ }
    }
  }

  function toggleMic() {
    if (isListening) {
      stopListening()
    } else {
      if (!recognitionRef.current) {
        recognitionRef.current = initSpeechRecognition()
      }
      if (recognitionRef.current) {
        try {
          recognitionRef.current.start()
          setIsListening(true)
        } catch { /* already started */ }
      }
    }
  }

  async function speakLastResponse() {
    if (!voiceEnabled || !lastBotText) return

    if (ttsAudioRef.current && !ttsAudioRef.current.paused) {
      ttsAudioRef.current.pause()
      ttsAudioRef.current = null
      setIsTtsPlaying(false)
      return
    }

    setIsTtsPlaying(true)
    try {
      const resp = await fetch('/voice/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: lastBotText, session_id: sessionId }),
      })
      if (!resp.ok) throw new Error('TTS failed')
      const blob = await resp.blob()
      const url = URL.createObjectURL(blob)
      const audio = new Audio(url)
      ttsAudioRef.current = audio
      audio.onended = () => {
        setIsTtsPlaying(false)
        URL.revokeObjectURL(url)
      }
      audio.play()
    } catch {
      setIsTtsPlaying(false)
    }
  }

  return { voiceEnabled, isListening, isTtsPlaying, toggleMic, speakLastResponse }
}
