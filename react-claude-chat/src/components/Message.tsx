import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Message as MessageType } from '../types';

interface MessageProps {
  message: MessageType;
}

function Message({ message }: MessageProps) {
  const isUser = message.role === 'user';
  const time = message.timestamp.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
  });

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div className={`flex gap-3 max-w-3xl ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
        {/* Avatar */}
        <div
          className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
            isUser
              ? 'bg-blue-500 text-white'
              : 'bg-gradient-to-br from-orange-400 to-pink-500 text-white'
          }`}
        >
          <span className="text-sm font-medium">{isUser ? 'U' : 'C'}</span>
        </div>

        {/* Message bubble */}
        <div className="flex flex-col gap-1">
          <div
            className={`px-4 py-3 rounded-2xl ${
              isUser
                ? 'bg-blue-500 text-white rounded-tr-sm'
                : 'bg-white border border-gray-200 text-gray-900 rounded-tl-sm'
            }`}
          >
            {isUser ? (
              <p className="whitespace-pre-wrap">{message.content}</p>
            ) : (
              <div className="prose prose-sm max-w-none prose-p:my-2 prose-pre:my-2">
                <ReactMarkdown
                  components={{
                    code({ className, children, ...props }) {
                      const match = /language-(\w+)/.exec(className || '');
                      const isBlock = String(children).includes('\n') || match;
                      return isBlock && match ? (
                        <SyntaxHighlighter
                          style={vscDarkPlus as Record<string, React.CSSProperties>}
                          language={match[1]}
                          PreTag="div"
                        >
                          {String(children).replace(/\n$/, '')}
                        </SyntaxHighlighter>
                      ) : (
                        <code className="bg-gray-100 text-pink-600 px-1 rounded" {...props}>
                          {children}
                        </code>
                      );
                    },
                  }}
                >
                  {message.content}
                </ReactMarkdown>
              </div>
            )}
          </div>
          <span
            className={`text-xs text-gray-400 px-2 ${isUser ? 'text-right' : 'text-left'}`}
          >
            {time}
          </span>
        </div>
      </div>
    </div>
  );
}

export default Message;
