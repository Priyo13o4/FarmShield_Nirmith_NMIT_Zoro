import { useState, useRef, useEffect, useCallback } from 'react'
import { PlusCircle, Loader2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { api } from '../services/api'
import ChatBubble from '../components/chat/ChatBubble'
import ChatInput from '../components/chat/ChatInput'
import ChatEmptyState from '../components/chat/ChatEmptyState'

// Generate a random session ID
const generateSessionId = () => Math.random().toString(36).substring(2, 10)

/**
 * Generates a concise thread name from the user's first message.
 * Truncates to ~40 chars at a word boundary and appends ellipsis.
 */
function generateThreadName(text) {
  const cleaned = text.trim().replace(/\s+/g, ' ')
  if (cleaned.length <= 40) return cleaned
  const truncated = cleaned.slice(0, 40)
  const lastSpace = truncated.lastIndexOf(' ')
  return (lastSpace > 20 ? truncated.slice(0, lastSpace) : truncated) + '…'
}

export default function Chat() {
  const { t } = useTranslation()
  const [messages, setMessages] = useState([])
  const [sessionId, setSessionId] = useState(generateSessionId())
  const [isTyping, setIsTyping] = useState(false)
  const [error, setError] = useState(null)
  const [threadName, setThreadName] = useState('')
  
  const contentRef = useRef(null)
  const abortControllerRef = useRef(null)

  // Auto-scroll to bottom on new message or typing updates
  const scrollToBottom = useCallback(() => {
    if (contentRef.current) {
      contentRef.current.scrollTop = contentRef.current.scrollHeight
    }
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, isTyping, scrollToBottom])

  // Handle unmount - abort any ongoing request
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current()
      }
    }
  }, [])

  const currentAssistantIndex = messages.findIndex(m => m.role === 'assistant' && m.id === 'streaming')
  const streamingMessage = currentAssistantIndex !== -1 ? messages[currentAssistantIndex] : null

  const handleSendMessage = async (text) => {
    if (!text.trim() || isTyping) return

    // Clear previous error
    setError(null)

    // Generate thread name from first message
    if (messages.length === 0) {
      setThreadName(generateThreadName(text))
    }
    
    // Add user message
    const userMessage = { id: Date.now(), role: 'user', content: text, sources: null }
    const streamingId = 'streaming'
    
    // Setup initial streaming state
    setMessages(prev => [...prev, userMessage, { id: streamingId, role: 'assistant', content: '', sources: null }])
    setIsTyping(true)

    try {
      abortControllerRef.current = api.chat.streamMessage({
        message: text,
        sessionId,
        onToken: (token) => {
          setMessages(prev => prev.map(m => 
            m.id === streamingId ? { ...m, content: m.content + token } : m
          ))
          scrollToBottom()
        },
        onDone: (result) => {
          setMessages(prev => prev.map(m => 
            m.id === streamingId ? { ...m, id: Date.now(), sources: result.sources } : m
          ))
          setIsTyping(false)
          abortControllerRef.current = null
        },
        onError: (err) => {
          console.error('Chat error:', err)
          setError(t('chat.error'))
          setMessages(prev => prev.filter(m => m.id !== streamingId))
          setIsTyping(false)
          abortControllerRef.current = null
        }
      })
    } catch (err) {
      console.error('Chat start error:', err)
      setError(t('chat.error'))
      setMessages(prev => prev.filter(m => m.id !== streamingId))
      setIsTyping(false)
    }
  }

  const handleNewSession = async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current()
      abortControllerRef.current = null
    }
    
    setIsTyping(false)
    
    // Optional: Call clearSession on backend if we want to free resources
    if (messages.length > 0) {
      try {
        await api.chat.clearSession(sessionId)
      } catch (e) {
        console.warn('Failed to clear session on backend', e)
      }
    }
    
    setMessages([])
    setSessionId(generateSessionId())
    setError(null)
    setThreadName('')
  }

  const displayTitle = threadName || t('chat.title')
  const displaySubtitle = threadName ? t('chat.subtitle') : null

  return (
    <div className="chat-page">
      {/* Header */}
      <header className="chat-header">
        <div>
          <h2 className="chat-title">{displayTitle}</h2>
          {!threadName && (
            <p className="chat-subtitle">{t('chat.subtitle')}</p>
          )}
        </div>
        <button
          className="btn btn-primary chat-new-btn"
          onClick={handleNewSession}
          disabled={isTyping}
        >
          <PlusCircle size={16} aria-hidden="true" />
          {t('chat.newChat')}
        </button>
      </header>

      {error && (
        <div className="chat-error">
          {error}
        </div>
      )}

      {/* Scrollable messages area */}
      <div ref={contentRef} className="chat-messages">
        {messages.length === 0 ? (
          <ChatEmptyState onSuggestionClick={handleSendMessage} />
        ) : (
          <div className="chat-thread">
            {messages.map((msg) => (
              <ChatBubble 
                key={msg.id} 
                role={msg.role} 
                content={msg.content} 
                sources={msg.sources}
                isStreaming={msg.id === 'streaming'}
              />
            ))}
            {isTyping && !streamingMessage?.content && (
              <div className="chat-thinking">
                <Loader2 size={16} className="chat-thinking-spinner" />
                <span>{t('chat.thinking')}</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Input bar — pinned to bottom */}
      <div className="chat-input-bar">
        <ChatInput 
          onSend={handleSendMessage} 
          disabled={isTyping} 
          placeholder={t('chat.placeholder')}
        />
      </div>
    </div>
  )
}