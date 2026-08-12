import { createContext, useContext, useEffect, useState } from 'react'
import { api, setAuthToken } from './api'

const AuthContext = createContext(null)

const TOKEN_KEY = 'vertex_token'

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY))
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!token) {
      setLoading(false)
      return
    }
    setAuthToken(token)
    api
      .get('/auth/me')
      .then(setUser)
      .catch(() => {
        // token invalid/expired — clear it
        logout()
      })
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  async function login(email, password) {
    const result = await api.post('/auth/login', { email, password })
    localStorage.setItem(TOKEN_KEY, result.access_token)
    setAuthToken(result.access_token)
    setToken(result.access_token)
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY)
    setAuthToken(null)
    setToken(null)
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
