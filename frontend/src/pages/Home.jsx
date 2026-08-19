import { useEffect, useState } from 'react'
import Layout from '../components/Layout'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { tierLabel, useClientConfig } from '../lib/clientConfig'

export default function Home() {
  const { user } = useAuth()
  const config = useClientConfig()
  const [accounts, setAccounts] = useState([])
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    const requests = [api.get('/items/')]
    // /accounts/ is staff+ only (tier 2+) — skip it for tier-1 accounts
    // rather than let it 403.
    if (user && user.tier >= 2) {
      requests.unshift(api.get('/accounts/'))
    }

    Promise.all(requests)
      .then((results) => {
        if (user && user.tier >= 2) {
          setAccounts(results[0])
          setItems(results[1])
        } else {
          setItems(results[0])
        }
      })
      .catch(() => setError('Could not load data.'))
      .finally(() => setLoading(false))
  }, [user])

  return (
    <Layout>
      <h1>Home</h1>
      <p style={{ color: '#555' }}>
        Starter landing page — replace with the real dashboard per client.
      </p>

      {loading && <p>Loading…</p>}
      {error && <p style={{ color: '#c0392b' }}>{error}</p>}

      {!loading && !error && (
        <>
          {user && user.tier >= 2 && (
            <section style={{ marginTop: 24 }}>
              <h2 style={{ fontSize: 16 }}>Accounts ({accounts.length})</h2>
              {accounts.length === 0 ? (
                <p style={{ color: '#888' }}>No accounts yet.</p>
              ) : (
                <ul>
                  {accounts.map((a) => (
                    <li key={a.id}>
                      {a.name || a.email} — {tierLabel(a.tier, config)}
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}

          <section style={{ marginTop: 24 }}>
            <h2 style={{ fontSize: 16 }}>Items ({items.length})</h2>
            {items.length === 0 ? (
              <p style={{ color: '#888' }}>No items yet.</p>
            ) : (
              <ul>
                {items.map((i) => (
                  <li key={i.id}>{i.name}</li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </Layout>
  )
}
