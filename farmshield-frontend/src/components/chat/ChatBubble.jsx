import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { ChevronDown, ChevronUp } from 'lucide-react'
import SourceBadge from './SourceBadge'

export default function ChatBubble({ role, content, sources, reasoning, isStreaming }) {
  const isAssistant = role === 'assistant'
  const [showThinking, setShowThinking] = useState(false)
  
  let displayContent = content || ''
  let displayReasoning = reasoning || ''

  if (isAssistant && typeof displayContent === 'string') {
    // Check for completed thought blocks
    const thoughtMatch = displayContent.match(/<thought>([\s\S]*?)<\/thought>/)
    if (thoughtMatch) {
      displayReasoning = displayReasoning ? `${displayReasoning}\n\n${thoughtMatch[1]}` : thoughtMatch[1]
      displayContent = displayContent.replace(/<thought>[\s\S]*?<\/thought>/, '').trim()
    } else if (displayContent.includes('<thought>')) {
      // Handle streaming thought block
      const parts = displayContent.split('<thought>')
      displayContent = parts[0].trim()
      const streamingThought = parts.slice(1).join('<thought>')
      displayReasoning = displayReasoning ? `${displayReasoning}\n\n${streamingThought}` : streamingThought
    }
  }
  return (
    <div className={`chat-bubble-wrap ${role}`}>
      <div className={`chat-bubble ${role}`}>
        {isAssistant && displayReasoning && (
          <div className="chat-reasoning-section">
            <button 
              className="chat-thinking-toggle"
              onClick={() => setShowThinking(!showThinking)}
              aria-expanded={showThinking}
            >
              {showThinking ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              <span>{showThinking ? 'Hide thinking' : 'Show thinking'}</span>
            </button>
            {showThinking && (
              <div className="chat-reasoning-content">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{displayReasoning}</ReactMarkdown>
              </div>
            )}
          </div>
        )}

        <div className="chat-bubble-content">
          {isAssistant ? (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{displayContent}</ReactMarkdown>
          ) : (
            displayContent
          )}
          {isStreaming && <span className="chat-streaming-cursor" aria-hidden="true" />}
        </div>
        
        {isAssistant && sources?.length > 0 && (
          <div className="chat-sources">
            <span className="chat-sources-label">Sources:</span>
            {sources.map((source, idx) => (
              <SourceBadge key={idx} source={source} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}