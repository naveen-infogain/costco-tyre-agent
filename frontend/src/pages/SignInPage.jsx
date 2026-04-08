import { useState, useEffect, useRef } from 'react'

const MAKES = ['Toyota', 'Honda', 'Ford', 'Hyundai', 'Kia', 'Tata', 'Mahindra', 'Maruti', 'Volkswagen', 'Skoda']

export default function SignInPage({ sessionId, onSignInSuccess }) {
  const [memberId, setMemberId]     = useState('')
  const [error, setError]           = useState('')
  const [loading, setLoading]       = useState(false)
  const [demoMembers, setDemoMembers] = useState([])
  const inputRef = useRef(null)

  useEffect(() => {
    inputRef.current?.focus()
    fetch('/demo-members')
      .then(r => r.json())
      .then(setDemoMembers)
      .catch(() => setDemoMembers([
        { member_id: 'M10001', name: 'Demo Member 1', vehicle: 'Toyota Camry', tier: 'Executive' },
        { member_id: 'M10002', name: 'Demo Member 2', vehicle: 'Honda Accord', tier: 'Gold Star' },
        { member_id: 'M10003', name: 'Demo Member 3', vehicle: 'Tata Nexon', tier: 'Executive' },
        { member_id: 'M10004', name: 'Demo Member 4', vehicle: 'Hyundai Creta', tier: 'Gold Star' },
        { member_id: 'M10005', name: 'Demo Member 5', vehicle: 'Maruti Swift', tier: 'Executive' },
      ]))
  }, [])

  function handleInput(e) {
    setMemberId(e.target.value.toUpperCase().replace(/[^M\d]/g, ''))
    setError('')
  }

  async function signIn() {
    const id = memberId.trim().toUpperCase()
    if (!id) { setError('Please enter your Costco Member ID.'); return }
    if (!/^M\d{4,6}$/.test(id)) {
      setError('Member IDs start with M followed by 4–6 digits (e.g. M10042).')
      return
    }
    setLoading(true)
    setError('')
    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, message: id }),
      })
      const data = await res.json()
      if (data.message?.toLowerCase().includes("couldn't find")) {
        setError(`Member ID ${id} not found. Please check and try again.`)
        setLoading(false)
        return
      }
      onSignInSuccess({ ...data, memberId: id })
    } catch {
      setError('Could not connect to the server. Make sure the server is running.')
      setLoading(false)
    }
  }

  return (
    <div className="signin-page">

      {/* Left panel — branding */}
      <div className="signin-left">
        <div className="signin-brand">
          <div className="signin-brand-logo">
            <span className="material-symbols-rounded" style={{ fontSize: 40, color: '#fff' }}>tire_repair</span>
          </div>
          <div className="signin-brand-name">COSTCO</div>
          <div className="signin-brand-sub">TYRE CENTRE</div>
        </div>

        <div className="signin-perks">
          <h2>Member Exclusive Benefits</h2>
          <ul className="signin-perks-list">
            <li>
              <span className="material-symbols-rounded">verified</span>
              <div>
                <strong>Member Pricing</strong>
                <span>Up to 30% off top tyre brands</span>
              </div>
            </li>
            <li>
              <span className="material-symbols-rounded">build</span>
              <div>
                <strong>Free Installation</strong>
                <span>Includes valve stems & lifetime rotation</span>
              </div>
            </li>
            <li>
              <span className="material-symbols-rounded">smart_toy</span>
              <div>
                <strong>AI Tyre Assistant</strong>
                <span>Personalised recommendations in minutes</span>
              </div>
            </li>
            <li>
              <span className="material-symbols-rounded">calendar_month</span>
              <div>
                <strong>Easy Booking</strong>
                <span>Same-week appointment slots available</span>
              </div>
            </li>
          </ul>
        </div>

        <div className="signin-brand-footer">
          <span className="material-symbols-rounded" style={{ fontSize: 14 }}>star</span>
          Serving Costco members since 1996
        </div>
      </div>

      {/* Right panel — sign in form */}
      <div className="signin-right">
        <div className="signin-card">

          <div className="signin-card-header">
            <div className="signin-card-icon">
              <span className="material-symbols-rounded" style={{ fontSize: 28 }}>tire_repair</span>
            </div>
            <h1 className="signin-card-title">Sign In</h1>
            <p className="signin-card-sub">Enter your Costco Member ID to get personalised tyre recommendations.</p>
          </div>

          <div className="signin-field">
            <label htmlFor="signin-member-id">Costco Member ID</label>
            <div className="signin-input-wrap">
              <span className="material-symbols-rounded signin-input-icon">badge</span>
              <input
                id="signin-member-id"
                ref={inputRef}
                type="text"
                placeholder="e.g. M10001"
                autoComplete="off"
                spellCheck="false"
                maxLength={8}
                value={memberId}
                onChange={handleInput}
                onKeyDown={e => e.key === 'Enter' && signIn()}
                className={error ? 'error' : ''}
              />
            </div>
            {error && (
              <span className="signin-error">
                <span className="material-symbols-rounded" style={{ fontSize: 14 }}>error</span>
                {error}
              </span>
            )}
          </div>

          <button className="signin-btn" onClick={signIn} disabled={loading}>
            {loading
              ? <><span className="signin-spinner" /> Signing in…</>
              : <><span className="material-symbols-rounded" style={{ fontSize: 18 }}>login</span> Sign In</>
            }
          </button>

          {/* Demo accounts */}
          <div className="signin-demo">
            <p>Demo accounts — click to fill:</p>
            <div className="signin-demo-chips">
              {demoMembers.map(m => (
                <button
                  key={m.member_id}
                  className="signin-demo-chip"
                  title={`${m.name} · ${m.vehicle} · ${m.tier}`}
                  onClick={() => { setMemberId(m.member_id); setError(''); inputRef.current?.focus() }}
                >
                  <span className="material-symbols-rounded" style={{ fontSize: 13 }}>person</span>
                  {m.member_id}
                  {m.vehicle && <span className="signin-demo-vehicle">{m.vehicle}</span>}
                </button>
              ))}
            </div>
          </div>

          <p className="signin-help">
            <span className="material-symbols-rounded" style={{ fontSize: 14 }}>help</span>
            Your member ID starts with M followed by digits (e.g. M10042).
            Find it on the front of your Costco membership card.
          </p>
        </div>
      </div>

    </div>
  )
}
