const tiers = [
  {
    name: 'Free',
    price: '0',
    description: 'Get started with the core agent and 14 built-in skills.',
    features: [
      '14 base skills included',
      'Claude + OpenAI routing',
      'Persistent memory (SQLite)',
      'Background task daemon',
      'React chat UI',
      'Community support',
    ],
    cta: 'Download Free',
    ctaLink: 'https://github.com/sdrakos/AgelClaw/releases/download/v2.1/AgelClaw-v2.1-win64.zip',
    highlighted: false,
  },
  {
    name: 'Pro',
    price: '29',
    description: 'All skills, monthly new additions, and priority support.',
    features: [
      'Everything in Free',
      'All marketplace skills',
      'Monthly new skill drops',
      'Outlook email digest',
      'Multi-agent orchestrator',
      'Email support',
    ],
    cta: 'Coming Soon',
    ctaLink: '#',
    highlighted: true,
  },
  {
    name: 'Enterprise',
    price: 'Custom',
    description: 'Custom skills, team workspaces, and dedicated setup.',
    features: [
      'Everything in Pro',
      'Custom skill development',
      'Team workspace & shared memory',
      'Dedicated setup assistance',
      'Priority support (24h SLA)',
      'On-prem deployment option',
    ],
    cta: 'Contact Us',
    ctaLink: 'mailto:info@agelclaw.com',
    highlighted: false,
  },
]

function PricingCards() {
  return (
    <section id="pricing" className="py-24 bg-gray-900/30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
            Simple Pricing
          </h2>
          <p className="text-lg text-gray-400 max-w-2xl mx-auto">
            Start free, upgrade when you need more. No credit card required.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-5xl mx-auto">
          {tiers.map((tier) => (
            <div
              key={tier.name}
              className={`relative p-8 rounded-2xl border ${
                tier.highlighted
                  ? 'bg-gray-900 border-indigo-500/50 shadow-xl shadow-indigo-500/10'
                  : 'bg-gray-900/50 border-gray-800'
              }`}
            >
              {tier.highlighted && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 bg-indigo-600 text-white text-xs font-medium rounded-full">
                  Most Popular
                </div>
              )}

              <div className="mb-6">
                <h3 className="text-lg font-semibold text-white mb-1">{tier.name}</h3>
                <div className="flex items-baseline gap-1 mb-3">
                  {tier.price === 'Custom' ? (
                    <span className="text-3xl font-bold text-white">Custom</span>
                  ) : (
                    <>
                      <span className="text-4xl font-bold text-white">${tier.price}</span>
                      <span className="text-gray-500">/month</span>
                    </>
                  )}
                </div>
                <p className="text-sm text-gray-400">{tier.description}</p>
              </div>

              <ul className="space-y-3 mb-8">
                {tier.features.map((feature) => (
                  <li key={feature} className="flex items-start gap-3 text-sm">
                    <svg className="w-5 h-5 text-indigo-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.5 12.75l6 6 9-13.5" />
                    </svg>
                    <span className="text-gray-300">{feature}</span>
                  </li>
                ))}
              </ul>

              <a
                href={tier.ctaLink}
                target={tier.ctaLink.startsWith('http') ? '_blank' : undefined}
                rel={tier.ctaLink.startsWith('http') ? 'noopener noreferrer' : undefined}
                className={`block w-full text-center py-3 rounded-xl font-medium transition-colors ${
                  tier.highlighted
                    ? 'bg-indigo-600 hover:bg-indigo-500 text-white'
                    : 'bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700'
                }`}
              >
                {tier.cta}
              </a>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

export default PricingCards
