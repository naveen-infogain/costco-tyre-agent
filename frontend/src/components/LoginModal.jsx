import { useState, useEffect, useRef } from 'react'

export default function LoginModal({ sessionId, onLoginSuccess }) {
  const [memberId, setMemberId] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [closing, setClosing] = useState(false)
  const [demoMembers, setDemoMembers] = useState([])
  const inputRef = useRef(null)

  useEffect(() => {
    inputRef.current?.focus()
    fetch('/demo-members')
      .then(r => r.json())
      .then(setDemoMembers)
      .catch(() => setDemoMembers([
        { member_id: 'M10001', name: 'Demo 1', vehicle: '', tier: '' },
        { member_id: 'M10002', name: 'Demo 2', vehicle: '', tier: '' },
        { member_id: 'M10003', name: 'Demo 3', vehicle: '', tier: '' },
        { member_id: 'M10004', name: 'Demo 4', vehicle: '', tier: '' },
        { member_id: 'M10005', name: 'Demo 5', vehicle: '', tier: '' },
      ]))
  }, [])

  function fillDemo(id) {
    setMemberId(id)
    setError('')
    inputRef.current?.focus()
  }

  function handleInput(e) {
    setMemberId(e.target.value.toUpperCase().replace(/[^M\d]/g, ''))
    setError('')
  }

  async function submit() {
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

      // Animate close then notify parent
      setClosing(true)
      setTimeout(() => onLoginSuccess(data), 250)
    } catch {
      setError('Could not connect to the server. Make sure the server is running.')
      setLoading(false)
    }
  }

  return (
    <div className={`login-backdrop${closing ? ' closing' : ''}`}>
      <div className={`login-card${closing ? ' closing' : ''}`} role="dialog" aria-modal="true">

        <div className="login-header">
          <div className="brand-row">
            <span className="material-symbols-rounded">tire_repair</span>
            <h2>Costco Tyre Assistant</h2>
          </div>
          <p>Sign in with your Costco membership to get personalised tyre recommendations.</p>
        </div>

        <div className="login-body">
          <div className="login-field">
            <label htmlFor="member-id-input">Costco Member ID</label>
            <input
              id="member-id-input"
              ref={inputRef}
              type="text"
              placeholder="e.g. M10001"
              autoComplete="off"
              spellCheck="false"
              maxLength={8}
              value={memberId}
              onChange={handleInput}
              onKeyDown={e => e.key === 'Enter' && submit()}
              className={error ? 'error' : ''}
            />
            {error && (
              <span className="login-error visible">
                <span className="material-symbols-rounded" style={{ fontSize: 14, verticalAlign: 'middle' }}>error</span>
                {' '}{error}
              </span>
            )}
          </div>

          <button className={`login-btn${loading ? ' loading' : ''}`} onClick={submit} disabled={loading}>
            {loading
              ? <span className="spinner" />
              : <>
                  <span className="material-symbols-rounded" style={{ fontSize: 18 }}>login</span>
                  Sign In
                </>
            }
          </button>

          <div className="demo-members">
            <p>Demo accounts — click to fill:</p>
            <div className="demo-chips">
              {demoMembers.map(m => (
                <button
                  key={m.member_id}
                  className="demo-chip"
                  title={`${m.name} · ${m.vehicle} · ${m.tier}`}
                  onClick={() => fillDemo(m.member_id)}
                >
                  {m.member_id}
                </button>
              ))}
            </div>
          </div>
        </div>

      </div>
    </div>
  )
}
