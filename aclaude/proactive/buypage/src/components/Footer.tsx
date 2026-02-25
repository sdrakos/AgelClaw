import { Link } from 'react-router-dom'

function Footer() {
  return (
    <footer className="border-t border-gray-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          {/* Brand */}
          <div className="md:col-span-2">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-8 h-8 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center">
                <span className="text-white font-bold text-sm">A</span>
              </div>
              <span className="font-bold text-lg text-white">AgelClaw</span>
            </div>
            <p className="text-sm text-gray-400 max-w-sm leading-relaxed">
              An autonomous AI agent that runs locally on your machine. Persistent memory,
              downloadable skills, multi-AI routing, and 24/7 background tasks.
            </p>
          </div>

          {/* Links */}
          <div>
            <h4 className="text-sm font-semibold text-white mb-4">Product</h4>
            <ul className="space-y-2.5">
              <li><Link to="/skills" className="text-sm text-gray-400 hover:text-white transition-colors">Skills</Link></li>
              <li><Link to="/pricing" className="text-sm text-gray-400 hover:text-white transition-colors">Pricing</Link></li>
              <li>
                <a href="https://github.com/sdrakos/AgelClaw/releases/download/v2.1/AgelClaw-v2.1-win64.zip" target="_blank" rel="noopener noreferrer" className="text-sm text-gray-400 hover:text-white transition-colors">
                  Download
                </a>
              </li>
            </ul>
          </div>

          <div>
            <h4 className="text-sm font-semibold text-white mb-4">Resources</h4>
            <ul className="space-y-2.5">
              <li>
                <a href="https://github.com/sdrakos/AgelClaw" target="_blank" rel="noopener noreferrer" className="text-sm text-gray-400 hover:text-white transition-colors">
                  GitHub
                </a>
              </li>
              <li>
                <a href="https://github.com/sdrakos/AgelClaw/issues" target="_blank" rel="noopener noreferrer" className="text-sm text-gray-400 hover:text-white transition-colors">
                  Issues
                </a>
              </li>
              <li>
                <a href="mailto:info@agelclaw.com" className="text-sm text-gray-400 hover:text-white transition-colors">
                  Contact
                </a>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-12 pt-8 border-t border-gray-800/50 flex flex-col sm:flex-row justify-between items-center gap-4">
          <p className="text-sm text-gray-500">&copy; {new Date().getFullYear()} AgelClaw. All rights reserved.</p>
          <p className="text-sm text-gray-600">Built with AI, for AI.</p>
        </div>
      </div>
    </footer>
  )
}

export default Footer
