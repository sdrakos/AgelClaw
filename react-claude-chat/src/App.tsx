import { useState, useRef } from 'react';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import MessageList from './components/MessageList';
import InputArea from './components/InputArea';
import DaemonLogs from './components/DaemonLogs';
import SkillsPage from './components/SkillsPage';
import ModelsPage from './components/ModelsPage';
import { Message } from './types';

function App() {
  const [activePage, setActivePage] = useState('chat');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [showLogs, setShowLogs] = useState(true);
  const [selectedModel, setSelectedModel] = useState('claude-opus-4-6');
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = async (content: string) => {
    if (!content.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: content.trim(),
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);

    const assistantId = (Date.now() + 1).toString();
    setMessages(prev => [
      ...prev,
      { id: assistantId, role: 'assistant', content: '', timestamp: new Date() },
    ]);

    try {
      abortRef.current = new AbortController();

      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: content.trim(),
          model: selectedModel,
          history: messages.map(m => ({ role: m.role, content: m.content })),
        }),
        signal: abortRef.current.signal,
      });

      if (!response.ok) throw new Error(`Server error: ${response.status}`);

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response stream');

      const decoder = new TextDecoder();
      let buffer = '';
      let fullText = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const data = line.slice(6).trim();
          if (data === '[DONE]') continue;

          try {
            const event = JSON.parse(data);
            if (event.type === 'text') {
              fullText += event.content;
              setMessages(prev =>
                prev.map(m =>
                  m.id === assistantId ? { ...m, content: fullText } : m,
                ),
              );
            } else if (event.type === 'error') {
              fullText += `\n\n**Error:** ${event.content}`;
              setMessages(prev =>
                prev.map(m =>
                  m.id === assistantId ? { ...m, content: fullText } : m,
                ),
              );
            }
          } catch {
            // skip malformed JSON
          }
        }
      }

      if (!fullText) {
        setMessages(prev =>
          prev.map(m =>
            m.id === assistantId
              ? { ...m, content: 'No response received from agent.' }
              : m,
          ),
        );
      }
    } catch (error) {
      if ((error as Error).name === 'AbortError') return;
      const errorText = `Error: ${error instanceof Error ? error.message : 'Failed to get response'}`;
      setMessages(prev => {
        const last = prev[prev.length - 1];
        if (last && last.role === 'assistant' && !last.content) {
          return prev.map((m, i) =>
            i === prev.length - 1 ? { ...m, content: errorText } : m,
          );
        }
        return prev;
      });
    } finally {
      setIsLoading(false);
      abortRef.current = null;
    }
  };

  return (
    <div className="flex h-screen bg-gray-50">
      <Sidebar activePage={activePage} onPageChange={setActivePage} />

      <div className="flex flex-col flex-1 min-w-0">
        <Header showLogs={showLogs} onToggleLogs={() => setShowLogs(!showLogs)} />

        <div className="flex flex-1 overflow-hidden">
          {activePage === 'chat' && (
            <div className="flex flex-col flex-1 min-w-0">
              <MessageList messages={messages} isLoading={isLoading} />
              <InputArea onSendMessage={sendMessage} disabled={isLoading} />
            </div>
          )}

          {activePage === 'skills' && <SkillsPage />}

          {activePage === 'models' && (
            <ModelsPage selectedModel={selectedModel} onSelectModel={setSelectedModel} />
          )}

          {/* Daemon logs panel - only show on chat page */}
          {activePage === 'chat' && showLogs && (
            <div className="w-80 xl:w-96 flex-shrink-0 hidden md:flex">
              <DaemonLogs />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
