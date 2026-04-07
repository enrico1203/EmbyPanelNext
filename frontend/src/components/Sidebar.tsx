import { NavLink, useLocation } from "react-router-dom";
import { LayoutDashboard, Users, LogOut, Shield, Store, CircleDollarSign, ReceiptText, SlidersHorizontal, CalendarClock } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";

interface SidebarProps {
  collapsed: boolean;
  mobileOpen: boolean;
  onCloseMobile: () => void;
}

export default function Sidebar({ collapsed, mobileOpen, onCloseMobile }: SidebarProps) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const isAdmin = user?.ruolo === "admin";
  const isMasterOrAdmin = user?.ruolo === "admin" || user?.ruolo === "master";

  const linkClass = (path: string) =>
    `sb-link${location.pathname === path ? " active" : ""}`;

  return (
    <aside
      id="sidebar"
      className={[
        collapsed ? "collapsed" : "",
        mobileOpen ? "mob-open" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {/* Header / Logo */}
      <div className="sb-header">
        <a className="sb-brand" href="/dashboard">
          <div className="sb-logo">SP</div>
          <div className="sb-brand-name">
            Streaming <span>Panel</span>
          </div>
        </a>
      </div>

      {/* Nav */}
      <nav className="sb-nav">
        <div className="sb-section">Menu</div>

        <NavLink
          to="/dashboard"
          className={linkClass("/dashboard")}
          onClick={onCloseMobile}
          data-tip="Dashboard"
        >
          <span className="sb-icon"><LayoutDashboard size={17} /></span>
          <span className="sb-label">Dashboard</span>
        </NavLink>

        <NavLink
          to="/movimenti"
          className={linkClass("/movimenti")}
          onClick={onCloseMobile}
          data-tip="Movimenti"
        >
          <span className="sb-icon"><ReceiptText size={17} /></span>
          <span className="sb-label">Movimenti</span>
        </NavLink>

        {isMasterOrAdmin && (
          <>
            <div className="sb-section">Reseller</div>
            <NavLink
              to="/resellers"
              className={linkClass("/resellers")}
              onClick={onCloseMobile}
              data-tip="I Miei Reseller"
            >
              <span className="sb-icon"><Store size={17} /></span>
              <span className="sb-label">I Miei Reseller</span>
            </NavLink>
          </>
        )}

        {isAdmin && (
          <>
            <div className="sb-section">Admin</div>
            <NavLink
              to="/admin/resellers"
              className={linkClass("/admin/resellers")}
              onClick={onCloseMobile}
              data-tip="Gestisci Reseller"
            >
              <span className="sb-icon"><Users size={17} /></span>
              <span className="sb-label">Gestisci Reseller</span>
            </NavLink>
            <NavLink
              to="/admin/prezzi"
              className={linkClass("/admin/prezzi")}
              onClick={onCloseMobile}
              data-tip="Prezzi"
            >
              <span className="sb-icon"><CircleDollarSign size={17} /></span>
              <span className="sb-label">Prezzi</span>
            </NavLink>
            <NavLink
              to="/admin/gestione"
              className={linkClass("/admin/gestione")}
              onClick={onCloseMobile}
              data-tip="Gestione"
            >
              <span className="sb-icon"><SlidersHorizontal size={17} /></span>
              <span className="sb-label">Gestione</span>
            </NavLink>
            <NavLink
              to="/admin/scheduler"
              className={linkClass("/admin/scheduler")}
              onClick={onCloseMobile}
              data-tip="Scheduler"
            >
              <span className="sb-icon"><CalendarClock size={17} /></span>
              <span className="sb-label">Scheduler</span>
            </NavLink>
          </>
        )}
      </nav>

      {/* Footer */}
      <div className="sb-footer">
        {isAdmin && (
          <div className="sb-admin-badge" title="Admin">
            <span className="sb-icon"><Shield size={14} /></span>
            <span className="sb-label">Admin</span>
          </div>
        )}
        <button
          className="sb-link sb-logout"
          data-tip="Logout"
          onClick={() => {
            logout();
            onCloseMobile();
          }}
        >
          <span className="sb-icon"><LogOut size={17} /></span>
          <span className="sb-label">Logout</span>
        </button>
      </div>
    </aside>
  );
}
