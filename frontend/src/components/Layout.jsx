import { useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import { useClientConfig } from '../lib/clientConfig'

export default function Layout({ children }) {
  const { user, logout } = useAuth()
  const config = useClientConfig()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <div style={{ fontFamily: 'system-ui' }}>
      <header style={styles.header}>
        <span style={styles.title}>{config.app_name}</span>
        <div style={styles.right}>
          {user && <span style={styles.email}>{user.email}</span>}
          <button onClick={handleLogout} style={styles.button}>
            Log out
          </button>
        </div>
      </header>
      <main style={styles.main}>{children}</main>
    </div>
  )
}

const styles = {
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '14px 24px',
    borderBottom: '1px solid #ddd',
  },
  title: { fontWeight: 700 },
  right: { display: 'flex', alignItems: 'center', gap: 12 },
  email: { fontSize: 13, color: '#555' },
  button: {
    padding: '6px 12px',
    fontSize: 13,
    border: '1px solid #ccc',
    borderRadius: 4,
    background: '#fff',
    cursor: 'pointer',
  },
  main: { padding: 24, maxWidth: 720 },
}
