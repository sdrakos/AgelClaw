import { useState, KeyboardEvent, useRef, useEffect, DragEvent } from 'react';
import { FileAttachment } from '../types';

interface InputAreaProps {
  onSendMessage: (content: string, file?: File) => void;
  disabled: boolean;
}

function InputArea({ onSendMessage, disabled }: InputAreaProps) {
  const [input, setInput] = useState('');
  const [attachment, setAttachment] = useState<FileAttachment | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!disabled && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [disabled]);

  const handleSubmit = () => {
    if (disabled) return;
    if (!input.trim() && !attachment) return;
    onSendMessage(input, attachment?.file);
    setInput('');
    setAttachment(null);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    const el = e.target;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 200) + 'px';
  };

  const addFile = (file: File) => {
    const att: FileAttachment = {
      name: file.name,
      size: file.size,
      type: file.type,
      file,
    };
    // Generate preview for images
    if (file.type.startsWith('image/')) {
      const reader = new FileReader();
      reader.onload = (e) => {
        att.previewUrl = e.target?.result as string;
        setAttachment({ ...att });
      };
      reader.readAsDataURL(file);
    } else {
      setAttachment(att);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) addFile(file);
    // Reset input so same file can be re-selected
    e.target.value = '';
  };

  const handleDragOver = (e: DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) addFile(file);
  };

  const removeAttachment = () => {
    setAttachment(null);
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const getFileIcon = (type: string) => {
    if (type.startsWith('image/')) return '\uD83D\uDDBC\uFE0F';
    if (type.includes('pdf')) return '\uD83D\uDCC4';
    if (type.includes('word') || type.includes('document')) return '\uD83D\uDCC3';
    if (type.includes('sheet') || type.includes('csv') || type.includes('excel')) return '\uD83D\uDCCA';
    if (type.startsWith('audio/') || type.includes('ogg')) return '\uD83C\uDFA4';
    if (type.startsWith('video/')) return '\uD83C\uDFA5';
    if (type.includes('text') || type.includes('json') || type.includes('xml')) return '\uD83D\uDCDD';
    if (type.includes('zip') || type.includes('rar') || type.includes('tar')) return '\uD83D\uDCE6';
    return '\uD83D\uDCCE';
  };

  return (
    <div
      className={`border-t border-gray-200 bg-white px-4 py-4 ${isDragOver ? 'ring-2 ring-blue-400 ring-inset bg-blue-50' : ''}`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <div className="max-w-4xl mx-auto">
        {/* File preview */}
        {attachment && (
          <div className="mb-2 flex items-center gap-2 px-2 py-2 bg-gray-50 rounded-xl border border-gray-200">
            {attachment.previewUrl ? (
              <img
                src={attachment.previewUrl}
                alt={attachment.name}
                className="w-12 h-12 object-cover rounded-lg"
              />
            ) : (
              <span className="text-2xl">{getFileIcon(attachment.type)}</span>
            )}
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-700 truncate">{attachment.name}</p>
              <p className="text-xs text-gray-400">{formatSize(attachment.size)}</p>
            </div>
            <button
              onClick={removeAttachment}
              className="p-1 text-gray-400 hover:text-red-500 transition-colors"
              aria-label="Remove file"
            >
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        )}

        {/* Drag overlay hint */}
        {isDragOver && (
          <div className="mb-2 text-center text-sm text-blue-500 font-medium">
            Drop file here
          </div>
        )}

        <div className="flex items-end gap-2">
          {/* Paperclip / attach button */}
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled}
            className="p-3 text-gray-400 hover:text-gray-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0"
            aria-label="Attach file"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M18.375 12.739l-7.693 7.693a4.5 4.5 0 01-6.364-6.364l10.94-10.94A3 3 0 1119.5 7.372L8.552 18.32m.009-.01l-.01.01m5.699-9.941l-7.81 7.81a1.5 1.5 0 002.112 2.13" />
            </svg>
          </button>

          <input
            ref={fileInputRef}
            type="file"
            onChange={handleFileSelect}
            className="hidden"
            accept="image/*,.pdf,.doc,.docx,.txt,.csv,.xlsx,.xls,.json,.xml,.html,.md,.py,.js,.ts,.ogg,.mp3,.wav"
          />

          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            placeholder={
              disabled
                ? 'Add your API key to start chatting...'
                : attachment
                  ? 'Add a message about the file... (Enter to send)'
                  : 'Type a message... (Enter to send, Shift+Enter for new line)'
            }
            disabled={disabled}
            rows={1}
            className="flex-1 resize-none rounded-2xl border border-gray-300 px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed text-gray-900 placeholder-gray-400"
          />

          <button
            onClick={handleSubmit}
            disabled={disabled || (!input.trim() && !attachment)}
            className="px-4 py-3 bg-blue-500 text-white rounded-2xl hover:bg-blue-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0"
            aria-label="Send message"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2}
              stroke="currentColor"
              className="w-5 h-5"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5"
              />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}

export default InputArea;
