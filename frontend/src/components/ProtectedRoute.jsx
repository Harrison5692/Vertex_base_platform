import { Navigate } from 'react-router-dom'
import { useAuth } from '../lib/auth'

/** minTier is optional — pass it to gate a route behind a tier (e.g.
 * staff-only pages). Omit it for any route that just needs "logged
 * in", regardless of tier. */
export default function ProtectedRoute({ children, minTier }) {
  const { token, user, loading } = useAuth()

  if (loading) return null // brief flash avoided — could add a spinner here later
  if (!token) return <Navigate to="/login" replace />
  if (minTier && user && user.tier < minTier) return <Navigate to="/" replace />

  return children
}
