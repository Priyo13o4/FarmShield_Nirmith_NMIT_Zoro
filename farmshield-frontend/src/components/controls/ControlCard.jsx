export default function ControlCard({ title, children, titleAction }) {
  return (
    <section className="control-card" aria-label={title}>
      <header className="control-title-row">
        <h3 className="control-title">{title}</h3>
        {titleAction}
      </header>
      {children}
    </section>
  )
}
