import { jsPDF } from 'jspdf'

export default function BookingCard({ data: bc }) {
  if (!bc) return null

  function downloadPdf() {
    const PRIMARY  = [0, 92, 169]
    const DARK     = [30, 30, 30]
    const MUTED    = [100, 100, 100]
    const WHITE    = [255, 255, 255]
    const BG_LIGHT = [245, 248, 252]
    const pageW    = 210
    const margin   = 20
    const contentW = pageW - margin * 2
    const doc = new jsPDF({ unit: 'mm', format: 'a4' })
    let y = 0

    // Header
    doc.setFillColor(...PRIMARY)
    doc.rect(0, 0, pageW, 32, 'F')
    doc.setTextColor(...WHITE)
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(16)
    doc.text('COSTCO TYRE CENTRE', margin, 13)
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(10)
    doc.text('Booking Confirmation', margin, 22)
    doc.setFontSize(8)
    doc.text(bc.booking_id, pageW - margin, 22, { align: 'right' })
    y = 42

    // Status badge
    doc.setFillColor(...BG_LIGHT)
    doc.roundedRect(margin, y - 6, contentW, 14, 3, 3, 'F')
    doc.setTextColor(...PRIMARY)
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(11)
    doc.text('✓  Booking Confirmed', margin + 5, y + 3)
    y += 18

    function sectionHeading(label) {
      doc.setDrawColor(...PRIMARY)
      doc.setLineWidth(0.5)
      doc.line(margin, y, margin + contentW, y)
      y += 5
      doc.setFont('helvetica', 'bold')
      doc.setFontSize(9)
      doc.setTextColor(...PRIMARY)
      doc.text(label.toUpperCase(), margin, y)
      y += 5
    }

    function kvRow(label, value) {
      doc.setFont('helvetica', 'bold')
      doc.setFontSize(9)
      doc.setTextColor(...MUTED)
      doc.text(label, margin, y)
      doc.setFont('helvetica', 'normal')
      doc.setTextColor(...DARK)
      doc.text(String(value || ''), margin + 36, y)
      y += 7
    }

    sectionHeading('Appointment Details')
    kvRow('Date & Time', `${bc.date} at ${bc.time}`)
    kvRow('Location',    bc.location)
    kvRow('Address',     bc.address)
    kvRow('Tyres',       bc.tyre)
    kvRow('Order ID',    bc.order_id)
    y += 4

    sectionHeading('What to Bring')
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(9)
    doc.setTextColor(...DARK);
    (bc.bring || []).forEach(item => { doc.text(`•  ${item}`, margin + 3, y); y += 6 })
    y += 4

    sectionHeading('What Happens Next')
    const next = [
      'SMS reminder sent the day before your appointment',
      'Installation takes approximately 60 minutes',
      '30-day satisfaction survey sent after install',
      'Tyre rotation reminder at 10,000 km',
    ]
    next.forEach(item => { doc.text(`•  ${item}`, margin + 3, y); y += 6 })

    // Footer
    doc.setFillColor(...PRIMARY)
    doc.rect(0, 280, pageW, 17, 'F')
    doc.setTextColor(...WHITE)
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(8)
    doc.text('Thank you for shopping with Costco Tyre Centre.', pageW / 2, 290, { align: 'center' })

    doc.save(`Costco_Booking_${bc.booking_id}.pdf`)
  }

  return (
    <div className="full-width">
      <div className="booking-card">
        <div className="bc-header">
          <div className="bc-icon">
            <span className="material-symbols-rounded">check_circle</span>
          </div>
          <div>
            <div className="bc-title">Booking Confirmed</div>
            <div className="bc-id">{bc.booking_id} · Order {bc.order_id}</div>
          </div>
        </div>

        <div className="bc-row">
          <span className="bc-label">Date</span>
          <span><strong>{bc.date}</strong> at <strong>{bc.time}</strong></span>
        </div>
        <div className="bc-row">
          <span className="bc-label">Location</span>
          <span>
            {bc.location}<br />
            <small style={{ color: 'var(--md-sys-color-outline)' }}>{bc.address}</small>
          </span>
        </div>
        <div className="bc-row">
          <span className="bc-label">Tyres</span>
          <span>{bc.tyre}</span>
        </div>
        {bc.calendar && (
          <div className="bc-row">
            <span className="bc-label">Calendar</span>
            <span>Invite sent to your email</span>
          </div>
        )}

        <div className="bc-bring">
          <strong>What to bring</strong>
          <ul>{(bc.bring || []).map((item, i) => <li key={i}>{item}</li>)}</ul>
        </div>

        <div className="bc-bring" style={{ marginTop: 8, background: 'var(--md-sys-color-surface-variant)' }}>
          <strong>What happens next</strong>
          <ul>
            <li>SMS reminder sent the day before your appointment</li>
            <li>Installation takes ~60 minutes</li>
            <li>30-day satisfaction survey will be sent after install</li>
            <li>Tyre rotation reminder at 10,000 km</li>
          </ul>
        </div>

        <button className="bc-download-btn" onClick={downloadPdf}>
          <span className="material-symbols-rounded">download</span>
          Download Booking Confirmation
        </button>
      </div>
    </div>
  )
}
