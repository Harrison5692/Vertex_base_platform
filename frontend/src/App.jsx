import { useEffect, useState } from 'react'
import { api } from './lib/api'

export default function App() {
  const [items, setItems] = useState([])
  const [status, setStatus] = useState('loading')

  useEffect(() => {
    api
      .get('/items/')
      .then((data) => {
        setItems(data)
        setStatus('ready')
      })
      .catch(() => setStatus('error'))
  }, [])

  return (
    <main style={{ fontFamily: 'system-ui', padding: '2rem', maxWidth: 640 }}>
      <h1>Vertex Base</h1>
      <p>Starter frontend — connected to the FastAPI backend at /api.</p>

      {status === 'loading' && <p>Loading items…</p>}
      {status === 'error' && (
        <p>Couldn't reach the API. Is the backend running? (see README)</p>
      )}
      {status === 'ready' && items.length === 0 && (
        <p>No items yet — POST to /items/ to create one.</p>
      )}
      {status === 'ready' && items.length > 0 && (
        <ul>
          {items.map((item) => (
            <li key={item.id}>{item.name}</li>
          ))}
        </ul>
      )}
    </main>
  )
}
