import { Leaf, Droplets, Thermometer, Wind, Zap } from 'lucide-react'

const SUGGESTIONS = [
  { icon: Droplets, text: 'Are my plants getting enough water?', color: '#60a5fa' },
  { icon: Leaf, text: 'Check my current NPK nutrient levels.', color: '#34d399' },
  { icon: Thermometer, text: 'Is the temperature too high for tomatoes?', color: '#f87171' },
  { icon: Wind, text: 'Should I adjust ventilation based on humidity?', color: '#a78bfa' }
]

export default function ChatEmptyState({ onSuggestionClick }) {
  return (
    <div className="chat-empty-wrap">
      <div className="chat-empty-icon">
        <div className="chat-empty-icon-circle">
          <Leaf size={28} style={{ color: 'var(--color-surface-0)', strokeWidth: 1.5 }} />
        </div>
      </div>

      <h2 className="chat-empty-title">FarmShield Assistant</h2>

      <p className="chat-empty-desc">
        Ask about your farm conditions, crop health, sensor readings, or irrigation needs.
      </p>

      <div className="chat-suggestions-grid">
        {SUGGESTIONS.map((s, idx) => {
          const Icon = s.icon
          return (
            <button
              key={idx}
              className="chat-suggestion-btn"
              onClick={() => onSuggestionClick(s.text)}
            >
              <div className="chat-suggestion-icon" style={{ background: `${s.color}20`, color: s.color }}>
                <Icon size={18} />
              </div>
              <span>{s.text}</span>
            </button>
          )
        })}
      </div>

      <p className="chat-empty-footer">
        <Zap size={12} />
        <span>Powered by real-time sensor data and AI analysis</span>
      </p>
    </div>
  )
}