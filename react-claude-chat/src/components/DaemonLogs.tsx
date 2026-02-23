import { useEffect, useRef, useState } from 'react';

interface LogEntry {
  id: string;
  type: string;
  time: string;
  text?: string;
  tool?: string;
  session_id?: string;
  reason?: string;
  error?: string;
  duration_s?: number;
  summary?: string;
  tools_used?: string[];
  task_id?: number;
  task_title?: string;
  tasks_launched?: number;
  cycle_session?: string;
}

type DaemonStatus = 'connecting' | 'connected' | 'disconnected';

const TASK_COLORS = [
  'bg-blue-100 text-blue-700 border-blue-300',
  'bg-purple-100 text-purple-700 border-purple-300',
  'bg-amber-100 text-amber-700 border-amber-300',
  'bg-emerald-100 text-emerald-700 border-emerald-300',
  'bg-rose-100 text-rose-700 border-rose-300',
  'bg-cyan-100 text-cyan-700 border-cyan-300',
];

const TASK_BORDER_COLORS = [
  'border-l-blue-400',
  'border-l-purple-400',
  'border-l-amber-400',
  'border-l-emerald-400',
  'border-l-rose-400',
  'border-l-cyan-400',
];

function getTaskColor(taskId: number) {
  return TASK_COLORS[taskId % TASK_COLORS.length];
}

function getTaskBorderColor(taskId: number) {
  return TASK_BORDER_COLORS[taskId % TASK_BORDER_COLORS.length];
}

function TaskBadge({ taskId, taskTitle }: { taskId: number; taskTitle?: string }) {
  const color = getTaskColor(taskId);
  return (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold border ${color}`}>
      #{taskId}{taskTitle ? ` ${taskTitle}` : ''}
    </span>
  );
}

function DaemonLogs() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [status, setStatus] = useState<DaemonStatus>('connecting');
  const [daemonState, setDaemonState] = useState<string>('unknown');
  const [runningCount, setRunningCount] = useState(0);
  const [collapsed, setCollapsed] = useState(false);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimer = useRef<number | null>(null);

  const addLog = (entry: LogEntry) => {
    setLogs(prev => {
      const next = [...prev, entry];
      // Keep last 200 entries
      return next.length > 200 ? next.slice(-200) : next;
    });
  };

  const connect = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    setStatus('connecting');
    const es = new EventSource('/daemon/events');
    eventSourceRef.current = es;

    es.onopen = () => {
      setStatus('connected');
      addLog({
        id: Date.now().toString(),
        type: 'system',
        time: new Date().toISOString(),
        text: 'Connected to daemon',
      });
    };

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const entry: LogEntry = {
          id: Date.now().toString() + Math.random(),
          ...data,
        };

        if (data.type === 'connected') {
          setDaemonState(data.status?.state || 'idle');
          const taskCount = Object.keys(data.status?.running_tasks || {}).length;
          setRunningCount(taskCount);
          return;
        }

        // Track running task count
        if (data.type === 'task_start') {
          setRunningCount(prev => prev + 1);
          setDaemonState('running');
        } else if (data.type === 'task_end' || data.type === 'task_error') {
          setRunningCount(prev => {
            const next = Math.max(0, prev - 1);
            if (next === 0) setDaemonState('idle');
            return next;
          });
        }

        addLog(entry);
      } catch {
        // ignore
      }
    };

    es.onerror = () => {
      es.close();
      setStatus('disconnected');
      setDaemonState('unknown');
      setRunningCount(0);
      // Reconnect after 5 seconds
      reconnectTimer.current = window.setTimeout(connect, 5000);
    };
  };

  useEffect(() => {
    connect();
    return () => {
      eventSourceRef.current?.close();
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    };
  }, []);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const statusColor = {
    connecting: 'bg-yellow-500',
    connected: 'bg-green-500',
    disconnected: 'bg-red-500',
  };

  const stateLabel = {
    idle: { text: 'Idle', color: 'text-gray-500' },
    running: { text: 'Running', color: 'text-blue-600' },
    error: { text: 'Error', color: 'text-red-600' },
    unknown: { text: 'Offline', color: 'text-gray-400' },
  };

  const formatTime = (iso: string) => {
    try {
      return new Date(iso).toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
    } catch {
      return '';
    }
  };

  const renderEntry = (entry: LogEntry) => {
    switch (entry.type) {
      case 'system':
        return (
          <div key={entry.id} className="px-3 py-1.5 text-xs text-gray-400 italic">
            {entry.text}
          </div>
        );

      case 'cycle_start':
        return (
          <div key={entry.id} className="px-3 py-2 border-t border-blue-100 bg-blue-50/50">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
              <span className="text-xs font-semibold text-blue-700">Cycle Started</span>
              <span className="text-xs text-gray-400 ml-auto">{formatTime(entry.time)}</span>
            </div>
            <div className="text-xs text-gray-500 mt-0.5 pl-4">
              {entry.session_id} &middot; {entry.reason}
            </div>
          </div>
        );

      case 'task_start':
        return (
          <div key={entry.id} className={`px-3 py-2 border-l-4 ${entry.task_id !== undefined ? getTaskBorderColor(entry.task_id) : 'border-l-blue-400'} bg-gray-50/80`}>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
              {entry.task_id !== undefined && <TaskBadge taskId={entry.task_id} taskTitle={entry.task_title} />}
              <span className="text-xs font-medium text-gray-600">started</span>
              <span className="text-xs text-gray-400 ml-auto">{formatTime(entry.time)}</span>
            </div>
          </div>
        );

      case 'task_end':
        return (
          <div key={entry.id} className={`px-3 py-2 border-l-4 ${entry.task_id !== undefined ? getTaskBorderColor(entry.task_id) : 'border-l-green-400'} bg-green-50/50`}>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-green-500"></span>
              {entry.task_id !== undefined && <TaskBadge taskId={entry.task_id} taskTitle={entry.task_title} />}
              <span className="text-xs font-medium text-green-700">completed</span>
              <span className="text-xs text-gray-400 ml-auto">{formatTime(entry.time)}</span>
            </div>
            {entry.duration_s !== undefined && (
              <div className="text-xs text-gray-500 mt-0.5 pl-4">
                {entry.duration_s}s &middot; {entry.tools_used?.length || 0} tools
              </div>
            )}
            {entry.summary && (
              <p className="text-xs text-gray-600 mt-1 pl-4 line-clamp-3">
                {entry.summary.slice(0, 300)}
              </p>
            )}
          </div>
        );

      case 'task_error':
        return (
          <div key={entry.id} className={`px-3 py-2 border-l-4 ${entry.task_id !== undefined ? getTaskBorderColor(entry.task_id) : 'border-l-red-400'} bg-red-50/50`}>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-red-500"></span>
              {entry.task_id !== undefined && <TaskBadge taskId={entry.task_id} taskTitle={entry.task_title} />}
              <span className="text-xs font-medium text-red-700">failed</span>
              <span className="text-xs text-gray-400 ml-auto">{formatTime(entry.time)}</span>
            </div>
            <p className="text-xs text-red-600 mt-0.5 pl-4">{entry.error}</p>
          </div>
        );

      case 'agent_text':
        return (
          <div key={entry.id} className={`px-3 py-1.5 ${entry.task_id !== undefined ? `border-l-2 ${getTaskBorderColor(entry.task_id)}` : ''}`}>
            <div className="flex items-start gap-2">
              <span className="text-xs text-purple-500 font-mono mt-0.5 flex-shrink-0">AI</span>
              {entry.task_id !== undefined && <TaskBadge taskId={entry.task_id} />}
              <p className="text-xs text-gray-700 break-words leading-relaxed">
                {entry.text && entry.text.length > 200 ? entry.text.slice(0, 200) + '...' : entry.text}
              </p>
            </div>
            <div className="text-[10px] text-gray-300 pl-6">{formatTime(entry.time)}</div>
          </div>
        );

      case 'tool_use':
        return (
          <div key={entry.id} className={`px-3 py-1 flex items-center gap-2 ${entry.task_id !== undefined ? `border-l-2 ${getTaskBorderColor(entry.task_id)}` : ''}`}>
            <span className="text-xs text-orange-500 font-mono flex-shrink-0">
              &gt;
            </span>
            {entry.task_id !== undefined && <TaskBadge taskId={entry.task_id} />}
            <span className="text-xs text-orange-700 font-medium">{entry.tool}</span>
            <span className="text-[10px] text-gray-300 ml-auto">{formatTime(entry.time)}</span>
          </div>
        );

      case 'cycle_end':
        return (
          <div key={entry.id} className="px-3 py-2 border-t border-green-100 bg-green-50/50">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-green-500"></span>
              <span className="text-xs font-semibold text-green-700">Cycle Complete</span>
              <span className="text-xs text-gray-400 ml-auto">{formatTime(entry.time)}</span>
            </div>
            {(entry.duration_s !== undefined || entry.tasks_launched !== undefined) && (
              <div className="text-xs text-gray-500 mt-0.5 pl-4">
                {entry.duration_s !== undefined && `${entry.duration_s}s`}
                {entry.tasks_launched !== undefined && ` \u00b7 ${entry.tasks_launched} task${entry.tasks_launched !== 1 ? 's' : ''} launched`}
                {entry.tools_used && ` \u00b7 ${entry.tools_used.length} tools`}
              </div>
            )}
            {entry.summary && (
              <p className="text-xs text-gray-600 mt-1 pl-4 line-clamp-3">
                {entry.summary.slice(0, 300)}
              </p>
            )}
          </div>
        );

      case 'cycle_error':
        return (
          <div key={entry.id} className="px-3 py-2 border-t border-red-100 bg-red-50/50">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-red-500"></span>
              <span className="text-xs font-semibold text-red-700">Cycle Error</span>
              <span className="text-xs text-gray-400 ml-auto">{formatTime(entry.time)}</span>
            </div>
            <p className="text-xs text-red-600 mt-0.5 pl-4">{entry.error}</p>
          </div>
        );

      default:
        return (
          <div key={entry.id} className="px-3 py-1 text-xs text-gray-400">
            [{entry.type}] {JSON.stringify(entry).slice(0, 120)}
          </div>
        );
    }
  };

  const currentState = stateLabel[daemonState as keyof typeof stateLabel] || stateLabel.unknown;

  return (
    <div className="flex flex-col h-full bg-white border-l border-gray-200">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200 bg-gray-50 flex-shrink-0">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${statusColor[status]}`}></span>
          <span className="text-sm font-semibold text-gray-700">Daemon</span>
          <span className={`text-xs font-medium ${currentState.color}`}>
            {currentState.text}{daemonState === 'running' && runningCount > 0 ? ` (${runningCount})` : ''}
          </span>
        </div>
        <div className="flex items-center gap-1">
          {status === 'disconnected' && (
            <button
              onClick={connect}
              className="text-xs px-2 py-0.5 rounded bg-blue-100 text-blue-700 hover:bg-blue-200 transition-colors"
            >
              Reconnect
            </button>
          )}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors"
          >
            {collapsed ? 'Expand' : 'Collapse'}
          </button>
          <button
            onClick={() => setLogs([])}
            className="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors"
          >
            Clear
          </button>
        </div>
      </div>

      {/* Logs */}
      {!collapsed && (
        <div className="flex-1 overflow-y-auto divide-y divide-gray-50">
          {logs.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center p-4">
              <div className="text-gray-300 text-3xl mb-2">
                {status === 'connected' ? '~' : '!'}
              </div>
              <p className="text-xs text-gray-400">
                {status === 'connected'
                  ? 'Waiting for daemon activity...'
                  : status === 'connecting'
                    ? 'Connecting to daemon...'
                    : 'Daemon not reachable. Is it running?'}
              </p>
              {status === 'connected' && (
                <p className="text-[10px] text-gray-300 mt-2">
                  Logs appear here when the daemon processes tasks
                </p>
              )}
            </div>
          ) : (
            <>
              {logs.map(renderEntry)}
              <div ref={logsEndRef} />
            </>
          )}
        </div>
      )}

      {/* Footer stats */}
      <div className="flex items-center justify-between px-3 py-1.5 border-t border-gray-100 bg-gray-50 text-[10px] text-gray-400 flex-shrink-0">
        <span>{logs.length} entries</span>
        <span>Port 8420</span>
      </div>
    </div>
  );
}

export default DaemonLogs;
