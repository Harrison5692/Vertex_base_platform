import { Navigate, Route, Routes } from 'react-router-dom'
import ProtectedRoute from './components/ProtectedRoute'
import { AuthProvider } from './lib/auth'
import { ClientConfigProvider } from './lib/clientConfig'
import Accounts from './pages/Accounts'
import Checkout from './pages/Checkout'
import Home from './pages/Home'
import Items from './pages/Items'
import Notifications from './pages/Notifications'
import Transactions from './pages/Transactions'

// A dedicated /login page still makes sense for a business type with
// real compliance/security needs of its own — but that's out of scope
// for this base build entirely. RPM specifically is NOT planned to
// evolve from this template; an RPM deployment is built from the
// existing, purpose-built RPM platform instead. This base build's
// intended evolution path is POS/retail, service-scheduling, and
// catering only. For the general storefront base build, sign-in is a
// corner widget on every page (see components/AuthModal.jsx +
// Layout.jsx) rather than a gate you have to pass before browsing
// anything.
export default function App() {
  return (
    <ClientConfigProvider>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Navigate to="/" replace />} />
          <Route path="/register" element={<Navigate to="/" replace />} />
          <Route path="/" element={<Home />} />
          <Route path="/items" element={<Items />} />
          <Route path="/checkout" element={<Checkout />} />
          <Route
            path="/transactions"
            element={
              <ProtectedRoute>
                <Transactions />
              </ProtectedRoute>
            }
          />
          <Route
            path="/notifications"
            element={
              <ProtectedRoute>
                <Notifications />
              </ProtectedRoute>
            }
          />
          <Route
            path="/accounts"
            element={
              <ProtectedRoute minTier={2}>
                <Accounts />
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </ClientConfigProvider>
  )
}
