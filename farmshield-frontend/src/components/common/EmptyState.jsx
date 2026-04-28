export default function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div className="empty-state" role="status" aria-live="polite">
      <div className="empty-state-icon">
        <Icon size={42} strokeWidth={1.5} aria-hidden="true" />
      </div>
      <div className="empty-state-title">{title}</div>
      <div className="empty-state-description">{description}</div>
      {action ? (
        <button
          type="button"
          className="btn btn-ghost"
          onClick={action.onClick}
          disabled={Boolean(action.loading)}
        >
          {action.loading ? <span className="inline-spinner" aria-hidden="true" /> : null}
          {action.label}
        </button>
      ) : null}
    </div>
  )
}
