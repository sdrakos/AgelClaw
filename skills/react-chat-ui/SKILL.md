---
name: react-chat-ui
description: >-
  Create modern, professional React chat interfaces with best practices for messaging UIs
---

# React Chat UI Skill

## Overview
Build modern, professional chat interfaces with React following industry best practices.

## Key Components
1. **ChatContainer** - Main wrapper with full-height layout
2. **MessageList** - Scrollable message area with auto-scroll
3. **Message** - Individual message bubble (user/assistant)
4. **InputArea** - Message input with send button
5. **Header** - Chat header with title and settings

## Best Practices

### Layout & Structure
- Use flexbox for vertical layout (header, messages, input)
- Messages area should flex-grow and scroll independently
- Auto-scroll to bottom on new messages
- Fixed input area at bottom
- Sticky header at top

### Message Display
- Different styling for user vs assistant messages
- User messages: right-aligned, colored background
- Assistant messages: left-aligned, neutral background
- Include timestamps (formatted)
- Support markdown rendering for assistant responses
- Code syntax highlighting for code blocks
- Avatar/icon for each message type

### UX Features
- Loading indicator while waiting for response
- Disable input while processing
- Clear visual feedback for sent messages
- Error handling and display
- Empty state when no messages
- Smooth animations for new messages

### Styling Guidelines
- Modern, clean design
- Adequate padding and spacing
- Responsive layout
- Readable typography
- Clear visual hierarchy
- Consistent color scheme
- Professional appearance (avoid generic AI aesthetics)

### Technical Requirements
- TypeScript for type safety
- React hooks (useState, useEffect, useRef)
- Proper state management
- Controlled components
- Accessibility (ARIA labels, keyboard navigation)
- Performance (memo, useCallback for expensive operations)

## Color Schemes

### Professional Blue
- Primary: #2563eb (blue-600)
- Secondary: #f3f4f6 (gray-100)
- User message: #2563eb
- Assistant message: #f9fafb
- Border: #e5e7eb

### Modern Purple
- Primary: #7c3aed (violet-600)
- Secondary: #f5f3ff
- User message: #7c3aed
- Assistant message: #faf5ff

### Clean Minimal
- Primary: #111827 (gray-900)
- Secondary: #f9fafb (gray-50)
- User message: #111827
- Assistant message: #ffffff
- Border: #e5e7eb

## Implementation Steps

1. Set up project with Vite + React + TypeScript + Tailwind
2. Create type definitions (Message, ChatConfig)
3. Create components in order:
   - App (main container with state)
   - Header component
   - MessageList component
   - Message component (with markdown support)
   - InputArea component
4. Add API integration (Anthropic SDK)
5. Implement auto-scroll behavior
6. Add loading states
7. Test and refine

## Libraries to Use
- **UI Framework**: React 18+
- **Styling**: TailwindCSS
- **Markdown**: react-markdown
- **Code Highlighting**: react-syntax-highlighter
- **API**: @anthropic-ai/sdk
- **Build Tool**: Vite
- **Language**: TypeScript

## Example Component Structure



## Anti-patterns to Avoid
- Don't use inline styles (use Tailwind classes)
- Don't forget auto-scroll on new messages
- Don't make API calls from child components
- Don't ignore loading/error states
- Don't use generic placeholder text
- Don't overcomplicate with unnecessary state management libraries
- Avoid emoji-heavy designs unless requested
