import { useState } from 'react'
import { ChatConfig } from '../types'

interface ApiKeyModalProps {
  config: ChatConfig
  onSave: (config: ChatConfig) => void
  onClose: () => void
}

function ApiKeyModal({ config, onSave, onClose }: ApiKeyModalProps) {
  const [apiKey, setApiKey] = useState(config.apiKey)
  const [model, setModel] = useState(config.model)
  const [maxTokens, setMaxTokens] = useState(config.maxTokens)

  const handleSave = () => {
    if (!apiKey.trim()) {
      alert('Παρακαλώ εισάγετε το API key')
      return
    }
    onSave({ apiKey, model, maxTokens })
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6">
        <h2 className="text-2xl font-bold text-gray-800 mb-4">Ρυθμίσεις API</h2>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Anthropic API Key
            </label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="sk-ant-..."
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-claude-500"
            />
            <p className="text-xs text-gray-500 mt-1">
              Λάβε το API key από το{' '}
              <a
                href="https://console.anthropic.com/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-claude-500 hover:underline"
              >
                Anthropic Console
              </a>
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Model
            </label>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-claude-500"
            >
              <option value="claude-3-5-sonnet-20241022">Claude 3.5 Sonnet (Recommended)</option>
              <option value="claude-3-opus-20240229">Claude 3 Opus</option>
              <option value="claude-3-sonnet-20240229">Claude 3 Sonnet</option>
              <option value="claude-3-haiku-20240307">Claude 3 Haiku</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Max Tokens
            </label>
            <input
              type="number"
              value={maxTokens}
              onChange={(e) => setMaxTokens(Number(e.target.value))}
              min="1"
              max="8192"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-claude-500"
            />
          </div>
        </div>

        <div className="flex space-x-3 mt-6">
          <button
            onClick={handleSave}
            className="flex-1 px-4 py-2 bg-gradient-to-r from-claude-500 to-claude-600 text-white rounded-lg hover:from-claude-600 hover:to-claude-700 transition-all font-medium"
          >
            Αποθήκευση
          </button>
          {config.apiKey && (
            <button
              onClick={onClose}
              className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
            >
              Ακύρωση
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export default ApiKeyModal
