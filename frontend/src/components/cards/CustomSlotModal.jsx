import { useState, useRef, useEffect } from 'react'

const ITEM_H = 44

/* ── Drum scroll column ──────────────────────────────────────────────────── */
function DrumColumn({ items, selectedIdx, onChange, width = 80 }) {
  const ref = useRef(null)
  const dragging = useRef(false)

  useEffect(() => {
    if (ref.current) {
      ref.current.scrollTop = selectedIdx * ITEM_H
    }
  }, []) // only on mount

  function handleScroll() {
    if (!ref.current) return
    const idx = Math.round(ref.current.scrollTop / ITEM_H)
    const clamped = Math.max(0, Math.min(idx, items.length - 1))
    onChange(clamped)
  }

  return (
    <div
      className="drum-col"
      ref={ref}
      onScroll={handleScroll}
      style={{ width }}
    >
      <div style={{ height: ITEM_H * 2, flexShrink: 0 }} />
      {items.map((item, i) => (
        <div
          key={i}
          className={`drum-item${i === selectedIdx ? ' drum-selected' : ''}`}
          onClick={() => {
            onChange(i)
            ref.current?.scrollTo({ top: i * ITEM_H, behavior: 'smooth' })
          }}
        >
          {item}
        </div>
      ))}
      <div style={{ height: ITEM_H * 2, flexShrink: 0 }} />
    </div>
  )
}

/* ── Build date options (today + 29 days) ────────────────────────────────── */
function buildDates() {
  const dates = []
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  for (let i = 0; i < 30; i++) {
    const d = new Date(today)
    d.setDate(today.getDate() + i)
    let label
    if (i === 0) label = 'Today'
    else if (i === 1) label = 'Tomorrow'
    else label = d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
    dates.push({ label, date: d })
  }
  return dates
}

const DATES   = buildDates()
const HOURS   = Array.from({ length: 12 }, (_, i) => String(i + 1).padStart(2, '0'))
const MINUTES = Array.from({ length: 12 }, (_, i) => String(i * 5).padStart(2, '0'))
const AMPM    = ['AM', 'PM']

/* ── Modal ───────────────────────────────────────────────────────────────── */
export default function CustomSlotModal({ onConfirm, onClose }) {
  const [dateIdx,   setDateIdx]   = useState(0)
  const [hourIdx,   setHourIdx]   = useState(8)   // 09:00
  const [minuteIdx, setMinuteIdx] = useState(0)
  const [ampmIdx,   setAmpmIdx]   = useState(0)   // AM

  function handleConfirm() {
    const d = DATES[dateIdx].date

    // Backend regex expects YYYY-MM-DD
    const yyyy = d.getFullYear()
    const mm   = String(d.getMonth() + 1).padStart(2, '0')
    const dd   = String(d.getDate()).padStart(2, '0')
    const isoDate = `${yyyy}-${mm}-${dd}`

    // Backend expects HH:MM in 24-hour
    let h = parseInt(HOURS[hourIdx], 10)
    const isPM = AMPM[ampmIdx] === 'PM'
    if (isPM && h !== 12) h += 12
    if (!isPM && h === 12) h = 0
    const time24 = `${String(h).padStart(2, '0')}:${MINUTES[minuteIdx]}`

    onConfirm(isoDate, time24)
  }

  return (
    <div className="csp-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="csp-modal">

        {/* Header */}
        <div className="csp-modal-header">
          <button className="csp-cancel-btn" onClick={onClose}>Cancel</button>
          <span className="csp-modal-title">Choose Date & Time</span>
          <button className="csp-confirm-btn ready" onClick={handleConfirm}>
            Confirm
          </button>
        </div>

        {/* Single drum row: Date | Hour : Minute | AM/PM */}
        <div className="csp-drum-wrap">
          <div className="csp-drum-picker">
            <div className="drum-highlight" />

            {/* Date column — wider */}
            <DrumColumn
              items={DATES.map(d => d.label)}
              selectedIdx={dateIdx}
              onChange={setDateIdx}
              width={110}
            />

            <div className="drum-divider" />

            {/* Hour */}
            <DrumColumn items={HOURS}   selectedIdx={hourIdx}   onChange={setHourIdx}   width={56} />
            <div className="drum-colon">:</div>
            {/* Minute */}
            <DrumColumn items={MINUTES} selectedIdx={minuteIdx} onChange={setMinuteIdx} width={56} />

            <div className="drum-divider" />

            {/* AM / PM */}
            <DrumColumn items={AMPM} selectedIdx={ampmIdx} onChange={setAmpmIdx} width={52} />
          </div>
        </div>

        {/* Selected summary */}
        <div className="csp-summary">
          {DATES[dateIdx].label} &nbsp;·&nbsp;
          {HOURS[hourIdx]}:{MINUTES[minuteIdx]} {AMPM[ampmIdx]}
        </div>

      </div>
    </div>
  )
}
