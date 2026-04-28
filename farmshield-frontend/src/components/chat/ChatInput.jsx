import { Loader2, Send } from 'lucide-react'
import { useRef } from 'react'

export default function ChatInput({ onSend, disabled, placeholder }) {
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
      border: '1px solid var(--border-color)',
      borderRadius: '12px',
      padding: '0.75rem 1.25rem',
      maxWidth: '900px',
      width: '100%',
      boxShadow: '0 10px 30px rgba(0, 0, 0, 0.15)',
      transition: 'all 0.3s ease',
    }}
    onFocus={(e) => {
      e.currentTarget.style.borderColor = 'var(--color-primary)'
      e.currentTarget.style.boxShadow = '0 10px 30px rgba(0, 0, 0, 0.15), 0 0 0 3px rgba(251, 191, 36, 0.1)'
    }}
    onBlur={(e) => {
      e.currentTarget.style.borderColor = 'var(--border-color)'
      e.currentTarget.style.boxShadow = '0 10px 30px rgba(0, 0, 0, 0.15)'
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
        placeholder={placeholder}
        onKeyDown={handleKeyDown}
        onChange={handleChange}
        disabled={disabled}
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
    </div>
  )
}