import { useEffect } from "react";
import Icon from "./Icon.jsx";

export default function Dialog({ title, onClose, children }) {
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="scrim" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="dialog" role="dialog" aria-modal="true" aria-label={title}>
        <div className="panel-head">
          <h2>{title}</h2>
          <button className="btn small" onClick={onClose} aria-label="Close"><Icon name="x" size={14} /></button>
        </div>
        {children}
      </div>
    </div>
  );
}
