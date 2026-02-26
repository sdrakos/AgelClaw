const INSTALLER_URL = 'https://raw.githubusercontent.com/sdrakos/AgelClaw/main/install.bat'
const GITHUB_URL = 'https://github.com/sdrakos/AgelClaw'

function DownloadCTA() {
  return (
    <section className="py-24">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <div className="p-12 bg-gradient-to-br from-indigo-950/50 to-purple-950/50 border border-indigo-500/20 rounded-3xl">
          <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
            Ready to Get Started?
          </h2>
          <p className="text-lg text-gray-400 mb-8 max-w-xl mx-auto">
            Download the installer, double-click, and your AI agent will be ready in 5 minutes.
            No programming required.
          </p>

          {/* Main download button */}
          <a
            href={INSTALLER_URL}
            className="group inline-flex items-center gap-3 px-10 py-5 bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xl rounded-2xl transition-all shadow-xl shadow-indigo-600/30 hover:shadow-indigo-500/50 hover:scale-105 mb-6"
          >
            <svg className="w-7 h-7 group-hover:animate-bounce" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
            </svg>
            Download for Windows
          </a>

          {/* Steps */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-6 mt-6 mb-8">
            {[
              { step: '1', text: 'Download & double-click' },
              { step: '2', text: 'Login to Claude' },
              { step: '3', text: 'Start chatting' },
            ].map((item, i) => (
              <div key={i} className="flex items-center gap-2">
                <span className="w-7 h-7 bg-indigo-500/20 border border-indigo-500/30 rounded-full flex items-center justify-center text-xs font-bold text-indigo-400">
                  {item.step}
                </span>
                <span className="text-sm text-gray-400">{item.text}</span>
                {i < 2 && <span className="hidden sm:block text-gray-700 ml-4">→</span>}
              </div>
            ))}
          </div>

          {/* Alternative: developer install */}
          <div className="border-t border-gray-800 pt-6">
            <p className="text-sm text-gray-500 mb-3">For developers:</p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <code className="px-4 py-2 bg-gray-900 border border-gray-800 rounded-lg text-sm text-indigo-300 font-mono">
                pip install git+{GITHUB_URL}.git
              </code>
              <a
                href={GITHUB_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="px-6 py-2 bg-gray-800 hover:bg-gray-700 text-gray-200 text-sm font-medium rounded-lg transition-colors border border-gray-700 flex items-center gap-2"
              >
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
                </svg>
                GitHub
              </a>
            </div>
          </div>

          <p className="mt-6 text-sm text-gray-600">
            Requires Windows 10/11 and a Claude Max or Pro subscription.
          </p>
        </div>
      </div>
    </section>
  )
}

export default DownloadCTA
