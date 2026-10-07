import { Link } from 'react-router-dom'
import Layout from '../components/Layout'
import { useClientConfig } from '../lib/clientConfig'

export default function Contact() {
  const config = useClientConfig()
  const policies = config.policies ?? {}
  const { contact_email: email, contact_phone: phone } = policies

  return (
    <Layout>
      <div className="mx-auto max-w-2xl space-y-4 text-gray-700">
        <h1 className="text-2xl font-semibold text-gray-900">Contact us</h1>
        {email || phone ? (
          <>
            <p>
              Questions about an order, a return, or anything else — reach out and a real person
              will get back to you. Include your order number if it's about an order.
            </p>
            <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
              {email && (
                <p>
                  <span className="text-gray-500">Email: </span>
                  <a className="font-medium text-brand-600 hover:underline" href={`mailto:${email}`}>
                    {email}
                  </a>
                </p>
              )}
              {phone && (
                <p className={email ? 'mt-1' : ''}>
                  <span className="text-gray-500">Phone: </span>
                  <a className="font-medium text-brand-600 hover:underline" href={`tel:${phone}`}>
                    {phone}
                  </a>
                </p>
              )}
            </div>
          </>
        ) : (
          <p className="rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800">
            Contact details haven't been set up yet. (Store owner: add contact_email or
            contact_phone under "policies" in client.config.json.)
          </p>
        )}
        <p className="text-sm">
          Looking to return something? See our{' '}
          <Link to="/return-policy" className="text-brand-600 hover:underline">
            return policy
          </Link>
          .
        </p>
      </div>
    </Layout>
  )
}
