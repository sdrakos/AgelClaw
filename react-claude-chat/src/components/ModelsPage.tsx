import { useState } from 'react';

interface ModelInfo {
  id: string;
  name: string;
  description: string;
  context: string;
  speed: 'fast' | 'medium' | 'slow';
}

interface ProviderGroup {
  provider: string;
  icon: string;
  models: ModelInfo[];
}

const MODEL_GROUPS: ProviderGroup[] = [
  {
    provider: 'Anthropic',
    icon: '🟤',
    models: [
      { id: 'claude-opus-4-6', name: 'Claude Opus 4.6', description: 'Most capable model, best for complex tasks', context: '1M', speed: 'slow' },
      { id: 'claude-sonnet-4-5-20250929', name: 'Claude Sonnet 4.5', description: 'Balanced performance and speed', context: '200K', speed: 'medium' },
      { id: 'claude-sonnet-4-20250514', name: 'Claude Sonnet 4', description: 'Fast and capable', context: '200K', speed: 'medium' },
      { id: 'claude-haiku-4-5-20251001', name: 'Claude Haiku 4.5', description: 'Fastest Claude model', context: '200K', speed: 'fast' },
      { id: 'claude-3-5-sonnet-20241022', name: 'Claude 3.5 Sonnet', description: 'Previous gen, still strong', context: '200K', speed: 'medium' },
      { id: 'claude-3-5-haiku-20241022', name: 'Claude 3.5 Haiku', description: 'Previous gen, very fast', context: '200K', speed: 'fast' },
      { id: 'claude-3-haiku-20240307', name: 'Claude 3 Haiku', description: 'Lightweight and economical', context: '200K', speed: 'fast' },
    ],
  },
  {
    provider: 'OpenAI',
    icon: '🟢',
    models: [
      { id: 'gpt-4.1', name: 'GPT-4.1', description: 'Latest GPT model', context: '1M', speed: 'medium' },
      { id: 'gpt-4.1-mini', name: 'GPT-4.1 Mini', description: 'Smaller, faster GPT-4.1', context: '1M', speed: 'fast' },
      { id: 'gpt-4.1-nano', name: 'GPT-4.1 Nano', description: 'Fastest GPT model', context: '1M', speed: 'fast' },
      { id: 'o3', name: 'o3', description: 'Reasoning model', context: '200K', speed: 'slow' },
      { id: 'o4-mini', name: 'o4-mini', description: 'Fast reasoning model', context: '200K', speed: 'medium' },
      { id: 'gpt-4o', name: 'GPT-4o', description: 'Multimodal GPT-4', context: '128K', speed: 'medium' },
    ],
  },
  {
    provider: 'Google',
    icon: '🔵',
    models: [
      { id: 'gemini-2.5-pro', name: 'Gemini 2.5 Pro', description: 'Most capable Gemini', context: '1M', speed: 'medium' },
      { id: 'gemini-2.5-flash', name: 'Gemini 2.5 Flash', description: 'Fast Gemini model', context: '1M', speed: 'fast' },
      { id: 'gemini-2.0-flash', name: 'Gemini 2.0 Flash', description: 'Previous gen flash', context: '1M', speed: 'fast' },
    ],
  },
  {
    provider: 'xAI',
    icon: '⚡',
    models: [
      { id: 'grok-3', name: 'Grok 3', description: 'Latest Grok model', context: '131K', speed: 'medium' },
      { id: 'grok-3-mini', name: 'Grok 3 Mini', description: 'Fast Grok model', context: '131K', speed: 'fast' },
    ],
  },
];

const speedColors = {
  fast: 'bg-green-100 text-green-700',
  medium: 'bg-yellow-100 text-yellow-700',
  slow: 'bg-orange-100 text-orange-700',
};

interface ModelsPageProps {
  selectedModel: string;
  onSelectModel: (modelId: string) => void;
}

function ModelsPage({ selectedModel, onSelectModel }: ModelsPageProps) {
  const [expandedProvider, setExpandedProvider] = useState<string | null>('Anthropic');

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-3xl mx-auto">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Model Selection</h1>
        <p className="text-sm text-gray-500 mb-6">
          Choose the AI model for your agent. Current:{' '}
          <span className="font-medium text-blue-600">{selectedModel}</span>
        </p>

        <div className="space-y-4">
          {MODEL_GROUPS.map((group) => (
            <div key={group.provider} className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <button
                onClick={() =>
                  setExpandedProvider(expandedProvider === group.provider ? null : group.provider)
                }
                className="w-full flex items-center justify-between px-5 py-3 hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <span className="text-xl">{group.icon}</span>
                  <span className="font-semibold text-gray-900">{group.provider}</span>
                  <span className="text-xs text-gray-400">{group.models.length} models</span>
                </div>
                <span className="text-gray-400 text-sm">
                  {expandedProvider === group.provider ? '▲' : '▼'}
                </span>
              </button>

              {expandedProvider === group.provider && (
                <div className="border-t border-gray-100">
                  {group.models.map((model) => (
                    <button
                      key={model.id}
                      onClick={() => onSelectModel(model.id)}
                      className={`w-full flex items-center gap-4 px-5 py-3 text-left transition-colors ${
                        selectedModel === model.id
                          ? 'bg-blue-50 border-l-4 border-blue-500'
                          : 'hover:bg-gray-50 border-l-4 border-transparent'
                      }`}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-sm text-gray-900">{model.name}</span>
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${speedColors[model.speed]}`}>
                            {model.speed}
                          </span>
                          <span className="text-[10px] text-gray-400">{model.context} ctx</span>
                        </div>
                        <p className="text-xs text-gray-500 mt-0.5">{model.description}</p>
                      </div>
                      {selectedModel === model.id && (
                        <span className="text-blue-500 text-sm font-medium">Active</span>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default ModelsPage;
