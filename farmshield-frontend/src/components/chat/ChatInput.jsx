import { Loader2, Send } from 'lucide-react'
import { useRef } from 'react'

export default function ChatInput({ onSend, disabled, placeholder, isVoiceActive, onVoiceToggle }) {
  const textareaRef = useRef(null)

  const adjustHeight = () => {
    const textarea = textareaRef.current
    if (textarea) {
      textarea.style.height = 'auto'
      textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px'
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      const text = textareaRef.current.value.trim()
      if (text && !disabled) {
        textareaRef.current.value = ''
        textareaRef.current.style.height = 'auto'
        onSend(text)
      }
    }
  }

  const handleChange = () => {
    adjustHeight()
  }

  const handleSend = () => {
    const text = textareaRef.current.value.trim()
    if (text && !disabled) {
      textareaRef.current.value = ''
      textareaRef.current.style.height = 'auto'
      onSend(text)
    }
  }

  return (
    <div className={`chat-input-wrap${isVoiceActive ? ' voice-active' : ''}`}>
      <textarea
        ref={textareaRef}
        className="chat-input-textarea"
        placeholder={isVoiceActive ? 'Listening...' : placeholder}
        onKeyDown={handleKeyDown}
        onChange={handleChange}
        disabled={disabled || isVoiceActive}
        rows={1}
        spellCheck="true"
      />
      <div className="chat-input-actions">
        <button
          className="chat-send-btn"
          onClick={handleSend}
          disabled={disabled}
          title={disabled ? 'Waiting for response...' : 'Send message (Enter)'}
        >
          {disabled ? (
            <Loader2 size={16} className="chat-thinking-spinner" />
          ) : (
            <Send size={16} />
          )}
        </button>

        {onVoiceToggle && (
          <button
            className={`chat-voice-btn${isVoiceActive ? ' recording' : ''}`}
            onClick={onVoiceToggle}
            disabled={disabled && !isVoiceActive}
            title={isVoiceActive ? 'Stop Recording' : 'Start Voice Chat'}
          >
            {isVoiceActive ? (
              <span className="chat-voice-stop" />
            ) : (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"></path>
                <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
                <line x1="12" y1="19" x2="12" y2="22"></line>
              </svg>
            )}
          </button>
        )}
      </div>
    </div>
  )
}