import { useState, useEffect, useCallback } from 'react';

interface Settings {
  anthropic_api_key: string;
  openai_api_key: string;
  default_provider: string;
  telegram_bot_token: string;
  telegram_allowed_users: string;
  outlook_client_id: string;
  outlook_client_secret: string;
  outlook_tenant_id: string;
  outlook_user_email: string;
  api_port: number;
  daemon_port: number;
  cost_limit_daily: number;
  max_concurrent_tasks: number;
  check_interval: number;
  is_configured: boolean;
  has_telegram: boolean;
  has_outlook: boolean;
}

interface ServiceStatus {
  api_server: boolean;
  daemon: boolean;
  telegram: boolean;
}

const tabs = [
  { id: 'ai', label: 'AI Providers' },
  { id: 'telegram', label: 'Telegram' },
  { id: 'email', label: 'Email' },
  { id: 'system', label: 'System' },
  { id: 'services', label: 'Services' },
];

interface SettingsPageProps {
  firstRun?: boolean;
}

function SettingsPage({ firstRun }: SettingsPageProps) {
  const [activeTab, setActiveTab] = useState('ai');
  const [settings, setSettings] = useState<Settings | null>(null);
  const [services, setServices] = useState<ServiceStatus | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState('');
  const [loading, setLoading] = useState(true);

  const fetchSettings = useCallback(async () => {
    try {
      const res = await fetch('/api/settings');
      const data = await res.json();
      setSettings(data);
    } catch {
      setSaveMsg('Failed to load settings');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchServices = useCallback(async () => {
    try {
      const res = await fetch('/api/services/status');
      setServices(await res.json());
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    fetchSettings();
    fetchServices();
    const interval = setInterval(fetchServices, 5000);
    return () => clearInterval(interval);
  }, [fetchSettings, fetchServices]);

  const handleSave = async () => {
    if (!settings) return;
    setSaving(true);
    setSaveMsg('');
    try {
      const res = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings),
      });
      if (res.ok) {
        setSaveMsg('Settings saved successfully');
        await fetchSettings();
      } else {
        setSaveMsg('Failed to save settings');
      }
    } catch {
      setSaveMsg('Network error saving settings');
    } finally {
      setSaving(false);
      setTimeout(() => setSaveMsg(''), 3000);
    }
  };

  const handleServiceAction = async (service: string, action: string) => {
    try {
      await fetch(`/api/services/${service}/${action}`, { method: 'POST' });
      // Wait a moment for service to start/stop, then refresh
      setTimeout(fetchServices, 1500);
    } catch {
      // ignore
    }
  };

  const updateField = (field: keyof Settings, value: string | number) => {
    if (!settings) return;
    setSettings({ ...settings, [field]: value });
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-gray-500">Loading settings...</div>
      </div>
    );
  }

  if (!settings) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-red-500">Failed to load settings</div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto bg-gray-50">
      <div className="max-w-3xl mx-auto px-6 py-8">
        {/* First-run welcome banner */}
        {firstRun && (
          <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <h2 className="text-lg font-semibold text-blue-900">Welcome to Agel Agent!</h2>
            <p className="text-sm text-blue-700 mt-1">
              Let's get you set up. Add at least one AI provider API key below, then click Save.
            </p>
          </div>
        )}

        <h1 className="text-2xl font-bold text-gray-900 mb-6">Settings</h1>

        {/* Tab navigation */}
        <div className="flex border-b border-gray-200 mb-6">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="space-y-6">
          {activeTab === 'ai' && (
            <div className="space-y-4">
              <FieldGroup label="Anthropic (Claude) API Key">
                <PasswordInput
                  value={settings.anthropic_api_key}
                  onChange={(v) => updateField('anthropic_api_key', v)}
                  placeholder="sk-ant-..."
                />
                <p className="text-xs text-gray-500 mt-1">
                  Using Claude subscription? Run <code className="bg-gray-100 px-1 rounded">claude login</code> in terminal — no API key needed.
                </p>
              </FieldGroup>
              <FieldGroup label="OpenAI API Key">
                <PasswordInput
                  value={settings.openai_api_key}
                  onChange={(v) => updateField('openai_api_key', v)}
                  placeholder="sk-..."
                />
              </FieldGroup>
              <FieldGroup label="Default Provider">
                <select
                  value={settings.default_provider}
                  onChange={(e) => updateField('default_provider', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="auto">Auto (use best available)</option>
                  <option value="claude">Claude (Anthropic)</option>
                  <option value="openai">OpenAI</option>
                </select>
              </FieldGroup>
              <SaveButton saving={saving} saveMsg={saveMsg} onSave={handleSave} />
            </div>
          )}

          {activeTab === 'telegram' && (
            <div className="space-y-4">
              <FieldGroup label="Bot Token">
                <PasswordInput
                  value={settings.telegram_bot_token}
                  onChange={(v) => updateField('telegram_bot_token', v)}
                  placeholder="123456:ABC-DEF..."
                />
                <p className="text-xs text-gray-500 mt-1">
                  Get one from{' '}
                  <a
                    href="https://t.me/BotFather"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-500 hover:underline"
                  >
                    @BotFather
                  </a>{' '}
                  on Telegram.
                </p>
              </FieldGroup>
              <FieldGroup label="Allowed Users">
                <input
                  type="text"
                  value={settings.telegram_allowed_users}
                  onChange={(e) => updateField('telegram_allowed_users', e.target.value)}
                  placeholder="user_id1,user_id2"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Comma-separated Telegram user IDs. Leave empty to allow all.
                </p>
              </FieldGroup>
              <SaveButton saving={saving} saveMsg={saveMsg} onSave={handleSave} />
            </div>
          )}

          {activeTab === 'email' && (
            <div className="space-y-4">
              <h3 className="text-sm font-semibold text-gray-700">Outlook / Microsoft Graph</h3>
              <FieldGroup label="Client ID">
                <PasswordInput
                  value={settings.outlook_client_id}
                  onChange={(v) => updateField('outlook_client_id', v)}
                  placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                />
              </FieldGroup>
              <FieldGroup label="Client Secret">
                <PasswordInput
                  value={settings.outlook_client_secret}
                  onChange={(v) => updateField('outlook_client_secret', v)}
                  placeholder="xxxxx~xxxxx"
                />
              </FieldGroup>
              <FieldGroup label="Tenant ID">
                <input
                  type="text"
                  value={settings.outlook_tenant_id}
                  onChange={(e) => updateField('outlook_tenant_id', e.target.value)}
                  placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </FieldGroup>
              <FieldGroup label="User Email">
                <input
                  type="email"
                  value={settings.outlook_user_email}
                  onChange={(e) => updateField('outlook_user_email', e.target.value)}
                  placeholder="user@example.com"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </FieldGroup>
              <SaveButton saving={saving} saveMsg={saveMsg} onSave={handleSave} />
            </div>
          )}

          {activeTab === 'system' && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <FieldGroup label="API Port">
                  <input
                    type="number"
                    value={settings.api_port}
                    onChange={(e) => updateField('api_port', parseInt(e.target.value) || 8000)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </FieldGroup>
                <FieldGroup label="Daemon Port">
                  <input
                    type="number"
                    value={settings.daemon_port}
                    onChange={(e) => updateField('daemon_port', parseInt(e.target.value) || 8420)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </FieldGroup>
              </div>
              <FieldGroup label="Daily Cost Limit ($)">
                <input
                  type="number"
                  step="0.5"
                  value={settings.cost_limit_daily}
                  onChange={(e) => updateField('cost_limit_daily', parseFloat(e.target.value) || 10)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </FieldGroup>
              <FieldGroup label="Max Concurrent Tasks">
                <input
                  type="number"
                  value={settings.max_concurrent_tasks}
                  onChange={(e) => updateField('max_concurrent_tasks', parseInt(e.target.value) || 3)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </FieldGroup>
              <FieldGroup label="Check Interval (seconds)">
                <input
                  type="number"
                  value={settings.check_interval}
                  onChange={(e) => updateField('check_interval', parseInt(e.target.value) || 300)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
                <p className="text-xs text-gray-500 mt-1">
                  How often the daemon checks for new tasks (in seconds).
                </p>
              </FieldGroup>
              <SaveButton saving={saving} saveMsg={saveMsg} onSave={handleSave} />
            </div>
          )}

          {activeTab === 'services' && (
            <div className="space-y-4">
              <ServiceRow
                name="API Server"
                running={services?.api_server ?? false}
                onAction={() => {}}
                locked
              />
              <ServiceRow
                name="Daemon"
                running={services?.daemon ?? false}
                onAction={(action) => handleServiceAction('daemon', action)}
              />
              <ServiceRow
                name="Telegram Bot"
                running={services?.telegram ?? false}
                onAction={(action) => handleServiceAction('telegram', action)}
              />
              <div className="flex gap-2 pt-4 border-t border-gray-200">
                <button
                  onClick={() => handleServiceAction('all', 'start')}
                  className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm hover:bg-green-700 transition-colors"
                >
                  Start All
                </button>
                <button
                  onClick={() => handleServiceAction('all', 'stop')}
                  className="px-4 py-2 bg-red-600 text-white rounded-lg text-sm hover:bg-red-700 transition-colors"
                >
                  Stop All
                </button>
                <button
                  onClick={() => handleServiceAction('all', 'restart')}
                  className="px-4 py-2 bg-yellow-600 text-white rounded-lg text-sm hover:bg-yellow-700 transition-colors"
                >
                  Restart All
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Helper Components ────────────────────────────────────────────── */

function FieldGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      {children}
    </div>
  );
}

function PasswordInput({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
}) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <input
        type={visible ? 'text' : 'password'}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
      />
      <button
        type="button"
        onClick={() => setVisible(!visible)}
        className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 text-xs"
      >
        {visible ? 'Hide' : 'Show'}
      </button>
    </div>
  );
}

function SaveButton({
  saving,
  saveMsg,
  onSave,
}: {
  saving: boolean;
  saveMsg: string;
  onSave: () => void;
}) {
  return (
    <div className="flex items-center gap-3 pt-2">
      <button
        onClick={onSave}
        disabled={saving}
        className="px-5 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
      >
        {saving ? 'Saving...' : 'Save'}
      </button>
      {saveMsg && (
        <span
          className={`text-sm ${saveMsg.includes('success') ? 'text-green-600' : 'text-red-600'}`}
        >
          {saveMsg}
        </span>
      )}
    </div>
  );
}

function ServiceRow({
  name,
  running,
  onAction,
  locked,
}: {
  name: string;
  running: boolean;
  onAction: (action: string) => void;
  locked?: boolean;
}) {
  return (
    <div className="flex items-center justify-between p-3 bg-white rounded-lg border border-gray-200">
      <div className="flex items-center gap-3">
        <div className={`w-2.5 h-2.5 rounded-full ${running ? 'bg-green-500' : 'bg-red-400'}`} />
        <span className="text-sm font-medium text-gray-800">{name}</span>
        <span className={`text-xs ${running ? 'text-green-600' : 'text-gray-400'}`}>
          {running ? 'Running' : 'Stopped'}
        </span>
      </div>
      {!locked && (
        <div className="flex gap-1.5">
          {!running ? (
            <button
              onClick={() => onAction('start')}
              className="px-3 py-1 bg-green-100 text-green-700 rounded text-xs font-medium hover:bg-green-200 transition-colors"
            >
              Start
            </button>
          ) : (
            <>
              <button
                onClick={() => onAction('stop')}
                className="px-3 py-1 bg-red-100 text-red-700 rounded text-xs font-medium hover:bg-red-200 transition-colors"
              >
                Stop
              </button>
              <button
                onClick={() => onAction('restart')}
                className="px-3 py-1 bg-yellow-100 text-yellow-700 rounded text-xs font-medium hover:bg-yellow-200 transition-colors"
              >
                Restart
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default SettingsPage;
