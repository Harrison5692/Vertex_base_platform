import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await login(email, password)
      navigate('/')
    } catch (err) {
      setError('Incorrect email or password.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div style={styles.wrap}>
      <form onSubmit={handleSubmit} style={styles.card}>
        <h1 style={styles.title}>Sign in</h1>

        <label style={styles.label}>Email</label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          style={styles.input}
        />

        <label style={styles.label}>Password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          style={styles.input}
        />

        {error && <p style={styles.error}>{error}</p>}

        <button type="submit" disabled={submitting} style={styles.button}>
          {submitting ? 'Signing in…' : 'Sign in'}
        </button>

        <p style={styles.footer}>
          No account? <Link to="/register">Register</Link>
        </p>
      </form>
    </div>
  )
}

const styles = {
  wrap: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    minHeight: '100vh',
    fontFamily: 'system-ui',
  },
  card: {
    width: 320,
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
    padding: 32,
    border: '1px solid #ddd',
    borderRadius: 8,
  },
  title: { marginBottom: 8 },
  label: { fontSize: 13, color: '#555', marginTop: 8 },
  input: { padding: 8, fontSize: 14, border: '1px solid #ccc', borderRadius: 4 },
  button: {
    marginTop: 16,
    padding: 10,
    fontSize: 14,
    fontWeight: 600,
    background: 'var(--primary-color, #1a9c8f)',
    color: '#fff',
    border: 'none',
    borderRadius: 4,
    cursor: 'pointer',
  },
  error: { color: '#c0392b', fontSize: 13, marginTop: 4 },
  footer: { fontSize: 13, marginTop: 12, textAlign: 'center', color: '#555' },
}
