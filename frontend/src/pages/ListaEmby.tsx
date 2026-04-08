import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import api from "../api/client";

interface EmbyUser {
  invito: number;
  reseller: string | null;
  user: string | null;
  date: string | null;
  expiry: number | null;
  days_left: number | null;
  server: string | null;
  schermi: number | null;
  k4: string | null;
  download: string | null;
  nota: string | null;
}

type SortKey = "user" | "reseller" | "server" | "schermi" | "k4" | "download" | "days_left" | "nota";
type SortDir = "asc" | "desc";

function DaysLeftBadge({ days }: { days: number | null }) {
  if (days === null) return <span style={{ color: "var(--txt-muted)" }}>—</span>;
  const color = days <= 0 ? "#e74c3c" : days <= 7 ? "#e67e22" : days <= 14 ? "#f5b84b" : "#2ecc71";
  const label = days <= 0 ? `Scaduto (${days})` : `${days}g`;
  return (
    <span style={{
      background: `${color}18`, color, border: `1px solid ${color}40`,
      borderRadius: 6, padding: "2px 9px", fontSize: ".78rem", fontWeight: 600,
    }}>
      {label}
    </span>
  );
}

function SortIcon({ col, sortKey, dir }: { col: SortKey; sortKey: SortKey; dir: SortDir }) {
  if (col !== sortKey) return <span style={{ opacity: 0.3, marginLeft: 4, fontSize: ".7rem" }}>↕</span>;
  return <span style={{ marginLeft: 4, fontSize: ".7rem" }}>{dir === "asc" ? "↑" : "↓"}</span>;
}

function ListSkeleton({ columns }: { columns: number }) {
  return (
    <>
      <div className="page-toolbar">
        <div style={{ height: 42, borderRadius: 12, background: "var(--bg-3)", flex: "1 1 280px", animation: "sk-pulse 1.4s ease-in-out infinite" }} />
        <div style={{ height: 16, width: 110, borderRadius: 8, background: "var(--bg-3)", animation: "sk-pulse 1.4s ease-in-out infinite" }} />
      </div>
      <div className="table-card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {Array.from({ length: columns }).map((_, index) => (
                  <th key={index}>
                    <div style={{ height: 10, width: `${55 + (index % 3) * 10}%`, borderRadius: 6, background: "var(--bg-3)", animation: "sk-pulse 1.4s ease-in-out infinite" }} />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Array.from({ length: 8 }).map((_, rowIndex) => (
                <tr key={rowIndex}>
                  {Array.from({ length: columns }).map((__, colIndex) => (
                    <td key={colIndex}>
                      <div style={{ height: 12, width: `${60 + ((rowIndex + colIndex) % 3) * 12}%`, borderRadius: 7, background: "var(--bg-3)", animation: "sk-pulse 1.4s ease-in-out infinite", animationDelay: `${(rowIndex + colIndex) * 0.04}s` }} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

function sortUsers(users: EmbyUser[], key: SortKey, dir: SortDir): EmbyUser[] {
  return [...users].sort((a, b) => {
    let av: string | number | null = a[key] as string | number | null;
    let bv: string | number | null = b[key] as string | number | null;

    // null sempre in fondo
    if (av === null && bv === null) return 0;
    if (av === null) return 1;
    if (bv === null) return -1;

    if (typeof av === "string") av = av.toLowerCase();
    if (typeof bv === "string") bv = bv.toLowerCase();

    if (av < bv) return dir === "asc" ? -1 : 1;
    if (av > bv) return dir === "asc" ? 1 : -1;
    return 0;
  });
}

export default function ListaEmby() {
  const { user } = useAuth();
  const isAdmin = user?.ruolo === "admin";
  const navigate = useNavigate();
  const [users, setUsers] = useState<EmbyUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("days_left");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  useEffect(() => {
    api.get("/users/emby")
      .then((r) => setUsers(r.data))
      .catch((e) => setError(e?.response?.data?.detail ?? e.message ?? "Errore sconosciuto"))
      .finally(() => setLoading(false));
  }, []);

  const handleSort = (key: SortKey) => {
    if (key === sortKey) setSortDir((d) => d === "asc" ? "desc" : "asc");
    else { setSortKey(key); setSortDir("asc"); }
  };

  const q = search.trim().toLowerCase();
  const filtered = users.filter((u) =>
    (u.user ?? "").toLowerCase().includes(q) ||
    (u.reseller ?? "").toLowerCase().includes(q) ||
    (u.server ?? "").toLowerCase().includes(q) ||
    (u.nota ?? "").toLowerCase().includes(q)
  );
  const sorted = sortUsers(filtered, sortKey, sortDir);

  const Th = ({ col, children }: { col: SortKey; children: React.ReactNode }) => (
    <th onClick={() => handleSort(col)} style={{ cursor: "pointer", userSelect: "none", whiteSpace: "nowrap" }}>
      {children}<SortIcon col={col} sortKey={sortKey} dir={sortDir} />
    </th>
  );

  return (
    <div className="pg">
      <div className="pg-title">
        Lista Utenti
        <span className="pg-badge platform-emby" style={{ marginLeft: 10 }}>Emby</span>
        <span style={{ fontSize: ".9rem", fontWeight: 500, color: "var(--txt-soft)", marginLeft: 8 }}>
          ({sorted.length})
        </span>
      </div>

      {!loading && !error && users.length > 0 && (
        <div className="page-toolbar">
          <label className="search-field" htmlFor="emby-search">
            <Search size={16} />
            <input
              id="emby-search"
              type="text"
              placeholder="Cerca utente, reseller, server..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              autoComplete="off"
            />
          </label>
          <div className="toolbar-meta">{sorted.length} risultat{sorted.length === 1 ? "o" : "i"}</div>
        </div>
      )}

      {loading ? (
        <ListSkeleton columns={isAdmin ? 8 : 7} />
      ) : error ? (
        <div className="wip-wrap" style={{ color: "#e74c3c" }}><p>Errore API: {error}</p></div>
      ) : sorted.length === 0 ? (
        <div className="wip-wrap">
          <p>{users.length === 0 ? "Nessun utente trovato." : `Nessun risultato per "${search.trim()}".`}</p>
        </div>
      ) : (
        <div className="table-card">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <Th col="user">Username</Th>
                  <Th col="days_left">Giorni rimanenti</Th>
                  {isAdmin && <Th col="reseller">Reseller</Th>}
                  <Th col="server">Server</Th>
                  <Th col="schermi">Schermi</Th>
                  <Th col="k4">4K</Th>
                  <Th col="download">Download</Th>
                  <Th col="nota">Nota</Th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((u) => (
                  <tr key={u.invito} onClick={() => navigate(`/lista/emby/${u.invito}`)} style={{ cursor: "pointer" }}>
                    <td style={{ fontWeight: 600 }}>{u.user ?? "—"}</td>
                    <td><DaysLeftBadge days={u.days_left} /></td>
                    {isAdmin && <td style={{ color: "var(--txt-soft)", fontSize: ".83rem" }}>{u.reseller ?? "—"}</td>}
                    <td>{u.server ?? "—"}</td>
                    <td>{u.schermi ?? "—"}</td>
                    <td>
                      {u.k4?.toLowerCase() === "true"
                        ? <span style={{ color: "#f5b84b", fontWeight: 600 }}>✓</span>
                        : <span style={{ color: "var(--txt-muted)" }}>—</span>}
                    </td>
                    <td>
                      {u.download?.toLowerCase() === "true"
                        ? <span style={{ color: "#2ecc71", fontWeight: 600 }}>✓</span>
                        : <span style={{ color: "var(--txt-muted)" }}>—</span>}
                    </td>
                    <td style={{ color: "var(--txt-soft)", fontSize: ".83rem", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {u.nota || "—"}
                    </td>
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
