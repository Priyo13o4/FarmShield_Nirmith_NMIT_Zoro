import SourceBadge from './SourceBadge'

export default function ChatBubble({ role, content, sources, isStreaming }) {
  const isAssistant = role === 'assistant'
  
  return (
    <div className={`chat-bubble-wrap ${role}`}>
      <div className={`chat-bubble ${role}`}>
        <div className="chat-bubble-content">
          {content}
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