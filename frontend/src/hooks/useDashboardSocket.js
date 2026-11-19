import { useCallback, useEffect, useRef, useState } from "react";
import { api, wsUrl } from "../services/api.js";

const MAX_EVENTS = 200;
const MAX_HISTORY = 900;
const STALE_MS = 8000;

/**
 * Live connection to the backend.
 * status: "connecting" | "live" | "reconnecting"
 * The backend pushes a snapshot about once a second and events as they happen. If the socket drops or goes quiet
 * the hook reconnects with back-off and reloads recent history, so the page recovers without a refresh.
 */
export function useDashboardSocket() {
  const [status, setStatus] = useState("connecting");
  const [snapshot, setSnapshot] = useState(null);
  const [events, setEvents] = useState([]);
  const [history, setHistory] = useState([]);
  const [backendUp, setBackendUp] = useState(null);
  const wsRef = useRef(null);
  const closedByUs = useRef(false);

  const loadBackfill = useCallback(async () => {
    try {
      const [ev, hist] = await Promise.all([api.events(60), api.liveHistory()]);
      setEvents(ev);
      setHistory(hist);
      setBackendUp(true);
    } catch {
      setBackendUp(false);
    }
  }, []);

  useEffect(() => {
    closedByUs.current = false;
    let retry = 0;
    let timer = null;
    let pingTimer = null;
    let watchdog = null;
    let lastMsg = Date.now();

    const connect = () => {
      setStatus((s) => (s === "live" ? "reconnecting" : s));
      let ws;
      try {
        ws = new WebSocket(wsUrl());
      } catch {
        schedule();
        return;
      }
      wsRef.current = ws;

      ws.onopen = () => {
        retry = 0;
        lastMsg = Date.now();
        setStatus("live");
        setBackendUp(true);
        loadBackfill();
        pingTimer = setInterval(() => ws.readyState === 1 && ws.send("ping"), 15000);
        watchdog = setInterval(() => {
          if (Date.now() - lastMsg > STALE_MS) ws.close();
        }, 2000);
      };

      ws.onmessage = (m) => {
        lastMsg = Date.now();
        let msg;
        try {
          msg = JSON.parse(m.data);
        } catch {
          return;
        }
        if (msg.type === "snapshot") {
          setSnapshot(msg);
          if (msg.live_point) {
            setHistory((h) => {
              const last = h[h.length - 1];
              if (last && last.t === msg.live_point.t) return h;
              const next = h.length >= MAX_HISTORY ? h.slice(h.length - MAX_HISTORY + 1) : h.slice();
              next.push(msg.live_point);
              return next;
            });
          } else {
            setHistory((h) => (h.length ? [] : h));
          }
        } else if (msg.type === "event") {
          setEvents((e) => [msg.event, ...e.filter((x) => x.id !== msg.event.id)].slice(0, MAX_EVENTS));
        }
      };

      const cleanup = () => {
        clearInterval(pingTimer);
        clearInterval(watchdog);
      };
      ws.onclose = () => {
        cleanup();
        if (closedByUs.current) return;
        setStatus("reconnecting");
        schedule();
      };
      ws.onerror = () => ws.close();
    };

    const schedule = () => {
      retry += 1;
      const delay = Math.min(10000, 500 * 2 ** Math.min(retry, 5));
      timer = setTimeout(connect, delay);
      api.health().then(() => setBackendUp(true)).catch(() => setBackendUp(false));
    };

    connect();
    return () => {
      closedByUs.current = true;
      clearTimeout(timer);
      clearInterval(pingTimer);
      clearInterval(watchdog);
      wsRef.current && wsRef.current.close();
    };
  }, [loadBackfill]);

  return { status, snapshot, events, history, backendUp, reload: loadBackfill };
}
