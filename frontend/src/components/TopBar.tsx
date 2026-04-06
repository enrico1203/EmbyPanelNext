import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Menu, Coins, Settings, Moon, Sun, ChevronDown } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { useTheme } from "../contexts/ThemeContext";

interface TopBarProps {
  onToggleDesktop: () => void;
  onToggleMobile: () => void;
}

export default function TopBar({ onToggleDesktop, onToggleMobile }: TopBarProps) {
  const { user } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fn = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", fn);
    return () => document.removeEventListener("mousedown", fn);
  }, []);

  const initials = user?.username?.slice(0, 2).toUpperCase() ?? "??";

  return (
    <header className="topbar">
      <div className="topbar-left">
        {/* Mobile hamburger */}
        <button className="btn-ic mobile-only" onClick={onToggleMobile} title="Menu">
          <Menu size={16} />
        </button>
        {/* Desktop collapse */}
        <button className="btn-ic desktop-only" onClick={onToggleDesktop} title="Comprimi menu">
          <Menu size={16} />
        </button>
      </div>

      <div className="topbar-right">
        {/* Saldo pill */}
        <div className="saldo-pill">
          <Coins size={13} />
          <span>{user?.credito ?? 0} crediti</span>
        </div>

        {/* User pill + dropdown */}
        <div ref={ref} style={{ position: "relative" }}>
          <button className="user-pill" onClick={() => setOpen((o) => !o)}>
            <div className="user-av">{initials}</div>
            <span>{user?.username}</span>
            <ChevronDown size={12} style={{ color: "var(--txt-muted)" }} />
          </button>

          <AnimatePresence>
            {open && (
              <motion.div
                className="user-dropdown"
                initial={{ opacity: 0, y: -6, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -6, scale: 0.97 }}
                transition={{ duration: 0.13 }}
              >
                <div className="user-dropdown-header">
                  <div className="user-dropdown-name">{user?.username}</div>
                  <div className="user-dropdown-role">{user?.ruolo}</div>
                </div>

                <button
                  className="dropdown-item"
                  onClick={() => { navigate("/settings"); setOpen(false); }}
                >
                  <Settings size={14} />
                  Impostazioni
                </button>

                <div className="dropdown-divider" />

                <div className="theme-row">
                  <div className="theme-row-label">
                    {theme === "dark" ? <Moon size={14} /> : <Sun size={14} />}
                    Tema scuro
                  </div>
                  <label className="theme-switch">
                    <input
                      type="checkbox"
                      checked={theme === "dark"}
                      onChange={toggleTheme}
                    />
                    <span className="slider" />
                  </label>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </header>
  );
}
