function fmt(p) { return '$' + parseFloat(p || 0).toFixed(2) }

const FIELDS = [
  { key: 'member_price',  label: 'Member Price', fmt: v => fmt(v) },
  { key: 'tread_life_km', label: 'Tread Life',   fmt: v => v.toLocaleString() + ' km' },
  { key: 'noise_db',      label: 'Road Noise',   fmt: v => v + ' dB' },
  { key: 'warranty_years',label: 'Warranty',     fmt: v => v + ' years' },
  { key: 'wet_grip',      label: 'Wet Grip',     fmt: v => v },
  { key: 'rating',        label: 'Rating',       fmt: v => '★ ' + v },
]

export default function CompareCard({ cards }) {
  const tyres = cards.map(c => c.tyre).filter(Boolean)
  if (tyres.length < 2) return null

  return (
    <div className="compare-card">
      <div className="compare-header">
        <span className="material-symbols-rounded">compare_arrows</span>
        Side-by-Side Comparison
      </div>

      <table className="compare-table">
        <thead>
          <tr>
            <th>Spec</th>
            {tyres.map(t => <th key={t.id}>{t.brand} {t.model}</th>)}
          </tr>
        </thead>
        <tbody>
          {FIELDS.map(f => (
            <tr key={f.key}>
              <td className="cmp-label">{f.label}</td>
              {tyres.map(t => <td key={t.id}>{f.fmt(t[f.key])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>

      <div style={{ padding: '10px 16px', display: 'flex', gap: 16, flexWrap: 'wrap', borderTop: '1px solid var(--md-sys-color-outline-variant)' }}>
        {tyres.map(t => {
          const cpm = (t.member_price / t.tread_life_km * 1000).toFixed(3)
          return (
            <div key={t.id}>
              <div style={{ font: '500 12px/16px Roboto,sans-serif', color: 'var(--md-sys-color-outline)' }}>
                {t.brand} {t.model}
              </div>
              <span className="cost-badge">${cpm} per 1,000 km</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
