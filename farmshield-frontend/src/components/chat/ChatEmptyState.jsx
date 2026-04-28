import { Leaf, Droplets, Thermometer, Wind, Zap } from 'lucide-react'

const SUGGESTIONS = [
  { icon: Droplets, text: 'Are my plants getting enough water?', color: '#60a5fa' },
  { icon: Leaf, text: 'Check my current NPK nutrient levels.', color: '#34d399' },
  { icon: Thermometer, text: 'Is the temperature too high for tomatoes?', color: '#f87171' },
  { icon: Wind, text: 'Should I adjust ventilation based on humidity?', color: '#a78bfa' }
]

export default function ChatEmptyState({ onSuggestionClick }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', padding: '3rem 2rem', textAlign: 'center' }}>
      {/* Animated Icon */}
      <div style={{ position: 'relative', marginBottom: '2rem', animation: 'float 3s ease-in-out infinite' }}>
        <div style={{ background: 'linear-gradient(135deg, var(--color-primary) 0%, rgba(251, 191, 36, 0.5) 100%)', padding: '2rem', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 20px 40px rgba(251, 191, 36, 0.2)' }}>
          <Leaf className="w-12 h-12" style={{ color: 'var(--color-surface-0)', strokeWidth: 1.5 }} />
        </div>
      </div>

      <h2 style={{ fontSize: '2rem', fontWeight: '700', color: 'var(--text-primary)', margin: '0 0 0.75rem 0', letterSpacing: '-0.5px' }}>
        Welcome to FarmShield AI
      </h2>

      <p style={{ fontSize: '1rem', color: 'var(--text-color-muted)', maxWidth: '500px', margin: '0 0 3rem 0', lineHeight: '1.6' }}>
        Ask me about your farm conditions, crop health, sensor readings, irrigation needs, or farming best practices. I analyze your live data to provide personalized recommendations.
      </p>

      <div style={{ width: '100%', maxWidth: '700px', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
        {SUGGESTIONS.map((s, idx) => {
          const Icon = s.icon
          return (
            <button
              key={idx}
              onClick={() => onSuggestionClick(s.text)}
              style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: '0.75rem', padding: '1.25rem', background: 'var(--color-surface)', border: '1px solid var(--border-color)', borderRadius: '12px', cursor: 'pointer', color: 'var(--text-color)', textAlign: 'left', transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)', fontSize: '0.9rem', fontWeight: '500', position: 'relative', overflow: 'hidden' }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = 'translateY(-4px)'
                e.currentTarget.style.borderColor = s.color
                e.currentTarget.style.boxShadow = `0 12px 24px rgba(0, 0, 0, 0.1), 0 0 20px ${s.color}20`
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'translateY(0)'
                e.currentTarget.style.borderColor = 'var(--border-color)'
                e.currentTarget.style.boxShadow = 'none'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', width: '100%' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '32px', height: '32px', borderRadius: '8px', background: `${s.color}20`, color: s.color, flexShrink: 0 }}>
                  <Icon className="w-5 h-5" />
                </div>
                <span style={{ flex: 1 }}>{s.text}</span>
              </div>
            </button>
          )
        })}
      </div>

      <p style={{ fontSize: '0.8rem', color: 'var(--text-color-muted)', display: 'flex', alignItems: 'center', gap: '0.5rem', justifyContent: 'center' }}>
        <Zap className="w-3 h-3" />
        <span>Powered by real-time sensor data and AI analysis</span>
      </p>

      <style>{`
        @keyframes float {
          0%, 100% { transform: translateY(0px); }
          50% { transform: translateY(-10px); }
        }
      `}</style>
    </div>
  )
}