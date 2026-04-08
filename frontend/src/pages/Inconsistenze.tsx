import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { AlertTriangle, Search, Server } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import api from "../api/client";

interface InconsistencyDbUser {
  username: string;
  expiry: number | null;
  schermi: number | null;
  nota: string | null;
}

interface InconsistencyResult {
  service: string;
  server_name: string;
  server_count: number;
  db_count: number;
  server_only: string[];
  db_only: InconsistencyDbUser[];
}

interface OptionsResponse {
  emby_servers: string[];
  jelly_servers: string[];
}

function serviceBadge(service: "emby" | "jelly") {
  return service === "emby"
    ? <span className="pg-badge platform-emby">Emby</span>
    : <span className="pg-badge platform-jelly">Jellyfin</span>;
}

function CheckSection({
  service,
  servers,
  selectedServer,
  onSelectServer,
  onRun,
  running,
  result,
  error,
}: {
  service: "emby" | "jelly";
  servers: string[];
  selectedServer: string;
  onSelectServer: (value: string) => void;
  onRun: () => void;
  running: boolean;
  result: InconsistencyResult | null;
  error: string;
}) {
  const isEmby = service === "emby";
  const title = isEmby ? "Verifica utenti Emby" : "Verifica utenti Jellyfin";
  const serverLabel = isEmby ? "Server Emby" : "Server Jellyfin";
  const serverOnlyLabel = isEmby ? "Su Emby ma NON nel database" : "Su Jellyfin ma NON nel database";
  const dbOnlyLabel = isEmby ? "Nel database ma NON su Emby" : "Nel database ma NON su Jellyfin";

  return (
    <section className="config-section" style={{ marginBottom: 24 }}>
      <div className="config-section-header">
        <div>
          <h2 style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            {title}
            {serviceBadge(service)}
          </h2>
          <p>Confronta gli utenti presenti sul server con quelli salvati nel database locale.</p>
        </div>
      </div>

      <div style={{ padding: "1.1rem 1.15rem 1.25rem" }}>
        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", alignItems: "end", marginBottom: "1rem" }}>
          <div className="form-group" style={{ minWidth: 250, flex: "1 1 280px" }}>
            <label>{serverLabel}</label>
            <select value={selectedServer} onChange={(e) => onSelectServer(e.target.value)}>
              {servers.map((server) => (
                <option key={server} value={server}>{server}</option>
              ))}
            </select>
          </div>
          <button className="btn btn-primary" onClick={onRun} disabled={running || !selectedServer}>
            <Search size={15} /> {running ? "Calcolo..." : "Calcola"}
          </button>
        </div>

        {error && <div className="login-error" style={{ marginBottom: "1rem" }}>{error}</div>}

        {result && result.server_only.length === 0 && result.db_only.length === 0 && (
          <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "16px 20px", background: "rgba(52,211,153,0.08)", border: "1px solid rgba(52,211,153,0.25)", borderRadius: "16px", color: "#34d399", fontWeight: 600, marginBottom: "1rem" }}>
            <Server size={18} />
            Tutto a posto! Gli utenti del server <strong>{result.server_name}</strong> corrispondono al 100% con il database.
          </div>
        )}

        {result && (
          <div className="cards-grid" style={{ marginBottom: "1rem" }}>
            <div className="stat-card">
              <div className="stat-label">Utenti sul server</div>
              <div className="stat-value">{result.server_count}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Utenti nel database</div>
              <div className="stat-value">{result.db_count}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Solo server</div>
              <div className="stat-value" style={{ color: "#f87171" }}>{result.server_only.length}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Solo database</div>
              <div className="stat-value" style={{ color: "#fbbf24" }}>{result.db_only.length}</div>
            </div>
          </div>
        )}

        {result && result.server_only.length > 0 && (
          <div className="table-card" style={{ marginBottom: "1rem" }}>
            <div style={{ fontSize: ".75rem", textTransform: "uppercase", letterSpacing: ".1em", color: "#f87171", fontWeight: 700, padding: "1rem 1.1rem 0.85rem", display: "flex", alignItems: "center", gap: 8 }}>
              <AlertTriangle size={14} />
              {serverOnlyLabel} ({result.server_only.length})
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Username sul server</th>
                  </tr>
                </thead>
                <tbody>
                  {result.server_only.map((username, index) => (
                    <tr key={`${service}-server-only-${username}`}>
                      <td style={{ color: "var(--txt-muted)", fontSize: ".78rem" }}>{index + 1}</td>
                      <td style={{ color: "#f87171", fontWeight: 700 }}>{username}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {result && result.db_only.length > 0 && (
          <div className="table-card">
            <div style={{ fontSize: ".75rem", textTransform: "uppercase", letterSpacing: ".1em", color: "#fbbf24", fontWeight: 700, padding: "1rem 1.1rem 0.85rem", display: "flex", alignItems: "center", gap: 8 }}>
              <AlertTriangle size={14} />
              {dbOnlyLabel} ({result.db_only.length})
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Username nel DB</th>
                    <th>Scadenza (giorni)</th>
                    <th>Schermi</th>
                    <th>Nota</th>
                  </tr>
                </thead>
                <tbody>
                  {result.db_only.map((row, index) => (
                    <tr key={`${service}-db-only-${row.username}-${index}`}>
                      <td style={{ color: "var(--txt-muted)", fontSize: ".78rem" }}>{index + 1}</td>
                      <td style={{ color: "#fbbf24", fontWeight: 700 }}>{row.username}</td>
                      <td>{row.expiry ?? "—"}</td>
                      <td>{row.schermi ?? "—"}</td>
                      <td style={{ color: "var(--txt-soft)", fontSize: ".83rem" }}>{row.nota || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

export default function Inconsistenze() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [options, setOptions] = useState<OptionsResponse>({ emby_servers: [], jelly_servers: [] });
  const [embyServer, setEmbyServer] = useState("");
  const [jellyServer, setJellyServer] = useState("");
  const [embyRunning, setEmbyRunning] = useState(false);
  const [jellyRunning, setJellyRunning] = useState(false);
  const [embyResult, setEmbyResult] = useState<InconsistencyResult | null>(null);
  const [jellyResult, setJellyResult] = useState<InconsistencyResult | null>(null);
  const [embyError, setEmbyError] = useState("");
  const [jellyError, setJellyError] = useState("");

  if (user?.ruolo !== "admin") return <Navigate to="/dashboard" replace />;

  useEffect(() => {
    api.get("/admin/inconsistenze/options")
      .then((response) => {
        const data = response.data as OptionsResponse;
        setOptions(data);
        setEmbyServer(data.emby_servers[0] ?? "");
        setJellyServer(data.jelly_servers[0] ?? "");
      })
      .finally(() => setLoading(false));
  }, []);

  const runCheck = async (service: "emby" | "jelly") => {
    const serverName = service === "emby" ? embyServer : jellyServer;
    if (!serverName) return;

    if (service === "emby") {
      setEmbyRunning(true);
      setEmbyError("");
    } else {
      setJellyRunning(true);
      setJellyError("");
    }

    try {
      const response = await api.post("/admin/inconsistenze/check", {
        service,
        server_name: serverName,
      });
      if (service === "emby") setEmbyResult(response.data);
      else setJellyResult(response.data);
    } catch (err: any) {
      const message = err?.response?.data?.detail ?? "Errore durante il confronto.";
      if (service === "emby") setEmbyError(message);
      else setJellyError(message);
    } finally {
      if (service === "emby") setEmbyRunning(false);
      else setJellyRunning(false);
    }
  };

  return (
    <div className="pg">
      <div className="pg-title">Inconsistenze</div>
      <p style={{ marginTop: "-0.6rem", marginBottom: "1.25rem", color: "var(--txt-soft)", fontSize: ".9rem" }}>
        Confronta il database locale con gli utenti presenti sui server Emby e Jellyfin.
      </p>

      {loading ? (
        <div className="loading-wrap"><div className="spinner" /></div>
      ) : (
        <>
          <CheckSection
            service="emby"
            servers={options.emby_servers}
            selectedServer={embyServer}
            onSelectServer={setEmbyServer}
            onRun={() => runCheck("emby")}
            running={embyRunning}
            result={embyResult}
            error={embyError}
          />

          <CheckSection
            service="jelly"
            servers={options.jelly_servers}
            selectedServer={jellyServer}
            onSelectServer={setJellyServer}
            onRun={() => runCheck("jelly")}
            running={jellyRunning}
            result={jellyResult}
            error={jellyError}
          />
        </>
      )}
    </div>
  );
}
