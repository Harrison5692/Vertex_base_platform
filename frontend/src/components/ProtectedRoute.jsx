import { Navigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'

export default function ProtectedRoute({ children }) {
  const { token, loading } = useAuth()

  if (loading) return null // brief flash avoided — could add a spinner here later
  if (!token) return <Navigate to="/login" replace />

  return children
}
