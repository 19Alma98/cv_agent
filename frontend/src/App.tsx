import { Link, Navigate, Route, Routes } from "react-router-dom";
import { HomePage } from "./pages/HomePage";
import { ReportPage } from "./pages/ReportPage";

export default function App() {
  return (
    <div className="app-shell">
      <nav className="top-nav">
        <span className="brand">CV Agent</span>
        <div className="nav-links">
          <Link to="/">Input</Link>
          <Link to="/report">Report</Link>
        </div>
      </nav>
      <main className="main">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/report" element={<ReportPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
