export default function Alert({ kind = 'danger', children }) {
  if (!children) return null;
  return (
    <div className={`alert alert-${kind} py-2`} role="alert">
      {children}
    </div>
  );
}
