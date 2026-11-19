import { useEffect, useRef, useState } from "react";

/** Width of a container, kept current with ResizeObserver, so SVG charts draw at true size (crisp text). */
export function useWidth(initial = 640) {
  const ref = useRef(null);
  const [width, setWidth] = useState(initial);
  useEffect(() => {
    if (!ref.current) return undefined;
    const el = ref.current;
    const update = () => setWidth(Math.max(280, Math.floor(el.getBoundingClientRect().width)));
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, width];
}
