export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export interface ChatConfig {
  apiKey: string;
  model: string;
  maxTokens: number;
}
