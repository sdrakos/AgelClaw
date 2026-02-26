export interface FileAttachment {
  name: string;
  size: number;
  type: string;
  file?: File;       // Only present before upload
  previewUrl?: string; // Data URL for image previews
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  attachment?: FileAttachment;
}

export interface ChatConfig {
  apiKey: string;
  model: string;
  maxTokens: number;
}
