import PricingCards from '../components/PricingCards'

const faqs = [
  {
    q: 'Do I need to pay to use AgelClaw?',
    a: 'No. The Free tier includes 14 skills, multi-AI routing, persistent memory, and the full chat UI. You only need your own API key (Claude or OpenAI).',
  },
  {
    q: 'What do I need to run it?',
    a: 'Python 3.11+, an API key from Anthropic or OpenAI, and a Windows/macOS/Linux machine. No cloud account or Docker required.',
  },
  {
    q: 'What does Pro add?',
    a: 'Pro unlocks all marketplace skills (including future ones), the multi-agent orchestrator, Outlook email digest, and email support.',
  },
  {
    q: 'Is my data sent to your servers?',
    a: 'No. AgelClaw runs 100% locally. Your data goes only to the AI provider you choose (Claude or OpenAI). We have no telemetry.',
  },
  {
    q: 'Can I create my own skills?',
    a: 'Yes! Every tier can create custom skills using SKILL.md files. Enterprise adds a visual skill builder and shared team workspaces.',
  },
]

function PricingPage() {
  return (
    <section className="pt-28 pb-24">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="text-center mb-4">
          <h1 className="text-3xl sm:text-4xl font-bold text-white mb-4">
            Pricing
          </h1>
          <p className="text-lg text-gray-400 max-w-2xl mx-auto">
            Start free. Upgrade when you need more skills and support.
          </p>
        </div>
      </div>

      <PricingCards />

      {/* FAQ */}
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 mt-8">
        <h2 className="text-2xl font-bold text-white text-center mb-10">
          Frequently Asked Questions
        </h2>
        <div className="space-y-6">
          {faqs.map((faq) => (
            <div key={faq.q} className="p-6 bg-gray-900/50 border border-gray-800 rounded-xl">
              <h3 className="text-sm font-semibold text-white mb-2">{faq.q}</h3>
              <p className="text-sm text-gray-400 leading-relaxed">{faq.a}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

export default PricingPage
