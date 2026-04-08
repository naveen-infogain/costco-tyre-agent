import { useState, useRef, useCallback } from 'react'

export function useChat() {
  const sessionId = useRef(crypto.randomUUID()).current
  const [messages, setMessages] = useState([])
  const [stage, setStage] = useState('enter')
  const [isTyping, setIsTyping] = useState(false)
  const [lastCards, setLastCards] = useState([])
  const [lastBookingCard, setLastBookingCard] = useState(null)
  const [lastBotText, setLastBotText] = useState('')
  const isTypingRef = useRef(false)

  const addMessage = useCallback((msg) => {
    setMessages(prev => [...prev, { id: `${Date.now()}-${Math.random()}`, ...msg }])
  }, [])

  // Mark all pending quick-reply rows as used when user sends a new message
  const dismissQuickReplies = useCallback(() => {
    setMessages(prev => prev.map(m =>
      m.type === 'quickreplies' ? { ...m, used: true } : m
    ))
  }, [])

  const processResponse = useCallback((data) => {
    if (data.stage) setStage(data.stage)
    if (data.message) {
      setLastBotText(data.message)
      addMessage({ type: 'bot', text: data.message })
    }
    if (data.quick_replies?.length)
      addMessage({ type: 'quickreplies', replies: data.quick_replies, used: false })
    if (data.cards?.length) {
      setLastCards(data.cards)
      addMessage({ type: 'cards', cards: data.cards })
    }
    if (data.appointment_slots?.length)
      addMessage({ type: 'slots', slots: data.appointment_slots })
    if (data.booking_card) {
      setLastBookingCard(data.booking_card)
      addMessage({ type: 'booking', data: data.booking_card })
    }
    if (data.drop_recovery)
      addMessage({ type: 'recovery', recovery: data.drop_recovery })
  }, [addMessage])

  const sendMessage = useCallback(async (text) => {
    const msg = (text || '').trim()
    if (!msg || isTypingRef.current) return

    dismissQuickReplies()
    addMessage({ type: 'user', text: msg })
    isTypingRef.current = true
    setIsTyping(true)

    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, message: msg }),
      })

      if (!res.ok) {
        addMessage({ type: 'bot', text: `Something went wrong (${res.status}). Please try again.` })
        return
      }

      const data = await res.json()
      processResponse(data)
    } catch {
      addMessage({ type: 'bot', text: "Sorry, I couldn't connect to the server. Make sure the server is running and try again." })
    } finally {
      isTypingRef.current = false
      setIsTyping(false)
    }
  }, [sessionId, addMessage, dismissQuickReplies, processResponse])

  const sendFeedback = useCallback(async (signal, tyreId, agent) => {
    try {
      await fetch('/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, signal, tyre_id: tyreId, agent }),
      })
    } catch { /* silent */ }
  }, [sessionId])

  // Called by LoginModal on successful login
  const handleLoginResponse = useCallback((data) => {
    processResponse(data)
  }, [processResponse])

  return {
    sessionId,
    messages,
    stage,
    isTyping,
    lastCards,
    lastBookingCard,
    lastBotText,
    sendMessage,
    sendFeedback,
    handleLoginResponse,
  }
}
