"use client";
import { useState } from "react";
import { COLORES, COLOR_ETIQUETA, COLOR_HEX, pct, type ColorConteo, type Grupo } from "@/lib/estadisticas";

/** Gráficas SVG propias (sin librería): el detalle de paridad con la referencia (número sobre cada
 *  barra, tooltip con el nombre y los 4 conteos, clic a detalle) se controla aquí. */
type Click = (g: Grupo, color: ColorConteo | null) => void;
type Tip = { x: number; y: number; g: Grupo } | null;

const corta = (s: string, n = 22) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);
const techo = (max: number) => Math.max(4, Math.ceil(max / 4) * 4); // 4 marcas enteras en el eje

function Tooltip({ tip, porcentaje }: { tip: Tip; porcentaje?: boolean }) {
  if (!tip) return null;
  const { g } = tip;
  return (
    <div className="stat-tooltip" style={{ left: tip.x + 14, top: tip.y + 14 }}>
      <strong>{g.nombre}</strong>
      {COLORES.map((c) => (
        <div key={c}><span style={{ color: COLOR_HEX[c] }}>■</span> {COLOR_ETIQUETA[c]}: {porcentaje ? `${pct(g[c], g.total).toFixed(1)} % (${g[c]})` : g[c]}</div>
      ))}
    </div>
  );
}

export function Leyenda() {
  return (
    <div className="stat-leyenda">
      {COLORES.map((c) => <span key={c}><span className="cuadro" style={{ background: COLOR_HEX[c] }} />{COLOR_ETIQUETA[c]}</span>)}
    </div>
  );
}

/** Dependencias / Ejes: 4 barras (verde, amarillo, rojo, gris) por grupo con el conteo encima. */
export function BarrasAgrupadas({ grupos, onClick }: { grupos: Grupo[]; onClick: Click }) {
  const [tip, setTip] = useState<Tip>(null);
  const ancho = 36, sep = 26, izq = 44, alto = 300, arriba = 24, abajo = 56;
  const anchoGrupo = ancho * 4 + sep;
  const W = Math.max(520, izq + grupos.length * anchoGrupo + 10);
  const max = techo(Math.max(1, ...grupos.flatMap((g) => COLORES.map((c) => g[c]))));
  const y = (v: number) => arriba + (alto - arriba - abajo) * (1 - v / max);
  const ticks = Array.from({ length: 5 }, (_, i) => Math.round((max * i) / 4));
  return (
    <div className="stat-grafica">
      <svg width={W} height={alto} role="img" aria-label="Conteo de indicadores por color">
        {ticks.map((t) => (
          <g key={t}><line x1={izq} x2={W - 6} y1={y(t)} y2={y(t)} stroke="#e8e8e8" /><text x={izq - 6} y={y(t) + 4} fontSize="11" textAnchor="end" fill="#777">{t}</text></g>
        ))}
        {grupos.map((g, gi) => {
          const x0 = izq + gi * anchoGrupo + sep / 2;
          return (
            <g key={g.id ?? "sin"} onMouseMove={(e) => setTip({ x: e.clientX, y: e.clientY, g })} onMouseLeave={() => setTip(null)}>
              {COLORES.map((c, ci) => {
                const h = y(0) - y(g[c]);
                return (
                  <g key={c} className="stat-barra" onClick={() => onClick(g, c)}>
                    <rect x={x0 + ci * ancho} y={y(g[c])} width={ancho - 4} height={Math.max(h, 0)} fill={COLOR_HEX[c]} />
                    <text x={x0 + ci * ancho + (ancho - 4) / 2} y={y(g[c]) - 5} fontSize="12" textAnchor="middle" fill="#323232">{g[c]}</text>
                  </g>
                );
              })}
              <text x={x0 + (ancho * 4 - 4) / 2} y={alto - abajo + 18} fontSize="12" textAnchor="middle" fill="#323232"
                style={{ cursor: "pointer" }} onClick={() => onClick(g, null)}>{corta(g.nombre)}<title>{g.nombre}</title></text>
            </g>
          );
        })}
        <line x1={izq} x2={W - 6} y1={y(0)} y2={y(0)} stroke="#999" />
      </svg>
      <Leyenda />
      <Tooltip tip={tip} />
    </div>
  );
}

/** Consolidado: una barra apilada al 100 % por dependencia; clic en el segmento → detalle. */
export function BarrasApiladas({ grupos, onClick }: { grupos: Grupo[]; onClick: Click }) {
  const [tip, setTip] = useState<Tip>(null);
  const ancho = 64, sep = 40, izq = 48, alto = 340, arriba = 16, abajo = 56;
  const W = Math.max(520, izq + grupos.length * (ancho + sep) + sep);
  const y = (p: number) => arriba + (alto - arriba - abajo) * (1 - p / 100);
  return (
    <div className="stat-grafica">
      <svg width={W} height={alto} role="img" aria-label="Porcentaje de indicadores por color">
        {[0, 25, 50, 75, 100].map((t) => (
          <g key={t}><line x1={izq} x2={W - 6} y1={y(t)} y2={y(t)} stroke="#e8e8e8" /><text x={izq - 6} y={y(t) + 4} fontSize="11" textAnchor="end" fill="#777">{t}%</text></g>
        ))}
        {grupos.map((g, gi) => {
          const x0 = izq + sep + gi * (ancho + sep);
          let acum = 0;
          return (
            <g key={g.id ?? "sin"} onMouseMove={(e) => setTip({ x: e.clientX, y: e.clientY, g })} onMouseLeave={() => setTip(null)}>
              {COLORES.map((c) => {
                const p = pct(g[c], g.total), desde = acum;
                acum += p;
                if (!p) return null;
                return (
                  <g key={c} className="stat-barra" onClick={() => onClick(g, c)}>
                    <rect x={x0} y={y(desde + p)} width={ancho} height={y(desde) - y(desde + p)} fill={COLOR_HEX[c]} />
                    {p >= 6 && <text x={x0 + ancho / 2} y={(y(desde) + y(desde + p)) / 2 + 4} fontSize="11" textAnchor="middle" fill="#323232">{p.toFixed(1)}%</text>}
                  </g>
                );
              })}
              <text x={x0 + ancho / 2} y={alto - abajo + 18} fontSize="12" textAnchor="middle" style={{ cursor: "pointer" }}
                onClick={() => onClick(g, null)}>{corta(g.nombre, 14)}<title>{g.nombre}</title></text>
            </g>
          );
        })}
        <line x1={izq} x2={W - 6} y1={y(0)} y2={y(0)} stroke="#999" />
      </svg>
      <Leyenda />
      <Tooltip tip={tip} porcentaje />
    </div>
  );
}

/** Cumplimiento de Metas: una gráfica por color con una sola barra (% de metas de la dependencia). */
export function BarraPorcentaje({ color, valor, cantidad, total, onClick }: { color: ColorConteo; valor: number; cantidad: number; total: number; onClick: () => void }) {
  const W = 220, alto = 260, izq = 40, arriba = 24, abajo = 36;
  const y = (p: number) => arriba + (alto - arriba - abajo) * (1 - p / 100);
  return (
    <div style={{ display: "inline-block", margin: "0 8px" }}>
      <svg width={W} height={alto} role="img" aria-label={`Metas en ${COLOR_ETIQUETA[color]}`}>
        {[0, 25, 50, 75, 100].map((t) => (
          <g key={t}><line x1={izq} x2={W - 6} y1={y(t)} y2={y(t)} stroke="#e8e8e8" /><text x={izq - 6} y={y(t) + 4} fontSize="11" textAnchor="end" fill="#777">{t}</text></g>
        ))}
        <g className="stat-barra" onClick={onClick}>
          <rect x={izq + 50} y={y(valor)} width={70} height={Math.max(y(0) - y(valor), 0)} fill={COLOR_HEX[color]} />
          <text x={izq + 85} y={y(valor) - 6} fontSize="12" textAnchor="middle">{valor.toFixed(1)} %</text>
        </g>
        <line x1={izq} x2={W - 6} y1={y(0)} y2={y(0)} stroke="#999" />
        <text x={izq + 85} y={alto - 14} fontSize="12" textAnchor="middle">{COLOR_ETIQUETA[color]} ({cantidad} de {total})</text>
      </svg>
    </div>
  );
}
