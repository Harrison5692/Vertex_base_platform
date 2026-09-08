import NewsletterSignup from './NewsletterSignup'
import { useAuth } from '../lib/auth'
import { useClientConfig } from '../lib/clientConfig'

/** Logo mark: renders config.logo_url once a real client has one;
 * until then, a plain monogram in the deployment's brand color so
 * the banner still looks intentional with zero assets provided. */
function LogoMark({ appName, logoUrl }) {
  if (logoUrl) {
    return <img src={logoUrl} alt={appName} className="h-14 w-14 rounded-lg object-cover" />
  }
  const initial = appName?.trim()?.[0]?.toUpperCase() || '•'
  return (
    <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-lg bg-brand-500 text-xl font-semibold text-white">
      {initial}
    </div>
  )
}

/** Full-width banner between the nav header and the page content —
 * background spans the viewport, inner content lines up with the
 * max-w-5xl column everything else on the page uses. */
export default function StorefrontBanner() {
  const { user } = useAuth()
  const config = useClientConfig()

  return (
    <div className="w-full border-b border-gray-200 bg-white">
      <div className="mx-auto flex max-w-5xl flex-col gap-6 px-6 py-10 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-4">
          <LogoMark appName={config.app_name} logoUrl={config.logo_url} />
          <div>
            <p className="text-sm font-medium text-brand-600">
              Welcome{user?.name ? `, ${user.name}` : ''}
            </p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight text-gray-900">
              {config.app_name}
            </h1>
            {config.tagline && (
              <p className="mt-2 max-w-md text-sm text-gray-600">{config.tagline}</p>
            )}
          </div>
        </div>

        <NewsletterSignup />
      </div>
    </div>
  )
}
