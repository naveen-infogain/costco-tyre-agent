import { jsPDF } from 'jspdf'

export default function BookingCard({ data: bc }) {
  if (!bc) return null

  function downloadPdf() {
    const NAVY     = [26, 58, 124]      // dark navy header
    const BLUE     = [26, 93, 192]      // section heading blue
    const DARK     = [28, 27, 31]       // body text
    const MUTED    = [140, 140, 140]    // label text
    const GREEN    = [46, 125, 50]
    const GREEN_BG = [232, 245, 233]
    const WHITE    = [255, 255, 255]
    const DIVIDER  = [220, 220, 220]
    const pageW    = 210
    const margin   = 20
    const contentW = pageW - margin * 2
    const labelW   = 36              // width of KV label column
    const doc = new jsPDF({ unit: 'mm', format: 'a4' })
    let y = 0

    // ── Header ──────────────────────────────────────────────────────────────
    doc.setFillColor(...NAVY)
    doc.rect(0, 0, pageW, 38, 'F')

    // Left: title + subtitle
    doc.setTextColor(...WHITE)
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(18)
    doc.text('COSTCO TYRE CENTRE', margin, 16)
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(9)
    doc.text('Booking Confirmation', margin, 24)

    // Right: Booking Reference label + ID
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(8)
    doc.setTextColor(200, 215, 240)
    doc.text('Booking Reference', pageW - margin, 14, { align: 'right' })
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(12)
    doc.setTextColor(...WHITE)
    doc.text(bc.booking_id || '', pageW - margin, 23, { align: 'right' })

    y = 50

    // ── Green status badge ───────────────────────────────────────────────────
    doc.setFillColor(...GREEN_BG)
    doc.roundedRect(margin, y - 5, 56, 10, 3, 3, 'F')
    doc.setTextColor(...GREEN)
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(9)
    doc.text('  Booking Confirmed', margin + 5, y + 1.5)
    // Draw checkmark circle with tick (drawn as lines, not text)
    doc.setFillColor(...GREEN)
    doc.circle(margin + 3.5, y - 0.5, 2.5, 'F')
    doc.setDrawColor(...WHITE)
    doc.setLineWidth(0.6)
    // Tick: short left stroke then long right stroke
    doc.line(margin + 2.2, y - 0.4,  margin + 3.2, y + 0.8)   // short left leg
    doc.line(margin + 3.2, y + 0.8,  margin + 5.1, y - 1.5)   // long right leg

    y += 16

    // ── Divider ──────────────────────────────────────────────────────────────
    doc.setDrawColor(...DIVIDER)
    doc.setLineWidth(0.3)
    doc.line(margin, y, pageW - margin, y)
    y += 10

    // ── Helpers ──────────────────────────────────────────────────────────────
    function divider(gap = 8) {
      doc.setDrawColor(...DIVIDER)
      doc.setLineWidth(0.3)
      doc.line(margin, y, pageW - margin, y)
      y += gap
    }

    function sectionHeading(label) {
      doc.setTextColor(...BLUE)
      doc.setFont('helvetica', 'bold')
      doc.setFontSize(8)
      doc.text(label, margin, y)
      y += 4
      doc.setDrawColor(...DIVIDER)
      doc.setLineWidth(0.3)
      doc.line(margin, y, pageW - margin, y)
      y += 6
    }

    function kvRow(label, value) {
      doc.setFont('helvetica', 'normal')
      doc.setFontSize(9)
      doc.setTextColor(...MUTED)
      doc.text(label, margin, y)
      doc.setTextColor(...DARK)
      const lines = doc.splitTextToSize(String(value || ''), contentW - labelW - 4)
      doc.text(lines, margin + labelW, y)
      y += Math.max(lines.length * 5, 8)
    }

    // ── Appointment Details ───────────────────────────────────────────────────
    sectionHeading('APPOINTMENT DETAILS')
    kvRow('Date & Time', `${bc.date} at ${bc.time}`)
    kvRow('Location',    `Costco Tyre Centre \u2014 ${bc.location}`)
    kvRow('Address',     bc.address)
    kvRow('Tyres',       bc.tyre)
    kvRow('Order ID',    bc.order_id)

    y += 4
    divider(8)

    // ── What to Bring ─────────────────────────────────────────────────────────
    sectionHeading('WHAT TO BRING')
    ;(bc.bring || []).forEach(item => {
      doc.setFillColor(...MUTED)
      doc.rect(margin, y - 3.2, 3.2, 4, 'F')
      doc.setTextColor(...DARK)
      doc.setFont('helvetica', 'normal')
      doc.setFontSize(9)
      doc.text(item, margin + 7, y)
      y += 8
    })

    y += 2
    divider(8)

    // ── What Happens Next ─────────────────────────────────────────────────────
    sectionHeading('WHAT HAPPENS NEXT')
    const next = [
      'SMS reminder sent the day before your appointment',
      'Installation takes approximately 60 minutes',
      '30-day satisfaction survey sent after install',
      'Tyre rotation reminder at 10,000 km',
    ]
    next.forEach((item, i) => {
      doc.setFillColor(...NAVY)
      doc.circle(margin + 3.5, y - 1.2, 3.5, 'F')
      doc.setTextColor(...WHITE)
      doc.setFont('helvetica', 'bold')
      doc.setFontSize(7)
      doc.text(String(i + 1), margin + 3.5, y + 0.3, { align: 'center' })
      doc.setTextColor(...DARK)
      doc.setFont('helvetica', 'normal')
      doc.setFontSize(9)
      const lines = doc.splitTextToSize(item, contentW - 14)
      doc.text(lines, margin + 10, y)
      y += lines.length * 5 + 5
    })

    // ── Footer ────────────────────────────────────────────────────────────────
    const footerY = 282
    doc.setDrawColor(...DIVIDER)
    doc.setLineWidth(0.3)
    doc.line(margin, footerY - 4, pageW - margin, footerY - 4)
    doc.setTextColor(...MUTED)
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(8)
    doc.text('Thank you for shopping with Costco Tyre Centre', pageW / 2, footerY, { align: 'center' })

    doc.save(`Costco_Booking_${bc.booking_id}.pdf`)
  }

  return (
    <div className="full-width">
      <div className="booking-card">

        {/* Blue header banner */}
        <div className="bc-header">
          <div className="bc-icon">
            <span className="material-symbols-rounded">check_circle</span>
          </div>
          <div>
            <div className="bc-title">Booking Confirmed</div>
            <div className="bc-id">{bc.booking_id} · Order {bc.order_id}</div>
          </div>
        </div>

        {/* 4 tiles — single row */}
        <div className="bc-tiles">
          <div className="bc-tile">
            <div className="bc-tile-icon"><span className="material-symbols-rounded">calendar_today</span></div>
            <div className="bc-tile-label">Date</div>
            <div className="bc-tile-value">{bc.date}</div>
            <div className="bc-tile-sub">{bc.time}</div>
          </div>
          <div className="bc-tile">
            <div className="bc-tile-icon"><span className="material-symbols-rounded">location_on</span></div>
            <div className="bc-tile-label">Location</div>
            <div className="bc-tile-value">Costco<br/>Tyre Centre</div>
            <div className="bc-tile-sub">{bc.location}</div>
          </div>
          <div className="bc-tile">
            <div className="bc-tile-icon"><span className="material-symbols-rounded">package_2</span></div>
            <div className="bc-tile-label">Tyres</div>
            <div className="bc-tile-value">{(bc.tyre || '').replace(' x4', '')}</div>
            <div className="bc-tile-sub">x4</div>
          </div>
          <div className="bc-tile">
            <div className="bc-tile-icon"><span className="material-symbols-rounded">event</span></div>
            <div className="bc-tile-label">Calendar</div>
            <div className="bc-tile-value">Invite sent</div>
            <div className="bc-tile-sub">to your email</div>
          </div>
        </div>

        {/* Two-column sections */}
        <div className="bc-sections">
          <div className="bc-section">
            <strong>What to bring</strong>
            <ul>{(bc.bring || []).map((item, i) => <li key={i}>{item}</li>)}</ul>
          </div>
          <div className="bc-section">
            <strong>What happens next</strong>
            <ul>
              <li>SMS reminder sent the day before your appointment</li>
              <li>Installation takes ~60 minutes</li>
              <li>30-day satisfaction survey will be sent after install</li>
              <li>Tyre rotation reminder at 10,000 km</li>
            </ul>
          </div>
        </div>

        <button className="bc-download-btn" onClick={downloadPdf}>
          <span className="material-symbols-rounded">download</span>
          Download Booking Confirmation
        </button>

      </div>
    </div>
  )
}
