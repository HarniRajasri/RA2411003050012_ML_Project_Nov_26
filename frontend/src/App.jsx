import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import Shell from "./components/Shell.jsx";
import { LiveProvider } from "./components/LiveContext.jsx";
import { ToastProvider } from "./components/Toast.jsx";
import DashboardPage from "./pages/DashboardPage.jsx";
import DevicesPage from "./pages/DevicesPage.jsx";
import AnalyticsPage from "./pages/AnalyticsPage.jsx";
import HistoryPage from "./pages/HistoryPage.jsx";
import DemoPage from "./pages/DemoPage.jsx";
import SystemPage from "./pages/SystemPage.jsx";

export default function App() {
  return (
    <ToastProvider>
      <LiveProvider>
        <HashRouter>
          <Routes>
            <Route element={<Shell />}>
              <Route index element={<DashboardPage />} />
              <Route path="devices" element={<DevicesPage />} />
              <Route path="analytics" element={<AnalyticsPage />} />
              <Route path="analytics/:id" element={<AnalyticsPage />} />
              <Route path="history" element={<HistoryPage />} />
              <Route path="demo" element={<DemoPage />} />
              <Route path="system" element={<SystemPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </HashRouter>
      </LiveProvider>
    </ToastProvider>
  );
}
