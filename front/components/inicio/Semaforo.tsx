import { COLOR_NOMBRE, type ColorSemaforo } from "@/lib/mir";

/** Círculo de semáforo. Gris = sin datos / no calculable; "sin_color" = hay resultado fuera de los rangos. */
export function Semaforo({ color, conTexto }: { color: ColorSemaforo; conTexto?: boolean }) {
  return (
    <span title={COLOR_NOMBRE[color]}>
      <span className={`semaforo semaforo-${color}`} />
      {conTexto && <span style={{ marginLeft: 6 }}>{COLOR_NOMBRE[color]}</span>}
    </span>
  );
}
