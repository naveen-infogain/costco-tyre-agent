import { useState } from 'react'
import CustomSlotModal from './CustomSlotModal'

export default function SlotPicker({ slots, onSendMessage }) {
  const [bookedIdx, setBookedIdx] = useState(null)
  const [showCustom, setShowCustom] = useState(false)

  const available = (slots || []).filter(s => s.available !== false).slice(0, 6)

  function bookSlot(slot, idx) {
    if (bookedIdx !== null) return
    setBookedIdx(idx)
    onSendMessage(`Book the slot on ${slot.date} at ${slot.time} (location ${slot.location_id})`)
  }

  function handleCustomConfirm(isoDate, time24) {
    setShowCustom(false)
    // Same format as regular slot chips — backend regex: YYYY-MM-DD + HH:MM
    onSendMessage(`Book the slot on ${isoDate} at ${time24}`)
  }

  return (
    <div className="full-width">
      <div className="section-label">Suggested Slots for Your Schedule</div>
      <div className="slots-grid">

        {available.map((slot, idx) => {
          const d = new Date(slot.date + 'T00:00:00')
          const dateStr = d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
          const chipClass = bookedIdx === null
            ? 'slot-chip'
            : bookedIdx === idx
            ? 'slot-chip booked-selected'
            : 'slot-chip booked-other'

          return (
            <div key={idx} className={chipClass} onClick={() => bookSlot(slot, idx)}>
              <div className="slot-date">{dateStr}</div>
              <div className="slot-time">{slot.time}</div>
              <div className="slot-wait">
                {slot.why || `~${slot.estimated_duration_mins} min`}
              </div>
            </div>
          )
        })}

        {/* Custom time card */}
        <div
          className={`slot-chip slot-chip-custom${bookedIdx !== null ? ' booked-other' : ''}`}
          onClick={() => bookedIdx === null && setShowCustom(true)}
        >
          <span className="material-symbols-rounded slot-custom-icon">edit_calendar</span>
          <div className="slot-date">Custom</div>
          <div className="slot-custom-label">Pick date & time</div>
        </div>

      </div>

      {showCustom && (
        <CustomSlotModal
          onConfirm={handleCustomConfirm}
          onClose={() => setShowCustom(false)}
        />
      )}
    </div>
  )
}
