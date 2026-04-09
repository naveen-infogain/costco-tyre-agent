import { useState, useRef, useCallback } from 'react'

// Positive intent — ONLY add-to-cart signals. "confirm" and "proceed" are intentionally
// excluded so they fall through to the backend confirm_pay route unchanged.
// Step 1 (voice): say one of these → tyre added to cart, In Cart card shown.
// Step 2 (voice): say "confirm" / "pay" / "pay now" → backend confirm_pay → payment.
const POSITIVE_INTENT = /\b(yes|sure|ok|okay|add it|i'?ll take|i want(ed)?|take it|perfect|go with( it| this)?|sounds good|buy( it)?|order( it)?|get it|this one|let'?s go|yep|yup|definitely|absolutely|do it|that'?s the one|works for me|i'?m in)\b/i

// ---------------------------------------------------------------------------
// Natural language slot parser
// Converts voice phrases like "tomorrow at 9 PM" → { isoDate, time24 }
// so the backend regex r"(\d{4}-\d{2}-\d{2})[^\d]+(\d{2}:\d{2})" can match.
// ---------------------------------------------------------------------------
function parseNaturalSlot(text) {
  const lower = text.toLowerCase()

  // ── Parse time ────────────────────────────────────────────────────────────
  // Matches: "9 PM", "9:00 PM", "9:00 p.m.", "9pm", "21:00", "9 o'clock PM"
  const timePat = /\b(\d{1,2})(?::(\d{2}))?\s*(?:o['']?clock\s*)?(a\.?m\.?|p\.?m\.?)\b/i
  const time24Pat = /\b([01]?\d|2[0-3]):([0-5]\d)\b/

  let hours = null
  let minutes = 0

  const tMatch = lower.match(timePat)
  if (tMatch) {
    hours = parseInt(tMatch[1], 10)
    minutes = parseInt(tMatch[2] || '0', 10)
    const mer = tMatch[3].replace(/\./g, '').toLowerCase()
    if (mer === 'pm' && hours !== 12) hours += 12
    if (mer === 'am' && hours === 12) hours = 0
  } else {
    const t24 = lower.match(time24Pat)
    if (t24) {
      hours = parseInt(t24[1], 10)
      minutes = parseInt(t24[2], 10)
    }
  }

  if (hours === null) return null   // no time found — not a slot booking phrase

  // ── Parse date ────────────────────────────────────────────────────────────
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const date = new Date(today)

  const DAYS = ['sunday','monday','tuesday','wednesday','thursday','friday','saturday']

  if (/\btomorrow\b/.test(lower)) {
    date.setDate(date.getDate() + 1)
  } else if (/\bday after tomorrow\b/.test(lower)) {
    date.setDate(date.getDate() + 2)
  } else if (/\btoday\b/.test(lower)) {
    // keep today
  } else {
    // Look for a named weekday ("this Friday", "next Monday", plain "Friday")
    for (let i = 0; i < DAYS.length; i++) {
      if (lower.includes(DAYS[i])) {
        const diff = (i - date.getDay() + 7) % 7 || 7  // always forward
        date.setDate(date.getDate() + diff)
        break
      }
    }
    // If still today (no day keyword found), default to tomorrow so slots don't go in the past
    if (date.getTime() === today.getTime()) {
      date.setDate(date.getDate() + 1)
    }
  }

  const isoDate = date.toISOString().split('T')[0]
  const time24  = `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`
  return { isoDate, time24 }
}

// Does the message look like a slot booking request?
// Catches: "tomorrow at 9 PM", "Friday 10am", "9:30 AM please", "slot at 9 PM"
const SLOT_TRIGGER = /\b(today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday|day after)\b.*\d{1,2}|\b\d{1,2}\s*(am|pm|a\.m\.|p\.m\.)|\bslot\b.*\d{1,2}|\b\d{1,2}.*\bslot\b/i

export function useChat() {
  const sessionId = useRef(
    typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID()
      : 'sess-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2)
  ).current
  const [messages, setMessages] = useState([])
  const [stage, setStage] = useState('enter')
  const [isTyping, setIsTyping] = useState(false)
  const [lastCards, setLastCards] = useState([])
  const [lastBookingCard, setLastBookingCard] = useState(null)
  const [lastBotText, setLastBotText] = useState('')
  const isTypingRef   = useRef(false)
  const detailContextRef = useRef(null)  // { tyreId, slotTag } set while fetching detail response
  const lastDetailRef    = useRef(null)  // persists last viewed tyre for positive-intent add-to-cart
  const slotsActiveRef   = useRef(false) // true while appointment slots are visible in the feed

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

    // Build TTS text: bot message + Top Pick punch line when cards are present.
    // The chat bubble shows only the original message; voice reads both so the
    // listener hears the punch line even without looking at the screen.
    let ttsText = data.message || ''
    if (data.cards?.length) {
      const topPick = data.cards.find(c => c.slot_tag === 'Top Pick')
      if (topPick?.punch_line) {
        ttsText = ttsText
          ? `${ttsText} And our top pick — ${topPick.punch_line}`
          : topPick.punch_line
      }
    }

    if (data.message) {
      setLastBotText(ttsText)   // TTS gets message + punch line
    }

    // ── Feed ordering ─────────────────────────────────────────────────────
    // "In Cart" response: card first → confirmation message → quick replies
    //   (user sees what was added before the text confirmation)
    // All other responses: message first → cards → quick replies
    //   (intro text sets context before the carousel appears)
    const isCartResponse = data.cards?.some(c => c.slot_tag === 'In Cart')

    if (isCartResponse && data.cards?.length) {
      setLastCards(data.cards)
      addMessage({ type: 'cards', cards: data.cards })      // card first
    }
    if (data.message) {
      addMessage({ type: 'bot', text: data.message })       // then confirmation text
    }
    if (data.quick_replies?.length)
      addMessage({ type: 'quickreplies', replies: data.quick_replies, used: false })
    if (!isCartResponse && data.cards?.length) {
      setLastCards(data.cards)
      addMessage({ type: 'cards', cards: data.cards })      // cards after message for recs
    }
    if (data.appointment_slots?.length) {
      slotsActiveRef.current = true   // slots are now visible — enable natural-language slot booking
      addMessage({ type: 'slots', slots: data.appointment_slots })
    }
    if (data.booking_card) {
      slotsActiveRef.current = false  // booking confirmed — slots no longer active
      setLastBookingCard(data.booking_card)
      addMessage({ type: 'booking', data: data.booking_card })
    }
    if (data.drop_recovery)
      addMessage({ type: 'recovery', recovery: data.drop_recovery })
  }, [addMessage])

  const goBackToRecs = useCallback(() => {
    setMessages(prev => {
      const lastCardsMsg = [...prev].reverse().find(m => m.type === 'cards')
      if (!lastCardsMsg) return prev
      return [...prev, { id: `${Date.now()}-back`, type: 'cards', cards: lastCardsMsg.cards }]
    })
  }, [])

  const sendMessage = useCallback(async (text) => {
    const msg = (text || '').trim()
    if (!msg || isTypingRef.current) return

    let backendMsg = msg

    // ── Natural-language slot booking (voice-first) ───────────────────────
    // When slots are visible and user says "tomorrow at 9 PM" (or similar),
    // parse the date/time and rewrite to the exact format the backend regex expects.
    // This fires before the add-to-cart check so "9 PM tomorrow slot please" doesn't
    // accidentally hit the positive-intent path.
    if (slotsActiveRef.current && SLOT_TRIGGER.test(msg) && !/book the slot on/i.test(msg)) {
      const parsed = parseNaturalSlot(msg)
      if (parsed) {
        backendMsg = `Book the slot on ${parsed.isoDate} at ${parsed.time24}`
        // slotsActiveRef stays true until booking_card arrives in processResponse
      }
    }

    // ── Positive intent → add-to-cart rewrite ────────────────────────────
    else if (
      POSITIVE_INTENT.test(msg) &&
      lastDetailRef.current?.tyreId &&
      !/add to cart/i.test(msg) &&
      !/view details/i.test(msg)
    ) {
      backendMsg = `add to cart ${lastDetailRef.current.tyreId}`
      lastDetailRef.current = null
    }

    // ── Detect detail-view request → track context for action buttons ─────
    const detailMatch = msg.match(/view details for the (.+?) option \((.+?)\)/)
    if (detailMatch) {
      const ctx = { slotTag: detailMatch[1], tyreId: detailMatch[2] }
      detailContextRef.current = ctx
      lastDetailRef.current = ctx
    } else {
      detailContextRef.current = null
    }

    dismissQuickReplies()
    addMessage({ type: 'user', text: msg })
    isTypingRef.current = true
    setIsTyping(true)

    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, message: backendMsg }),
      })

      if (!res.ok) {
        addMessage({ type: 'bot', text: `Something went wrong (${res.status}). Please try again.` })
        return
      }

      const data = await res.json()
      processResponse(data)

      // After detail response, inject action buttons into the feed
      if (detailContextRef.current) {
        addMessage({ type: 'detail_actions', ...detailContextRef.current })
        detailContextRef.current = null
      }
    } catch {
      addMessage({ type: 'bot', text: "Sorry, I couldn't connect to the server. Make sure the server is running and try again." })
    } finally {
      isTypingRef.current = false
      setIsTyping(false)
    }
  }, [sessionId, addMessage, dismissQuickReplies, processResponse])

  const sendImage = useCallback(async (file) => {
    if (!file || isTypingRef.current) return

    const objectUrl = URL.createObjectURL(file)
    addMessage({ type: 'image', src: objectUrl, name: file.name })
    isTypingRef.current = true
    setIsTyping(true)

    try {
      const arrayBuffer = await file.arrayBuffer()
      const bytes = new Uint8Array(arrayBuffer)
      let binary = ''
      for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i])
      const base64 = btoa(binary)

      const res = await fetch('/image-analyse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          image_data: base64,
          image_type: file.type || 'image/jpeg',
        }),
      })

      if (!res.ok) {
        addMessage({ type: 'bot', text: `Image analysis failed (${res.status}). Please try again.` })
        return
      }

      const data = await res.json()
      processResponse(data)
    } catch {
      addMessage({ type: 'bot', text: "Couldn't analyse the image. Please check your connection and try again." })
    } finally {
      isTypingRef.current = false
      setIsTyping(false)
    }
  }, [sessionId, addMessage, processResponse])

  const sendFeedback = useCallback(async (signal, tyreId, agent) => {
    try {
      await fetch('/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, signal, tyre_id: tyreId, agent }),
      })
    } catch { /* silent */ }
  }, [sessionId])

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
    sendImage,
    sendFeedback,
    handleLoginResponse,
    goBackToRecs,
  }
}
