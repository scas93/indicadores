"use client";
import { useEffect, useRef, useState } from "react";

/** Gráficas SVG propias del Padrón (sin librería), con el menú de exportación (☰) de cada gráfica: imagen PNG, imagen
 *  SVG e imprimir. Los estilos van como atributos del SVG para que la imagen exportada se vea igual que en pantalla. */
export type Dato = { nombre: string; total: number };
export const PALETA = ["#4e79a7", "#f28e2b", "#59a14f", "#e15759", "#76b7b2", "#edc948", "#b07aa1", "#9c755f", "#bab0ac"];
const corta = (s: string, n = 14) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);
const techo = (max: number) => Math.max(4, Math.ceil(max / 4) * 4);

function descargarBlob(blob: Blob, nombre: string) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = nombre;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

/** Envuelve una gráfica con su título y el menú de exportación. */
export function Grafica({ titulo, children, archivo }: { titulo: string; children: React.ReactNode; archivo: string }) {
  const caja = useRef<HTMLDivElement>(null);
  const [menu, setMenu] = useState(false);
  useEffect(() => {
    if (!menu) return;
    const cerrar = () => setMenu(false);
    document.addEventListener("mousedown", cerrar);
    return () => document.removeEventListener("mousedown", cerrar);
  }, [menu]);

  const svg = () => {
    const s = caja.current?.querySelector("svg");
    if (!s) return null;
    const c = s.cloneNode(true) as SVGSVGElement;
    c.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    return { c, w: s.viewBox.baseVal.width || s.clientWidth, h: s.viewBox.baseVal.height || s.clientHeight };
  };
  const comoSvg = () => { const s = svg(); if (s) descargarBlob(new Blob([new XMLSerializer().serializeToString(s.c)], { type: "image/svg+xml" }), `${archivo}.svg`); };
  const comoPng = () => {
    const s = svg();
    if (!s) return;
    const img = new Image();
    img.onload = () => {
      const k = 2, cv = document.createElement("canvas");
      cv.width = s.w * k; cv.height = s.h * k;
      const g = cv.getContext("2d")!;
      g.fillStyle = "#fff"; g.fillRect(0, 0, cv.width, cv.height); g.drawImage(img, 0, 0, cv.width, cv.height);
      cv.toBlob((b) => b && descargarBlob(b, `${archivo}.png`));
    };
    img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(new XMLSerializer().serializeToString(s.c))}`;
  };
  const imprimir = () => {
    const s = svg();
    if (!s) return;
    const w = window.open("", "_blank");
    if (w) { w.document.write(`<title>${titulo}</title><h3>${titulo}</h3>${new XMLSerializer().serializeToString(s.c)}`); w.document.close(); w.print(); }
  };

  return (
    <div className="pe-grafica" ref={caja}>
      <div className="pe-grafica-cab">
        <h4>{titulo}</h4>
        <div className="pe-menu" onMouseDown={(e) => e.stopPropagation()}>
          <button type="button" className="btn btn-xs btn-default" aria-label="Menú de exportación" title="Menú de exportación" onClick={() => setMenu(!menu)}><i className="fa fa-bars" /></button>
          {menu && (
            <ul className="pe-menu-lista">
              <li><button type="button" onClick={() => { setMenu(false); imprimir(); }}>Imprimir gráfica</button></li>
              <li><button type="button" onClick={() => { setMenu(false); comoPng(); }}>Descargar imagen PNG</button></li>
              <li><button type="button" onClick={() => { setMenu(false); comoSvg(); }}>Descargar imagen SVG</button></li>
            </ul>)}
        </div>
      </div>
      {children}
    </div>
  );
}

/** Barras verticales simples con el número sobre cada barra. */
export function Barras({ datos, etiqueta }: { datos: Dato[]; etiqueta: string }) {
  const ancho = 56, sep = 28, izq = 40, alto = 280, arriba = 24, abajo = 50;
  const W = Math.max(360, izq + datos.length * (ancho + sep) + sep);
  const max = techo(Math.max(1, ...datos.map((d) => d.total)));
  const y = (v: number) => arriba + (alto - arriba - abajo) * (1 - v / max);
  return (
    <svg viewBox={`0 0 ${W} ${alto}`} width={W} height={alto} role="img" aria-label={etiqueta} fontFamily="sans-serif">
      {[0, 1, 2, 3, 4].map((i) => { const t = Math.round((max * i) / 4); return (
        <g key={i}><line x1={izq} x2={W - 6} y1={y(t)} y2={y(t)} stroke="#e8e8e8" /><text x={izq - 6} y={y(t) + 4} fontSize="11" textAnchor="end" fill="#777">{t}</text></g>); })}
      {datos.map((d, i) => {
        const x = izq + sep + i * (ancho + sep);
        return (
          <g key={d.nombre}>
            <rect x={x} y={y(d.total)} width={ancho} height={Math.max(y(0) - y(d.total), 0)} fill={PALETA[i % PALETA.length]} />
            <text x={x + ancho / 2} y={y(d.total) - 5} fontSize="12" textAnchor="middle" fill="#323232">{d.total}</text>
            <text x={x + ancho / 2} y={alto - abajo + 18} fontSize="12" textAnchor="middle" fill="#323232">{corta(d.nombre)}<title>{d.nombre}</title></text>
          </g>);
      })}
      <line x1={izq} x2={W - 6} y1={y(0)} y2={y(0)} stroke="#999" />
    </svg>
  );
}

/** Barras agrupadas: una barra por año dentro de cada localidad (Comparativo). */
export function BarrasPorAnio({ grupos, anios }: { grupos: { nombre: string; anios: Record<string, number> }[]; anios: number[] }) {
  const ancho = 30, sep = 30, izq = 40, alto = 300, arriba = 24, abajo = 56;
  const gw = ancho * anios.length;
  const W = Math.max(420, izq + grupos.length * (gw + sep) + sep);
  const max = techo(Math.max(1, ...grupos.flatMap((g) => anios.map((a) => g.anios[String(a)] ?? 0))));
  const y = (v: number) => arriba + (alto - arriba - abajo) * (1 - v / max);
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${alto}`} width={W} height={alto} role="img" aria-label="Comparativo por localidad" fontFamily="sans-serif">
        {[0, 1, 2, 3, 4].map((i) => { const t = Math.round((max * i) / 4); return (
          <g key={i}><line x1={izq} x2={W - 6} y1={y(t)} y2={y(t)} stroke="#e8e8e8" /><text x={izq - 6} y={y(t) + 4} fontSize="11" textAnchor="end" fill="#777">{t}</text></g>); })}
        {grupos.map((g, gi) => {
          const x0 = izq + sep + gi * (gw + sep);
          return (
            <g key={g.nombre}>
              {anios.map((a, ai) => { const v = g.anios[String(a)] ?? 0; return (
                <g key={a}>
                  <rect x={x0 + ai * ancho} y={y(v)} width={ancho - 3} height={Math.max(y(0) - y(v), 0)} fill={PALETA[ai % PALETA.length]} />
                  <text x={x0 + ai * ancho + (ancho - 3) / 2} y={y(v) - 5} fontSize="11" textAnchor="middle" fill="#323232">{v}</text>
                </g>); })}
              <text x={x0 + gw / 2} y={alto - abajo + 18} fontSize="12" textAnchor="middle" fill="#323232">{corta(g.nombre, 16)}<title>{g.nombre}</title></text>
            </g>);
        })}
        <line x1={izq} x2={W - 6} y1={y(0)} y2={y(0)} stroke="#999" />
      </svg>
      <Leyenda items={anios.map((a, i) => ({ nombre: String(a), color: PALETA[i % PALETA.length] }))} />
    </div>
  );
}

export function Leyenda({ items }: { items: { nombre: string; color: string }[] }) {
  return <div className="pe-leyenda">{items.map((i) => <span key={i.nombre}><span className="cuadro" style={{ background: i.color }} />{i.nombre}</span>)}</div>;
}

/** Pastel con porcentaje por rebanada y leyenda con los conteos. */
export function Pastel({ datos, etiqueta }: { datos: Dato[]; etiqueta: string }) {
  const R = 100, C = 120, total = datos.reduce((s, d) => s + d.total, 0);
  let acum = 0;
  const punto = (a: number) => [C + R * Math.sin(a), C - R * Math.cos(a)];
  return (
    <div className="pe-pastel">
      <svg viewBox={`0 0 ${C * 2} ${C * 2}`} width={C * 2} height={C * 2} role="img" aria-label={etiqueta} fontFamily="sans-serif">
        {total === 0 && <circle cx={C} cy={C} r={R} fill="#eee" />}
        {datos.filter((d) => d.total > 0).map((d, i) => {
          const a0 = (acum / total) * 2 * Math.PI, a1 = ((acum + d.total) / total) * 2 * Math.PI;
          acum += d.total;
          const color = PALETA[datos.indexOf(d) % PALETA.length], pc = (d.total * 100) / total;
          const m = (a0 + a1) / 2, [tx, ty] = [C + R * 0.62 * Math.sin(m), C - R * 0.62 * Math.cos(m)];
          return (
            <g key={d.nombre}>
              {d.total === total
                ? <circle cx={C} cy={C} r={R} fill={color}><title>{`${d.nombre}: ${d.total}`}</title></circle>
                : <path d={`M${C},${C} L${punto(a0)[0]},${punto(a0)[1]} A${R},${R} 0 ${a1 - a0 > Math.PI ? 1 : 0} 1 ${punto(a1)[0]},${punto(a1)[1]} Z`} fill={color} stroke="#fff"><title>{`${d.nombre}: ${d.total}`}</title></path>}
              {pc >= 5 && <text x={tx} y={ty + 4} fontSize="12" textAnchor="middle" fill="#fff" fontWeight="bold">{pc.toFixed(1)}%</text>}
            </g>);
        })}
      </svg>
      <Leyenda items={datos.map((d, i) => ({ nombre: `${d.nombre} (${d.total})`, color: PALETA[i % PALETA.length] }))} />
    </div>
  );
}

/** Indicador circular con el porcentaje (Apoyos por Género). */
export function Circular({ porcentaje, etiqueta, color, detalle }: { porcentaje: number; etiqueta: string; color: string; detalle: string }) {
  const r = 62, c = 2 * Math.PI * r;
  return (
    <svg viewBox="0 0 160 190" width={160} height={190} role="img" aria-label={`${etiqueta} ${porcentaje}%`} fontFamily="sans-serif">
      <circle cx="80" cy="80" r={r} fill="none" stroke="#eee" strokeWidth="16" />
      <circle cx="80" cy="80" r={r} fill="none" stroke={color} strokeWidth="16" strokeDasharray={`${(c * porcentaje) / 100} ${c}`} transform="rotate(-90 80 80)" />
      <text x="80" y="88" fontSize="24" textAnchor="middle" fill="#323232">{porcentaje.toFixed(1)}%</text>
      <text x="80" y="176" fontSize="14" textAnchor="middle" fill="#323232">{etiqueta} ({detalle})</text>
    </svg>
  );
}
