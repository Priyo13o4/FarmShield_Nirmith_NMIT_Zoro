import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { ChevronDown, ChevronUp } from 'lucide-react'
import SourceBadge from './SourceBadge'

export default function ChatBubble({ role, content, sources, reasoning, isStreaming }) {
  const isAssistant = role === 'assistant'
  const [showThinking, setShowThinking] = useState(false)
  
  return (
    <div className={`chat-bubble-wrap ${role}`}>
      <div className={`chat-bubble ${role}`}>
        {isAssistant && reasoning && (
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
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{reasoning}</ReactMarkdown>
              </div>
            )}
          </div>
        )}

        <div className="chat-bubble-content">
          {isAssistant ? (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
          ) : (
            content
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