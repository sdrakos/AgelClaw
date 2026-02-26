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
            {/* File attachment display */}
            {isUser && message.attachment && (
              <div className="mb-2">
                {message.attachment.previewUrl ? (
                  <img
                    src={message.attachment.previewUrl}
                    alt={message.attachment.name}
                    className="max-w-xs max-h-48 rounded-lg object-contain"
                  />
                ) : (
                  <div className="flex items-center gap-2 bg-blue-400/30 rounded-lg px-3 py-2">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5 flex-shrink-0">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                    </svg>
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">{message.attachment.name}</p>
                      <p className="text-xs opacity-75">
                        {message.attachment.size < 1024
                          ? `${message.attachment.size} B`
                          : message.attachment.size < 1024 * 1024
                            ? `${(message.attachment.size / 1024).toFixed(1)} KB`
                            : `${(message.attachment.size / (1024 * 1024)).toFixed(1)} MB`}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            )}
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
