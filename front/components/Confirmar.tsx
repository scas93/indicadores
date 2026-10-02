"use client";
import { Modal } from "./Modal";

/** Confirmación previa a una baja (usada antes de eliminar nodos del árbol, componentes, etc.). */
export function Confirmar({ titulo, mensaje, boton = "Eliminar", onConfirmar, onClose }: {
  titulo: string; mensaje: React.ReactNode; boton?: string; onConfirmar: () => void; onClose: () => void;
}) {
  return (
    <Modal titulo={titulo} onClose={onClose} footer={<>
      <button className="btn btn-default" onClick={onClose}>Cancelar</button>
      <button className="btn btn-danger" onClick={onConfirmar} autoFocus>{boton}</button></>}>
      <p>{mensaje}</p>
    </Modal>
  );
}
