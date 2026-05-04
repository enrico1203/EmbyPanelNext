import { useEffect, useMemo, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { Search, MonitorSmartphone } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import api from "../api/client";

interface DeviceStat {
  invito: number;
  username: string | null;
  server: string | null;
  server_tipo: string | null;
  device_count: number;
}

export default function DispositiviUtenti() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [rows, setRows] = useState<DeviceStat[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [hideNormali, setHideNormali] = useState(false);

  useEffect(() => {
    api.get("/admin/devices-stats")
      .then((r) => setRows(r.data))
      .catch((e) => setError(e?.response?.data?.detail ?? e.message ?? "Errore sconosciuto"))
      .finally(() => setLoading(false));
  }, []);

  if (!user) return <Navigate to="/login" replace />;
  if (user.ruolo !== "admin") return <Navigate to="/dashboard" replace />;

  const q = search.trim().toLowerCase();
  const filtered = useMemo(
    () => rows.filter((row) => {
      if (hideNormali && (row.server_tipo ?? "").trim().toLowerCase() === "normale") return false;
      return (row.username ?? "").toLowerCase().includes(q) ||
        (row.server ?? "").toLowerCase().includes(q);
    }),
    [rows, q, hideNormali],
  );

  return (
    <div className="pg">
      <div className="pg-title">
        <MonitorSmartphone size={18} style={{ marginRight: 8 }} />
        Verifica dispositivi utenti
        <span style={{ fontSize: ".9rem", fontWeight: 500, color: "var(--txt-soft)", marginLeft: 8 }}>
          ({filtered.length})
        </span>
      </div>
      <p className="manage-subtitle" style={{ marginTop: 4 }}>
        Utenti Emby con almeno un dispositivo associato, ordinati dal numero di dispositivi più alto.
      </p>

      {!loading && !error && rows.length > 0 && (
        <div className="page-toolbar">
          <label className="search-field" htmlFor="dev-search">
            <Search size={16} />
            <input
              id="dev-search"
              type="text"
              placeholder="Cerca utente o server..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              autoComplete="off"
            />
          </label>
          <label style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: ".88rem", color: "var(--txt-soft)", cursor: "pointer", userSelect: "none" }}>
            <input
              type="checkbox"
              checked={hideNormali}
              onChange={(e) => setHideNormali(e.target.checked)}
            />
            Togli utenti server normali
          </label>
          <div className="toolbar-meta">{filtered.length} risultat{filtered.length === 1 ? "o" : "i"}</div>
        </div>
      )}

      {loading ? (
        <div className="loading-wrap"><div className="spinner" /></div>
      ) : error ? (
        <div className="wip-wrap" style={{ color: "#e74c3c" }}><p>Errore API: {error}</p></div>
      ) : filtered.length === 0 ? (
        <div className="wip-wrap">
          <p>{rows.length === 0 ? "Nessun utente con dispositivi registrati." : `Nessun risultato per "${search.trim()}".`}</p>
        </div>
      ) : (
        <div className="table-card">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Username</th>
                  <th style={{ width: 160 }}>Numero dispositivi</th>
                  <th>Server</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((row) => (
                  <tr
                    key={row.invito}
                    onClick={() => navigate(`/lista/emby/${row.invito}`)}
                    style={{ cursor: "pointer" }}
                  >
                    <td style={{ fontWeight: 600 }}>{row.username ?? "—"}</td>
                    <td>
                      <span style={{
                        background: "rgba(108,142,247,.18)",
                        color: "#a5b8f8",
                        border: "1px solid rgba(108,142,247,.35)",
                        borderRadius: 999,
                        padding: "3px 12px",
                        fontSize: ".82rem",
                        fontWeight: 700,
                      }}>
                        {row.device_count}
                      </span>
                    </td>
                    <td>{row.server ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
