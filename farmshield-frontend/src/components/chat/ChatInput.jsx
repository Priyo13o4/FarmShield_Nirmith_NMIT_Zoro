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
    <div style={{
      display: 'flex',
      alignItems: 'flex-end',
      gap: '0.75rem',
      background: 'var(--color-surface)',
      border: isVoiceActive ? '1px solid var(--color-danger, #ef4444)' : '1px solid var(--border-color)',
      borderRadius: '12px',
      padding: '0.75rem 1.25rem',
      maxWidth: '900px',
      width: '100%',
      boxShadow: isVoiceActive 
        ? '0 0 15px rgba(239, 68, 68, 0.4)' 
        : '0 10px 30px rgba(0, 0, 0, 0.15)',
      transition: 'all 0.3s ease',
    }}
    onFocus={(e) => {
      if (!isVoiceActive) {
        e.currentTarget.style.borderColor = 'var(--color-primary)'
        e.currentTarget.style.boxShadow = '0 10px 30px rgba(0, 0, 0, 0.15), 0 0 0 3px rgba(251, 191, 36, 0.1)'
      }
    }}
    onBlur={(e) => {
      if (!isVoiceActive) {
        e.currentTarget.style.borderColor = 'var(--border-color)'
        e.currentTarget.style.boxShadow = '0 10px 30px rgba(0, 0, 0, 0.15)'
      }
    }}
    >
      <textarea
        ref={textareaRef}
        style={{
          flex: 1,
          border: 'none',
          background: 'transparent',
          color: 'var(--text-color)',
          resize: 'none',
          outline: 'none',
          padding: '0.5rem 0',
          minHeight: '24px',
          maxHeight: '120px',
          lineHeight: '1.5',
          fontSize: '0.95rem',
          fontFamily: 'inherit',
          WebkitFontSmoothing: 'antialiased',
        }}
        placeholder={isVoiceActive ? 'Listening...' : placeholder}
        onKeyDown={handleKeyDown}
        onChange={handleChange}
        disabled={disabled || isVoiceActive}
        rows={1}
        spellCheck="true"
      />
      <button
        onClick={handleSend}
        disabled={disabled}
        style={{
          background: disabled ? 'var(--text-color-muted)' : 'var(--color-primary)',
          color: 'var(--color-surface-0)',
          border: 'none',
          borderRadius: '8px',
          padding: '0.625rem 0.875rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: disabled ? 'not-allowed' : 'pointer',
          opacity: disabled ? 0.6 : 1,
          transition: 'all 0.2s ease',
          flexShrink: 0,
          fontSize: '0.85rem',
          fontWeight: '600',
        }}
        onMouseEnter={(e) => !disabled && (
          e.currentTarget.style.transform = 'scale(1.05)',
          e.currentTarget.style.boxShadow = '0 4px 12px rgba(251, 191, 36, 0.4)'
        )}
        onMouseLeave={(e) => (
          e.currentTarget.style.transform = 'scale(1)',
          e.currentTarget.style.boxShadow = 'none'
        )}
        title={disabled ? 'Waiting for response...' : 'Send message (Enter)'}
      >
        {disabled ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : (
          <Send className="w-4 h-4" />
        )}
      </button>
      
      {onVoiceToggle && (
        <button
          onClick={onVoiceToggle}
          disabled={disabled && !isVoiceActive}
          style={{
            background: isVoiceActive ? 'var(--color-danger, #ef4444)' : 'transparent',
            color: isVoiceActive ? 'white' : 'var(--text-color-muted)',
            border: isVoiceActive ? 'none' : '1px solid var(--border-color)',
            borderRadius: '50%',
            padding: '0.625rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: (disabled && !isVoiceActive) ? 'not-allowed' : 'pointer',
            opacity: (disabled && !isVoiceActive) ? 0.6 : 1,
            transition: 'all 0.2s ease',
            flexShrink: 0,
            width: '40px',
            height: '40px'
          }}
          title={isVoiceActive ? 'Stop Recording' : 'Start Voice Chat'}
        >
          {isVoiceActive ? (
            <span style={{ display: 'block', width: '12px', height: '12px', background: 'white', borderRadius: '2px' }} />
          ) : (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"></path>
              <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
              <line x1="12" y1="19" x2="12" y2="22"></line>
            </svg>
          )}
        </button>
      )}

    </div>
  )
}