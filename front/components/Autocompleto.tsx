"use client";
import { useEffect, useRef, useState } from "react";

export type OpcionAc = { valor: string; etiqueta: string };

/** Campo "Escriba y Seleccione": al teclear consulta `buscar` (con pausa) y muestra coincidencias; al elegir una
 *  llama `onElegir`. `texto` es lo que se ve en el campo (lo controla quien lo usa). */
export function Autocompleto({ texto, onTexto, buscar, onElegir, placeholder, ariaLabel, deshabilitado }: {
  texto: string; onTexto: (t: string) => void; buscar: (q: string) => Promise<OpcionAc[]>;
  onElegir: (o: OpcionAc) => void; placeholder?: string; ariaLabel: string; deshabilitado?: boolean;
}) {
  const [ops, setOps] = useState<OpcionAc[] | null>(null);
  const [activo, setActivo] = useState(0);
  const pausa = useRef<ReturnType<typeof setTimeout>>(undefined);
  const raiz = useRef<HTMLDivElement>(null);
  const turno = useRef(0);

  useEffect(() => {
    const fuera = (e: MouseEvent) => raiz.current && !raiz.current.contains(e.target as Node) && setOps(null);
    document.addEventListener("mousedown", fuera);
    return () => { document.removeEventListener("mousedown", fuera); clearTimeout(pausa.current); };
  }, []);

  function teclear(t: string) {
    onTexto(t);
    clearTimeout(pausa.current);
    const mio = ++turno.current;
    pausa.current = setTimeout(() => {
      buscar(t).then((r) => { if (mio === turno.current) { setOps(r); setActivo(0); } }).catch(() => undefined);
    }, 200);
  }
  function elegir(o: OpcionAc) { turno.current++; setOps(null); onElegir(o); }

  return (
    <div className="ac" ref={raiz}>
      <input className="form-control" value={texto} placeholder={placeholder} aria-label={ariaLabel} disabled={deshabilitado}
        autoComplete="off" onChange={(e) => teclear(e.target.value)} onFocus={() => teclear(texto)}
        onKeyDown={(e) => {
          if (!ops) return;
          if (e.key === "ArrowDown") { e.preventDefault(); setActivo((a) => Math.min(a + 1, ops.length - 1)); }
          else if (e.key === "ArrowUp") { e.preventDefault(); setActivo((a) => Math.max(a - 1, 0)); }
          else if (e.key === "Enter" && ops[activo]) { e.preventDefault(); elegir(ops[activo]); }
          else if (e.key === "Escape") setOps(null);
        }} />
      {ops && (
        <ul className="ac-lista" role="listbox">
          {ops.length === 0 && <li className="vacio">Sin coincidencias</li>}
          {ops.map((o, i) => (
            <li key={o.valor} role="option" aria-selected={i === activo} className={i === activo ? "activo" : ""}
              onMouseDown={(e) => { e.preventDefault(); elegir(o); }}>{o.etiqueta}</li>))}
        </ul>)}
    </div>
  );
}
