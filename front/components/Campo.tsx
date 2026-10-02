export function Campo({ label, error, children }: { label: string; error?: string; children: React.ReactNode }) {
  return (
    <div className={`form-group${error ? " has-error" : ""}`}>
      <label className="control-label">{label}</label>
      {children}
      {error && <span className="help-block">{error}</span>}
    </div>
  );
}

export const mensajeError = (e: unknown) => (e instanceof Error ? e.message : "Error de conexión");
