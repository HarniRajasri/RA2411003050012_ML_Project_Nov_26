import { createContext, useContext } from "react";
import { useDashboardSocket } from "../hooks/useDashboardSocket.js";

const LiveCtx = createContext(null);

export function LiveProvider({ children }) {
  const live = useDashboardSocket();
  return <LiveCtx.Provider value={live}>{children}</LiveCtx.Provider>;
}

export const useLive = () => useContext(LiveCtx);
