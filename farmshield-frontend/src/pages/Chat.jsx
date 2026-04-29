import { useState, useRef, useEffect, useCallback } from 'react'
import { PlusCircle, Loader2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { api, getApiConfig } from '../services/api'
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

  const [isVoiceActive, setIsVoiceActive] = useState(false)
  const voiceWsRef = useRef(null)
  const mediaRecorderRef = useRef(null)
  const audioCtxRef = useRef(null)
  const nextStartTimeRef = useRef(0)
  
  const playAudioChunk = (arrayBuffer) => {
    if (!audioCtxRef.current) {
      audioCtxRef.current = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 })
      nextStartTimeRef.current = audioCtxRef.current.currentTime
    }
    const audioData = new Int16Array(arrayBuffer)
    const floatData = new Float32Array(audioData.length)
    for (let i = 0; i < audioData.length; i++) {
      floatData[i] = audioData[i] / 32768.0
    }
    const buffer = audioCtxRef.current.createBuffer(1, floatData.length, 24000)
    buffer.getChannelData(0).set(floatData)
    const source = audioCtxRef.current.createBufferSource()
    source.buffer = buffer
    source.connect(audioCtxRef.current.destination)
    
    const startTime = Math.max(audioCtxRef.current.currentTime, nextStartTimeRef.current)
    source.start(startTime)
    nextStartTimeRef.current = startTime + buffer.duration
  }

  const handleVoiceToggle = async () => {
    if (isVoiceActive) {
      // Stop Voice
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop()
      }
      if (voiceWsRef.current && voiceWsRef.current.readyState === WebSocket.OPEN) {
        voiceWsRef.current.send(JSON.stringify({ event: 'end_of_speech' }))
      }
      setIsVoiceActive(false)
      setIsTyping(true)
      return
    }

    // Start Voice
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const { url } = getApiConfig()
      const wsUrl = `${url.replace(/^http/, 'ws')}/api/v1/chat/voice/ws?session_id=${sessionId}`
      const ws = new WebSocket(wsUrl)
      voiceWsRef.current = ws

      const userStreamingId = 'user_streaming'
      const streamingId = 'streaming'
      setMessages(prev => [
        ...prev, 
        { id: userStreamingId, role: 'user', content: '' },
        { id: streamingId, role: 'assistant', content: '', reasoning: '', sources: null }
      ])

      ws.onopen = () => {
        setIsVoiceActive(true)
        
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 })
        const source = audioCtx.createMediaStreamSource(stream)
        const processor = audioCtx.createScriptProcessor(4096, 1, 1)
        
        processor.onaudioprocess = (e) => {
          if (ws.readyState === WebSocket.OPEN) {
            const float32Array = e.inputBuffer.getChannelData(0)
            const int16Array = new Int16Array(float32Array.length)
            for (let i = 0; i < float32Array.length; i++) {
              let s = Math.max(-1, Math.min(1, float32Array[i]))
              int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7FFF
            }
            ws.send(int16Array.buffer)
          }
        }
        
        source.connect(processor)
        // Note: ScriptProcessor must be connected to destination, but we can gain it to 0
        const gainNode = audioCtx.createGain()
        gainNode.gain.value = 0
        processor.connect(gainNode)
        gainNode.connect(audioCtx.destination)
        
        mediaRecorderRef.current = {
          state: 'recording',
          stop: () => {
            source.disconnect()
            processor.disconnect()
            gainNode.disconnect()
            audioCtx.close()
            this.state = 'inactive'
          }
        }
      }

      ws.onmessage = async (event) => {
        if (event.data instanceof Blob) {
          const buffer = await event.data.arrayBuffer()
          playAudioChunk(buffer)
        } else {
          try {
            const data = JSON.parse(event.data)
            if (data.event === 'transcript') {
               setMessages(prev => prev.map(m => 
                 m.id === streamingId ? { ...m, content: (m.content || '') + data.text } : m
               ))
               scrollToBottom()
            } else if (data.event === 'reasoning') {
               setMessages(prev => prev.map(m => 
                 m.id === streamingId ? { ...m, reasoning: (m.reasoning || '') + data.text } : m
               ))
               scrollToBottom()
            } else if (data.event === 'user_transcript') {
               setMessages(prev => prev.map(m => 
                 m.id === userStreamingId ? { ...m, content: (m.content || '') + data.text } : m
               ))
               scrollToBottom()
            } else if (data.event === 'turn_complete') {
               setMessages(prev => {
                 // Finalize current streaming bubbles
                 const finalized = prev.map(m => {
                   if (m.id === streamingId) return { ...m, id: Date.now() + 1 }
                   if (m.id === userStreamingId) return { ...m, id: Date.now() }
                   return m
                 })
                 // Add fresh streaming bubbles for the next continuous turn
                 return [
                   ...finalized,
                   { id: userStreamingId, role: 'user', content: '' },
                   { id: streamingId, role: 'assistant', content: '', reasoning: '', sources: null }
                 ]
               })
               // Keep the connection open for continuous conversation!
            } else if (data.event === 'error') {
               console.error('Voice WS Error:', data.message)
               setError(data.message)
               setIsTyping(false)
               ws.close()
            }
          } catch (err) {
            // non-json text
          }
        }
      }

      ws.onclose = () => {
        setIsVoiceActive(false)
        setIsTyping(false)
        if (stream) stream.getTracks().forEach(track => track.stop())
        
        // Remove empty leftover streaming bubbles
        setMessages(prev => prev.filter(m => {
          if (m.id === 'streaming' || m.id === 'user_streaming') {
             return (m.content && m.content.trim() !== '') || (m.reasoning && m.reasoning.trim() !== '')
          }
          return true
        }))
      }
      
      ws.onerror = () => {
        setError("Voice WebSocket error")
        setIsVoiceActive(false)
        setIsTyping(false)
        if (stream) stream.getTracks().forEach(track => track.stop())
        
        setMessages(prev => prev.filter(m => {
          if (m.id === 'streaming' || m.id === 'user_streaming') {
             return (m.content && m.content.trim() !== '') || (m.reasoning && m.reasoning.trim() !== '')
          }
          return true
        }))
      }
    } catch (err) {
      console.error('Failed to start voice:', err)
      setError("Failed to access microphone or start voice chat")
    }
  }

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
    setMessages(prev => [...prev, userMessage, { id: streamingId, role: 'assistant', content: '', reasoning: '', sources: null }])
    setIsTyping(true)

    try {
      abortControllerRef.current = api.chat.streamMessage({
        message: text,
        sessionId,
        onReasoning: (reasoning) => {
          setMessages(prev => prev.map(m => 
            m.id === streamingId ? { ...m, reasoning: (m.reasoning || '') + reasoning } : m
          ))
          scrollToBottom()
        },
        onToken: (token) => {
          setMessages(prev => prev.map(m => 
            m.id === streamingId ? { ...m, content: (m.content || '') + token } : m
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
                reasoning={msg.reasoning}
                sources={msg.sources}
                isStreaming={msg.id === 'streaming' || msg.id === 'user_streaming'}
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
          disabled={isTyping && !isVoiceActive} 
          placeholder={t('chat.placeholder')}
          isVoiceActive={isVoiceActive}
          onVoiceToggle={handleVoiceToggle}
        />
      </div>
    </div>
  )
}