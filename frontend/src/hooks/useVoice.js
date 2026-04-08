import { useState, useRef, useEffect, useCallback } from 'react'

const STT_SUPPORTED = !!(window.SpeechRecognition || window.webkitSpeechRecognition)

export function useVoice(onTranscript, lastBotText, sessionId) {
  const [voiceEnabled, setVoiceEnabled]   = useState(false)   // ElevenLabs TTS available
  const [isListening, setIsListening]     = useState(false)
  const [isTtsPlaying, setIsTtsPlaying]   = useState(false)
  const [interimText, setInterimText]     = useState('')       // live partial transcript

  const recognitionRef  = useRef(null)
  const ttsAudioRef     = useRef(null)
  const listeningRef    = useRef(false)   // sync ref so callbacks see current value
  const voiceInputRef   = useRef(false)   // true when last user message came from mic

  // Check if ElevenLabs TTS is configured on the backend
  useEffect(() => {
    fetch('/voice/status')
      .then(r => r.json())
      .then(d => setVoiceEnabled(d.enabled))
      .catch(() => {})
  }, [])

  // ── Text-to-Speech (TTS via ElevenLabs) ──────────────────────────────────
  // Defined before auto-TTS effect so the effect closure captures the stable reference
  const speakLastResponse = useCallback(async (textOverride) => {
    const text = textOverride || lastBotText
    if (!voiceEnabled || !text) return

    // Stop any currently playing audio
    if (ttsAudioRef.current && !ttsAudioRef.current.paused) {
      ttsAudioRef.current.pause()
      ttsAudioRef.current = null
      setIsTtsPlaying(false)
      if (!textOverride) return   // manual toggle off — don't restart
    }

    setIsTtsPlaying(true)
    try {
      const resp = await fetch('/voice/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, session_id: sessionId }),
      })
      if (!resp.ok) throw new Error(`TTS ${resp.status}`)

      const blob  = await resp.blob()
      const url   = URL.createObjectURL(blob)
      const audio = new Audio(url)
      ttsAudioRef.current = audio

      audio.onended = () => {
        setIsTtsPlaying(false)
        URL.revokeObjectURL(url)
        ttsAudioRef.current = null
      }
      audio.onerror = () => {
        setIsTtsPlaying(false)
        ttsAudioRef.current = null
      }
      await audio.play()
    } catch (err) {
      console.warn('TTS error:', err)
      setIsTtsPlaying(false)
    }
  }, [voiceEnabled, lastBotText, sessionId])

  // ── Auto-TTS: speak bot response when last input was via mic ─────────────
  useEffect(() => {
    if (!lastBotText || !voiceInputRef.current || !voiceEnabled) return
    voiceInputRef.current = false   // consume the flag — one auto-play per voice input
    speakLastResponse(lastBotText)
  }, [lastBotText]) // eslint-disable-line

  // ── Speech Recognition (STT) ─────────────────────────────────────────────
  function buildRecognition() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) return null

    const r = new SR()
    r.lang = 'en-US'
    r.interimResults = true
    r.maxAlternatives = 1
    r.continuous = false

    let utteranceSent = false   // closure flag — prevents double-fire before r.stop() takes effect

    r.onresult = (e) => {
      if (utteranceSent) return   // already dispatched this utterance
      let interim = ''
      let final   = ''
      for (const result of e.results) {
        if (result.isFinal) final += result[0].transcript
        else interim += result[0].transcript
      }
      if (interim) setInterimText(interim)
      if (final.trim()) {
        utteranceSent = true
        setInterimText('')
        _stopListening()
        voiceInputRef.current = true   // flag: this message came from mic → auto-TTS response
        onTranscript(final.trim())
      }
    }

    r.onerror = (e) => {
      if (e.error !== 'aborted') console.warn('STT error:', e.error)
      _stopListening()
    }

    r.onend = () => {
      if (listeningRef.current) _stopListening()
    }

    return r
  }

  function _stopListening() {
    listeningRef.current = false
    setIsListening(false)
    setInterimText('')
    if (recognitionRef.current) {
      try { recognitionRef.current.stop() } catch { /* ignore */ }
      recognitionRef.current = null
    }
  }

  function toggleMic() {
    if (!STT_SUPPORTED) return
    if (listeningRef.current) {
      _stopListening()
    } else {
      const r = buildRecognition()
      if (!r) return
      recognitionRef.current = r
      try {
        r.start()
        listeningRef.current = true
        setIsListening(true)
      } catch (err) {
        console.warn('STT start error:', err)
        listeningRef.current = false
      }
    }
  }

  return {
    voiceEnabled,
    sttSupported: STT_SUPPORTED,
    isListening,
    isTtsPlaying,
    interimText,
    toggleMic,
    speakLastResponse,
  }
}
