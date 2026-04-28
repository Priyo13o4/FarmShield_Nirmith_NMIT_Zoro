export default function Skeleton({
  width = '100%',
  height = '1rem',
  borderRadius = 'var(--radius-2)',
}) {
  return (
    <span
      className="skeleton"
      style={{
        width,
        height,
        borderRadius,
      }}
      aria-hidden="true"
    />
  )
}
