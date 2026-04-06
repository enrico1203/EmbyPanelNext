import { useEffect, useState } from "react";
import { ArrowDownLeft, ArrowUpRight, Search } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import api from "../api/client";

interface Movimento {
  id: number;
  date: string | null;  // ISO datetime from FastAPI
  type: string | null;
  user: string | null;
  text: string | null;
  costo: number | null;
  saldo: number | null;
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("it-IT", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function TypeBadge({ type }: { type: string | null }) {
  const isIn = type === "ricarica";
  return (
    <span style={{
      display: "inline-flex",
      alignItems: "center",
      gap: "0.3rem",
      padding: "2px 9px",
      borderRadius: "999px",
      fontSize: ".72rem",
      fontWeight: 700,
      background: isIn ? "rgba(34,197,94,.1)" : "rgba(239,68,68,.1)",
      color: isIn ? "#4ade80" : "var(--red)",
      border: `1px solid ${isIn ? "rgba(34,197,94,.25)" : "rgba(239,68,68,.25)"}`,
      whiteSpace: "nowrap",
    }}>
      {isIn ? <ArrowDownLeft size={11} /> : <ArrowUpRight size={11} />}
      {type ?? "—"}
    </span>
  );
}

export default function Movimenti() {
  const { user } = useAuth();
  const isAdmin = user?.ruolo === "admin";
  const [rows, setRows] = useState<Movimento[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    api.get("/movimenti?limit=500")
      .then((r) => setRows(r.data))
      .finally(() => setLoading(false));
  }, []);

  const normalizedSearch = search.trim().toLowerCase();
  const filteredRows = rows.filter((row) =>
    (row.user ?? "").toLowerCase().includes(normalizedSearch)
  );

  return (
    <div className="pg">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1.5rem", flexWrap: "wrap", gap: "0.75rem" }}>
        <div className="pg-title" style={{ margin: 0 }}>Movimenti</div>
        {isAdmin && (
          <span style={{
            padding: "3px 10px",
            borderRadius: "999px",
            fontSize: ".72rem",
            fontWeight: 700,
            background: "rgba(61,213,165,0.12)",
            color: "#3dd5a5",
            border: "1px solid rgba(61,213,165,0.3)",
            letterSpacing: ".05em",
            textTransform: "uppercase",
          }}>Tutti i movimenti</span>
        )}
      </div>

      {!loading && rows.length > 0 && (
        <div className="page-toolbar">
          <label className="search-field" htmlFor="movimenti-search">
            <Search size={16} />
            <input
              id="movimenti-search"
              type="text"
              placeholder="Cerca username"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              autoComplete="off"
            />
          </label>
          <div className="toolbar-meta">
            {filteredRows.length} risultat{filteredRows.length === 1 ? "o" : "i"}
          </div>
        </div>
      )}

      {loading ? (
        <div className="loading-wrap"><div className="spinner" /></div>
      ) : rows.length === 0 ? (
        <div className="wip-wrap">
          <p>Nessun movimento trovato.</p>
        </div>
      ) : filteredRows.length === 0 ? (
        <div className="wip-wrap">
          <p>Nessun movimento trovato per “{search.trim()}”.</p>
        </div>
      ) : (
        <div className="table-card">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Data</th>
                  <th>Tipo</th>
                  <th>Utente</th>
                  <th>Causale</th>
                  <th style={{ textAlign: "right" }}>Importo</th>
                  <th style={{ textAlign: "right" }}>Saldo</th>
                </tr>
              </thead>
              <tbody>
                {filteredRows.map((m) => (
                  <tr key={m.id}>
                    <td style={{ color: "var(--txt-muted)", fontSize: ".78rem", whiteSpace: "nowrap" }}>
                      {formatDate(m.date)}
                    </td>
                    <td><TypeBadge type={m.type} /></td>
                    <td style={{ fontWeight: 600, fontSize: ".85rem" }}>{m.user ?? "—"}</td>
                    <td style={{ color: "var(--txt-muted)", fontSize: ".85rem" }}>{m.text ?? "—"}</td>
                    <td style={{ textAlign: "right", fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>
                      {m.costo != null ? (
                        <span style={{ color: m.type === "ricarica" ? "#4ade80" : "var(--red)" }}>
                          {m.type === "ricarica" ? "+" : "-"}{m.costo.toFixed(2)}
                        </span>
                      ) : "—"}
                    </td>
                    <td style={{ textAlign: "right", color: "var(--txt-muted)", fontSize: ".85rem", fontVariantNumeric: "tabular-nums" }}>
                      {m.saldo != null ? m.saldo.toFixed(2) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div style={{ padding: "0.75rem 1.5rem", fontSize: ".78rem", color: "var(--txt-muted)", borderTop: "1px solid var(--border)" }}>
            {filteredRows.length} moviment{filteredRows.length === 1 ? "o" : "i"} visualizzat{filteredRows.length === 1 ? "o" : "i"} · ultimi 500
          </div>
        </div>
      )}
    </div>
  );
}
