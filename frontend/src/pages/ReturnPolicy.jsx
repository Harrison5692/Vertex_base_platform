import { Link } from 'react-router-dom'
import Layout from '../components/Layout'
import { useClientConfig } from '../lib/clientConfig'

/** Plain-language return policy, driven by client.config.json
 * "policies" — return_window_days here is the same number refund
 * requests are checked against, so the page can't promise something
 * the system won't honor. */
export default function ReturnPolicy() {
  const config = useClientConfig()
  const policies = config.policies ?? {}
  const days = policies.return_window_days ?? 30
  const contact = policies.contact_email || policies.contact_phone

  return (
    <Layout>
      <article className="mx-auto max-w-2xl space-y-5 text-gray-700">
        <h1 className="text-2xl font-semibold text-gray-900">Returns &amp; refunds</h1>

        <p>
          If something isn't right, we want to fix it. You can return any item within{' '}
          <strong>{days} days</strong> of your order date for a refund.
        </p>

        <section className="space-y-2">
          <h2 className="font-semibold text-gray-900">How to start a return</h2>
          <p>
            {contact ? (
              <>
                Get in touch at{' '}
                {policies.contact_email ? (
                  <a className="text-brand-600 hover:underline" href={`mailto:${policies.contact_email}`}>
                    {policies.contact_email}
                  </a>
                ) : (
                  policies.contact_phone
                )}{' '}
                with your order number and what's wrong.
              </>
            ) : (
              <>
                <Link to="/contact" className="text-brand-600 hover:underline">
                  Contact us
                </Link>{' '}
                with your order number and what's wrong.
              </>
            )}{' '}
            We'll reply with where to send it.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="font-semibold text-gray-900">What we accept</h2>
          <p>
            Items should be unused, unwashed, and in the condition you received them. If an item
            arrived damaged, defective, or wasn't what you ordered, tell us — that's always
            covered, regardless of condition.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="font-semibold text-gray-900">Return shipping</h2>
          <p>
            {policies.customer_pays_return_shipping === false
              ? "Return shipping is on us."
              : 'Return shipping is paid by you, unless the item arrived damaged, defective, or wrong — then it\u2019s on us.'}
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="font-semibold text-gray-900">Refunds</h2>
          <p>
            Once your return arrives, we inspect it and issue the refund to your original payment
            method. Your bank may take a few business days to show it. Original shipping charges
            are refunded when the return is our mistake.
          </p>
        </section>
      </article>
    </Layout>
  )
}
