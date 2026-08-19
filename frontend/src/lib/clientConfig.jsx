import { createContext, useContext, useEffect, useState } from 'react'
import { api } from './api'

const ClientConfigContext = createContext(null)

const DEFAULTS = {
  app_name: 'Vertex Base',
  primary_color: '#1a9c8f',
  tier_labels: { 1: 'Client', 2: 'Staff', 3: 'Manager' },
}

export function ClientConfigProvider({ children }) {
  const [config, setConfig] = useState(DEFAULTS)

  useEffect(() => {
    api
      .get('/config/')
      .then(setConfig)
      .catch(() => setConfig(DEFAULTS)) // fine to fall back silently — just branding
  }, [])

  useEffect(() => {
    document.documentElement.style.setProperty('--primary-color', config.primary_color)
    document.title = config.app_name
  }, [config])

  return (
    <ClientConfigContext.Provider value={config}>{children}</ClientConfigContext.Provider>
  )
}

export function useClientConfig() {
  const ctx = useContext(ClientConfigContext)
  if (!ctx) throw new Error('useClientConfig must be used inside ClientConfigProvider')
  return ctx
}

/** e.g. tierLabel(2, config) -> "Staff" instead of the raw number. */
export function tierLabel(tier, config) {
  return config.tier_labels[String(tier)] || `Tier ${tier}`
}
