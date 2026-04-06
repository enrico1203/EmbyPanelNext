import { useState } from "react";
import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";

export default function Layout() {
  const [collapsed, setCollapsed] = useState(() => {
    const stored = localStorage.getItem("sidebar");
    if (stored !== null) return stored === "true";
    return false; // aperta di default su desktop
  });

  const [mobileOpen, setMobileOpen] = useState(false);

  const toggleDesktop = () => {
    setCollapsed((c) => {
      localStorage.setItem("sidebar", String(!c));
      return !c;
    });
  };

  const toggleMobile = () => setMobileOpen((o) => !o);

  return (
    <div id="wrapper">
      <div
        id="sb-backdrop"
        className={mobileOpen ? "show" : ""}
        onClick={() => setMobileOpen(false)}
      />
      <Sidebar
        collapsed={collapsed}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
      />
      <div id="main">
        <TopBar
          onToggleDesktop={toggleDesktop}
          onToggleMobile={toggleMobile}
        />
        <div className="page-body">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
