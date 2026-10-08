import { NavLink, Route, Routes } from "react-router-dom";
import PublicDemo from "./pages/PublicDemo";
import SuperAdminConsole from "./pages/SuperAdminConsole";
import IncidentRoom from "./pages/IncidentRoom";

export default function App() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-line px-6 py-4 flex items-center justify-between">
        <NavLink to="/" className="flex items-center gap-3 text-paper no-underline">
          <span className="h-2.5 w-2.5 rounded-full bg-lime" />
          <span className="font-mono text-sm tracking-[0.18em]">SHADOWFIX</span>
        </NavLink>
        <nav className="flex gap-5 text-sm text-mute">
          <NavLink to="/" className={({ isActive }) => (isActive ? "text-lime" : "")}>
            Demo
          </NavLink>
          <NavLink to="/console" className={({ isActive }) => (isActive ? "text-lime" : "")}>
            Admin
          </NavLink>
        </nav>
      </header>
      <Routes>
        <Route path="/" element={<PublicDemo />} />
        <Route path="/console" element={<SuperAdminConsole />} />
        <Route path="/incident/:id" element={<IncidentRoom />} />
      </Routes>
    </div>
  );
}
