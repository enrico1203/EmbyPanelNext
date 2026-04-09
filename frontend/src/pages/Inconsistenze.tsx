import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { AlertTriangle, Search, Server } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import api from "../api/client";

type Service = "emby" | "jelly";

interface InconsistencyDbUser {
  username: string;
  reseller: string | null;
  expiry: number | null;
  schermi: number | null;
  k4: string | null;
  download: string | null;
  password: string | null;
  nota: string | null;
}

interface InconsistencyResult {
  service: Service;
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

interface FeedbackState {
  type: "success" | "error";
  text: string;
}

interface ResolveToDbModalState {
  service: Service;
  serverName: string;
  username: string;
}

interface RecreateModalState {
  service: Service;
  serverName: string;
  row: InconsistencyDbUser;
}

function serviceBadge(service: Service) {
  return service === "emby" ? (
    <span className="pg-badge platform-emby">Emby</span>
  ) : (
    <span className="pg-badge platform-jelly">Jellyfin</span>
  );
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
  onResolveServerOnly,
  onDeleteServerOnly,
  onResolveDbOnly,
}: {
  service: Service;
  servers: string[];
  selectedServer: string;
  onSelectServer: (value: string) => void;
  onRun: () => void;
  running: boolean;
  result: InconsistencyResult | null;
  error: string;
  onResolveServerOnly: (service: Service, serverName: string, username: string) => void;
  onDeleteServerOnly: (service: Service, serverName: string, username: string) => void;
  onResolveDbOnly: (service: Service, serverName: string, row: InconsistencyDbUser) => void;
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
                <option key={server} value={server}>
                  {server}
                </option>
              ))}
            </select>
          </div>
          <button className="btn btn-primary" onClick={onRun} disabled={running || !selectedServer}>
            <Search size={15} /> {running ? "Calcolo..." : "Calcola"}
          </button>
        </div>

        {error && <div className="login-error" style={{ marginBottom: "1rem" }}>{error}</div>}

        {result && result.server_only.length === 0 && result.db_only.length === 0 && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              padding: "16px 20px",
              background: "rgba(52,211,153,0.08)",
              border: "1px solid rgba(52,211,153,0.25)",
              borderRadius: "16px",
              color: "#34d399",
              fontWeight: 600,
              marginBottom: "1rem",
            }}
          >
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
            <div
              style={{
                fontSize: ".75rem",
                textTransform: "uppercase",
                letterSpacing: ".1em",
                color: "#f87171",
                fontWeight: 700,
                padding: "1rem 1.1rem 0.85rem",
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              <AlertTriangle size={14} />
              {serverOnlyLabel} ({result.server_only.length})
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Username sul server</th>
                    <th style={{ width: 260 }}>Azione</th>
                  </tr>
                </thead>
                <tbody>
                  {result.server_only.map((username, index) => (
                    <tr key={`${service}-server-only-${username}`}>
                      <td style={{ color: "var(--txt-muted)", fontSize: ".78rem" }}>{index + 1}</td>
                      <td style={{ color: "#f87171", fontWeight: 700 }}>{username}</td>
                      <td>
                        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                          <button
                            className="btn btn-ghost"
                            type="button"
                            onClick={() => onResolveServerOnly(service, result.server_name, username)}
                          >
                            Risolvi
                          </button>
                          <button
                            className="btn btn-ghost"
                            type="button"
                            onClick={() => onDeleteServerOnly(service, result.server_name, username)}
                            style={{ borderColor: "rgba(239,68,68,0.28)", color: "#f87171" }}
                          >
                            Elimina
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {result && result.db_only.length > 0 && (
          <div className="table-card">
            <div
              style={{
                fontSize: ".75rem",
                textTransform: "uppercase",
                letterSpacing: ".1em",
                color: "#fbbf24",
                fontWeight: 700,
                padding: "1rem 1.1rem 0.85rem",
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              <AlertTriangle size={14} />
              {dbOnlyLabel} ({result.db_only.length})
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Username nel DB</th>
                    <th>Reseller</th>
                    <th>Scadenza (giorni)</th>
                    <th>Schermi</th>
                    <th>Nota</th>
                    <th style={{ width: 140 }}>Azione</th>
                  </tr>
                </thead>
                <tbody>
                  {result.db_only.map((row, index) => (
                    <tr key={`${service}-db-only-${row.username}-${index}`}>
                      <td style={{ color: "var(--txt-muted)", fontSize: ".78rem" }}>{index + 1}</td>
                      <td style={{ color: "#fbbf24", fontWeight: 700 }}>{row.username}</td>
                      <td>{row.reseller || "—"}</td>
                      <td>{row.expiry ?? "—"}</td>
                      <td>{row.schermi ?? "—"}</td>
                      <td style={{ color: "var(--txt-soft)", fontSize: ".83rem" }}>{row.nota || "—"}</td>
                      <td>
                        <button
                          className="btn btn-ghost"
                          type="button"
                          onClick={() => onResolveDbOnly(service, result.server_name, row)}
                        >
                          Risolvi
                        </button>
                      </td>
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
  const [feedback, setFeedback] = useState<FeedbackState | null>(null);
  const [resolveToDbModal, setResolveToDbModal] = useState<ResolveToDbModalState | null>(null);
  const [recreateModal, setRecreateModal] = useState<RecreateModalState | null>(null);
  const [resolveSubmitting, setResolveSubmitting] = useState(false);
  const [resolveDbForm, setResolveDbForm] = useState({
    reseller: "",
    expiry: "30",
    schermi: "1",
    password: "",
    k4: "false",
    download: "false",
    nota: "",
  });
  const [recreatePassword, setRecreatePassword] = useState("");

  if (user?.ruolo !== "admin") return <Navigate to="/dashboard" replace />;

  useEffect(() => {
    api
      .get("/admin/inconsistenze/options")
      .then((response) => {
        const data = response.data as OptionsResponse;
        setOptions(data);
        setEmbyServer(data.emby_servers[0] ?? "");
        setJellyServer(data.jelly_servers[0] ?? "");
      })
      .finally(() => setLoading(false));
  }, []);

  const runCheck = async (service: Service) => {
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

  const openResolveToDbModal = (service: Service, serverName: string, username: string) => {
    setFeedback(null);
    setResolveDbForm({
      reseller: "",
      expiry: "30",
      schermi: "1",
      password: "",
      k4: "false",
      download: "false",
      nota: "",
    });
    setResolveToDbModal({ service, serverName, username });
  };

  const openRecreateModal = (service: Service, serverName: string, row: InconsistencyDbUser) => {
    setFeedback(null);
    setRecreatePassword(row.password ?? "");
    setRecreateModal({ service, serverName, row });
  };

  const closeModals = () => {
    if (resolveSubmitting) return;
    setResolveToDbModal(null);
    setRecreateModal(null);
  };

  const submitResolveToDb = async () => {
    if (!resolveToDbModal) return;
    setResolveSubmitting(true);
    setFeedback(null);
    try {
      const response = await api.post("/admin/inconsistenze/resolve-to-db", {
        service: resolveToDbModal.service,
        server_name: resolveToDbModal.serverName,
        username: resolveToDbModal.username,
        reseller: resolveDbForm.reseller,
        expiry: Number(resolveDbForm.expiry),
        schermi: Number(resolveDbForm.schermi),
        password: resolveDbForm.password,
        k4: resolveDbForm.k4,
        download: resolveDbForm.download,
        nota: resolveDbForm.nota.trim() || null,
      });
      setResolveToDbModal(null);
      await runCheck(resolveToDbModal.service);
      setFeedback({ type: "success", text: response.data?.message ?? "Utente aggiunto al database." });
    } catch (err: any) {
      setFeedback({
        type: "error",
        text: err?.response?.data?.detail ?? "Errore durante il salvataggio nel database.",
      });
    } finally {
      setResolveSubmitting(false);
    }
  };

  const submitRecreateRemote = async () => {
    if (!recreateModal) return;
    setResolveSubmitting(true);
    setFeedback(null);
    try {
      const response = await api.post("/admin/inconsistenze/recreate-on-server", {
        service: recreateModal.service,
        server_name: recreateModal.serverName,
        username: recreateModal.row.username,
        password: recreatePassword.trim() || undefined,
      });
      setRecreateModal(null);
      await runCheck(recreateModal.service);
      setFeedback({ type: "success", text: response.data?.message ?? "Utente ricreato sul server." });
    } catch (err: any) {
      setFeedback({
        type: "error",
        text: err?.response?.data?.detail ?? "Errore durante la ricreazione sul server.",
      });
    } finally {
      setResolveSubmitting(false);
    }
  };

  const deleteRemoteUser = async (service: Service, serverName: string, username: string) => {
    const serviceLabel = service === "emby" ? "Emby" : "Jellyfin";
    const confirmed = window.confirm(
      `Vuoi eliminare ${username} direttamente dal server ${serviceLabel} ${serverName}?`
    );
    if (!confirmed) return;

    setResolveSubmitting(true);
    setFeedback(null);
    try {
      const response = await api.post("/admin/inconsistenze/delete-on-server", {
        service,
        server_name: serverName,
        username,
      });
      await runCheck(service);
      setFeedback({
        type: "success",
        text: response.data?.message ?? "Utente eliminato dal server.",
      });
    } catch (err: any) {
      setFeedback({
        type: "error",
        text: err?.response?.data?.detail ?? "Errore durante l'eliminazione sul server.",
      });
    } finally {
      setResolveSubmitting(false);
    }
  };

  return (
    <div className="pg">
      <div className="pg-title">Inconsistenze</div>
      <p style={{ marginTop: "-0.6rem", marginBottom: "1.25rem", color: "var(--txt-soft)", fontSize: ".9rem" }}>
        Confronta il database locale con gli utenti presenti sui server Emby e Jellyfin.
      </p>

      {feedback && (
        <div
          className={feedback.type === "error" ? "login-error" : undefined}
          style={
            feedback.type === "success"
              ? {
                  marginBottom: "1rem",
                  padding: "14px 16px",
                  borderRadius: 14,
                  border: "1px solid rgba(52,211,153,0.25)",
                  background: "rgba(52,211,153,0.08)",
                  color: "#34d399",
                  fontWeight: 600,
                }
              : { marginBottom: "1rem" }
          }
        >
          {feedback.text}
        </div>
      )}

      {loading ? (
        <div className="loading-wrap">
          <div className="spinner" />
        </div>
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
            onResolveServerOnly={openResolveToDbModal}
            onDeleteServerOnly={deleteRemoteUser}
            onResolveDbOnly={openRecreateModal}
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
            onResolveServerOnly={openResolveToDbModal}
            onDeleteServerOnly={deleteRemoteUser}
            onResolveDbOnly={openRecreateModal}
          />
        </>
      )}

      {resolveToDbModal && (
        <div className="modal-overlay" onClick={(event) => event.target === event.currentTarget && closeModals()}>
          <div className="modal" style={{ maxWidth: 760 }}>
            <div className="modal-header">
              <span className="modal-title">Risolvi: aggiungi al database</span>
              <button className="btn-ic" type="button" onClick={closeModals} disabled={resolveSubmitting}>
                ✕
              </button>
            </div>
            <div className="modal-body">
              <div style={{ color: "var(--txt-soft)", lineHeight: 1.6 }}>
                Stai aggiungendo <strong>{resolveToDbModal.username}</strong> al database {serviceBadge(resolveToDbModal.service)} sul server{" "}
                <strong>{resolveToDbModal.serverName}</strong>.
              </div>

              <div className="detail-modal-grid">
                <div className="form-group">
                  <label className="modal-label">Reseller</label>
                  <input
                    value={resolveDbForm.reseller}
                    onChange={(e) => setResolveDbForm((prev) => ({ ...prev, reseller: e.target.value }))}
                    placeholder="Username reseller"
                  />
                </div>
                <div className="form-group">
                  <label className="modal-label">Password</label>
                  <input
                    type="text"
                    value={resolveDbForm.password}
                    onChange={(e) => setResolveDbForm((prev) => ({ ...prev, password: e.target.value }))}
                    placeholder="Password utente"
                  />
                </div>
                <div className="form-group">
                  <label className="modal-label">Scadenza Giorni</label>
                  <input
                    type="number"
                    min={1}
                    value={resolveDbForm.expiry}
                    onChange={(e) => setResolveDbForm((prev) => ({ ...prev, expiry: e.target.value }))}
                  />
                </div>
                <div className="form-group">
                  <label className="modal-label">Schermi</label>
                  <select
                    value={resolveDbForm.schermi}
                    onChange={(e) => setResolveDbForm((prev) => ({ ...prev, schermi: e.target.value }))}
                  >
                    <option value="1">1</option>
                    <option value="2">2</option>
                    <option value="3">3</option>
                    <option value="4">4</option>
                  </select>
                </div>
                <div className="form-group">
                  <label className="modal-label">4K</label>
                  <select
                    value={resolveDbForm.k4}
                    onChange={(e) => setResolveDbForm((prev) => ({ ...prev, k4: e.target.value }))}
                  >
                    <option value="false">No</option>
                    <option value="true">Sì</option>
                  </select>
                </div>
                <div className="form-group">
                  <label className="modal-label">Download</label>
                  <select
                    value={resolveDbForm.download}
                    onChange={(e) => setResolveDbForm((prev) => ({ ...prev, download: e.target.value }))}
                  >
                    <option value="false">No</option>
                    <option value="true">Sì</option>
                  </select>
                </div>
              </div>

              <div className="form-group">
                <label className="modal-label">Nota</label>
                <textarea
                  rows={3}
                  value={resolveDbForm.nota}
                  onChange={(e) => setResolveDbForm((prev) => ({ ...prev, nota: e.target.value }))}
                  placeholder="Nota opzionale"
                  style={{
                    width: "100%",
                    borderRadius: 12,
                    border: "1px solid var(--border)",
                    background: "var(--bg-2)",
                    color: "var(--txt)",
                    padding: "12px 14px",
                    resize: "vertical",
                    font: "inherit",
                  }}
                />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" type="button" onClick={closeModals} disabled={resolveSubmitting}>
                Annulla
              </button>
              <button className="btn btn-primary" type="button" onClick={submitResolveToDb} disabled={resolveSubmitting}>
                {resolveSubmitting ? "Salvataggio..." : "Salva nel database"}
              </button>
            </div>
          </div>
        </div>
      )}

      {recreateModal && (
        <div className="modal-overlay" onClick={(event) => event.target === event.currentTarget && closeModals()}>
          <div className="modal" style={{ maxWidth: 560 }}>
            <div className="modal-header">
              <span className="modal-title">Risolvi: ricrea sul server</span>
              <button className="btn-ic" type="button" onClick={closeModals} disabled={resolveSubmitting}>
                ✕
              </button>
            </div>
            <div className="modal-body">
              <p style={{ margin: 0, color: "var(--txt-soft)", lineHeight: 1.7 }}>
                Verrà ricreato o riallineato sul server <strong>{recreateModal.serverName}</strong> l'utente{" "}
                <strong>{recreateModal.row.username}</strong>, mantenendo i dati del database.
              </p>
              <div className="detail-modal-grid">
                <div className="form-group">
                  <label className="modal-label">Reseller</label>
                  <input value={recreateModal.row.reseller ?? ""} readOnly />
                </div>
                <div className="form-group">
                  <label className="modal-label">Schermi</label>
                  <input value={String(recreateModal.row.schermi ?? "")} readOnly />
                </div>
                <div className="form-group">
                  <label className="modal-label">4K</label>
                  <input value={recreateModal.row.k4 ?? "false"} readOnly />
                </div>
                <div className="form-group">
                  <label className="modal-label">Download</label>
                  <input value={recreateModal.row.download ?? "false"} readOnly />
                </div>
              </div>
              <div className="form-group">
                <label className="modal-label">Password</label>
                <input
                  type="text"
                  value={recreatePassword}
                  onChange={(e) => setRecreatePassword(e.target.value)}
                  placeholder="Necessaria per ricreare l'utente"
                />
              </div>
              {recreateModal.row.nota && (
                <div style={{ color: "var(--txt-soft)", fontSize: ".9rem", lineHeight: 1.6 }}>
                  <strong>Nota:</strong> {recreateModal.row.nota}
                </div>
              )}
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" type="button" onClick={closeModals} disabled={resolveSubmitting}>
                Annulla
              </button>
              <button className="btn btn-primary" type="button" onClick={submitRecreateRemote} disabled={resolveSubmitting}>
                {resolveSubmitting ? "Invio..." : "Ricrea sul server"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
