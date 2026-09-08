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

export default function StorefrontBanner() {
  const config = useClientConfig()

  return (
    <div className="mb-8 flex items-center gap-4 border-b border-gray-200 pb-6">
      <LogoMark appName={config.app_name} logoUrl={config.logo_url} />
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-gray-900">
          {config.app_name}
        </h1>
        {config.tagline && (
          <p className="mt-1 max-w-md text-sm text-gray-500">{config.tagline}</p>
        )}
      </div>
    </div>
  )
}
