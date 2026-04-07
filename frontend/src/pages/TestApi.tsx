import { useEffect, useMemo, useState } from "react";
import { Navigate } from "react-router-dom";
import { FlaskConical, LoaderCircle, Play, RefreshCcw } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import api from "../api/client";

interface ActionOption {
  id: string;
  label: string;
}

interface OptionsResponse {
  emby_servers: string[];
  jelly_servers: string[];
  plex_servers: string[];
  emby_actions: ActionOption[];
  jelly_actions: ActionOption[];
  plex_actions: ActionOption[];
}

type ServiceType = "emby" | "jelly" | "plex";

const QUICK_ACTIONS: Array<{
  service: ServiceType;
  action: string;
  title: string;
  description: string;
}> = [
  {
    service: "emby",
    action: "least_used_normal",
    title: "Emby normale meno usato",
    description: "Legge tutti i server Emby normali e restituisce quello col carico minore.",
  },
  {
    service: "emby",
    action: "random_premium",
    title: "Emby premium casuale",
    description: "Seleziona un server premium con limite = no per verificare il bilanciamento premium.",
  },
  {
    service: "emby",
    action: "server_status",
    title: "Stato server Emby",
    description: "Mostra utenti, capienza e rapporto di carico dei server Emby.",
  },
  {
    service: "jelly",
    action: "server_status",
    title: "Stato server Jellyfin",
    description: "Conta gli utenti attuali su ogni server Jellyfin configurato.",
  },
  {
    service: "plex",
    action: "server_status",
    title: "Stato server Plex",
    description: "Conta gli utenti condivisi su ogni server Plex e i posti residui stimati.",
  },
];

function prettyJson(value: unknown) {
  return JSON.stringify(value, null, 2);
}

export default function TestApi() {
  const { user } = useAuth();
  const [options, setOptions] = useState<OptionsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState("");
  const [service, setService] = useState<ServiceType>("emby");
  const [action, setAction] = useState("least_used_normal");
  const [serverName, setServerName] = useState("");
  const [serverType, setServerType] = useState("normale");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("");
  const [defaultMax, setDefaultMax] = useState("99");

  if (user?.ruolo !== "admin") return <Navigate to="/dashboard" replace />;

  const loadOptions = async () => {
    try {
      const response = await api.get("/admin/testapi/options");
      setOptions(response.data);
      setError("");
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Errore durante il caricamento delle opzioni test.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadOptions();
  }, []);

  const actionOptions = useMemo(() => {
    if (!options) return [];
    if (service === "emby") return options.emby_actions;
    if (service === "jelly") return options.jelly_actions;
    return options.plex_actions;
  }, [options, service]);

  const serverOptions = useMemo(() => {
    if (!options) return [];
    if (service === "emby") return options.emby_servers;
    if (service === "jelly") return options.jelly_servers;
    return options.plex_servers;
  }, [options, service]);

  useEffect(() => {
    if (!actionOptions.length) return;
    setAction((prev) => (actionOptions.some((item) => item.id === prev) ? prev : actionOptions[0].id));
  }, [actionOptions]);

  useEffect(() => {
    if (!serverOptions.length) {
      setServerName("");
      return;
    }
    setServerName((prev) => (serverOptions.includes(prev) ? prev : serverOptions[0]));
  }, [serverOptions]);

  const requiresServer = ["list_users", "create_user", "delete_user", "change_password", "disable_4k", "enable_4k", "send_invite", "remove_invite", "remove_user"].includes(action);
  const requiresUsername = ["create_user", "delete_user", "change_password", "disable_4k", "enable_4k", "remove_invite", "remove_user"].includes(action);
  const requiresPassword = ["create_user", "change_password"].includes(action);
  const requiresEmail = ["verify_email", "send_invite"].includes(action);
  const showsServerType = service === "emby" && action === "server_status";
  const showsDefaultMax = service === "plex" && action === "server_status";

  const runAction = async (payload: Record<string, unknown>) => {
    setRunning(true);
    setError("");
    try {
      const response = await api.post("/admin/testapi/run", payload);
      setResult(prettyJson(response.data.result));
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Errore durante l'esecuzione del test.");
    } finally {
      setRunning(false);
    }
  };

  const handleRun = async (event: React.FormEvent) => {
    event.preventDefault();
    await runAction({
      service,
      action,
      server_name: requiresServer ? serverName : undefined,
      server_type: showsServerType ? serverType : undefined,
      username: requiresUsername ? username : undefined,
      password: requiresPassword ? password : undefined,
      email: requiresEmail ? email : undefined,
      default_max: showsDefaultMax ? Number(defaultMax) || 99 : undefined,
    });
  };

  return (
    <div className="pg">
      <div className="manage-header">
        <div>
          <div className="pg-title" style={{ marginBottom: "0.35rem" }}>
            <FlaskConical size={18} />
            <span>Test API</span>
          </div>
          <p className="manage-subtitle">
            Da qui puoi provare alcune funzioni interne di `embyapi.py`, `jellyapi.py` e `plexapi.py` senza esporle come API pubbliche normali.
          </p>
        </div>
        <button className="btn btn-ghost" type="button" onClick={loadOptions} disabled={loading || running}>
          <RefreshCcw size={15} /> Aggiorna
        </button>
      </div>

      {error && <div className="login-error">{error}</div>}

      {loading ? (
        <div className="loading-wrap"><div className="spinner" /></div>
      ) : (
        <>
          <div className="testapi-grid">
            {QUICK_ACTIONS.map((item) => (
              <section className="testapi-card" key={`${item.service}-${item.action}`}>
                <div className="testapi-card-head">
                  <div className="testapi-card-title">{item.title}</div>
                  <span className="config-count">{item.service.toUpperCase()}</span>
                </div>
                <p className="testapi-card-desc">{item.description}</p>
                <button
                  className="btn btn-primary"
                  type="button"
                  onClick={() =>
                    runAction({
                      service: item.service,
                      action: item.action,
                      server_type: item.service === "emby" && item.action === "server_status" ? "normale" : undefined,
                      default_max: item.service === "plex" ? Number(defaultMax) || 99 : undefined,
                    })
                  }
                  disabled={running}
                >
                  {running ? <LoaderCircle size={15} className="spin-inline" /> : <Play size={15} />}
                  Esegui test
                </button>
              </section>
            ))}
          </div>

          <div className="config-section" style={{ marginTop: "18px" }}>
            <div className="config-section-header">
              <div>
                <h2>Runner manuale</h2>
                <p>Scegli servizio, funzione e parametri minimi per provare le chiamate interne direttamente dal pannello.</p>
              </div>
            </div>

            <form className="manage-form" onSubmit={handleRun}>
              <div className="config-fields-grid">
                <label className="config-field">
                  <span>Servizio</span>
                  <select value={service} onChange={(e) => setService(e.target.value as ServiceType)}>
                    <option value="emby">Emby</option>
                    <option value="jelly">Jellyfin</option>
                    <option value="plex">Plex</option>
                  </select>
                </label>

                <label className="config-field">
                  <span>Azione</span>
                  <select value={action} onChange={(e) => setAction(e.target.value)}>
                    {actionOptions.map((item) => (
                      <option key={item.id} value={item.id}>{item.label}</option>
                    ))}
                  </select>
                </label>

                {requiresServer ? (
                  <label className="config-field">
                    <span>Server</span>
                    <select value={serverName} onChange={(e) => setServerName(e.target.value)}>
                      {serverOptions.map((item) => (
                        <option key={item} value={item}>{item}</option>
                      ))}
                    </select>
                  </label>
                ) : (
                  <div className="config-field">
                    <span>Server</span>
                    <input value="Non richiesto" disabled />
                  </div>
                )}

                {showsServerType && (
                  <label className="config-field">
                    <span>Tipo server Emby</span>
                    <select value={serverType} onChange={(e) => setServerType(e.target.value)}>
                      <option value="normale">Normale</option>
                      <option value="premium">Premium</option>
                    </select>
                  </label>
                )}

                {requiresUsername && (
                  <label className="config-field">
                    <span>Username</span>
                    <input
                      type="text"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      placeholder={service === "plex" ? "username o email Plex" : "username"}
                    />
                  </label>
                )}

                {requiresPassword && (
                  <label className="config-field">
                    <span>Password</span>
                    <input
                      type="text"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="password nuova o iniziale"
                    />
                  </label>
                )}

                {requiresEmail && (
                  <label className="config-field">
                    <span>Email</span>
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="utente@example.com"
                    />
                  </label>
                )}

                {showsDefaultMax && (
                  <label className="config-field">
                    <span>Capienza default Plex</span>
                    <input
                      type="number"
                      min="1"
                      value={defaultMax}
                      onChange={(e) => setDefaultMax(e.target.value)}
                    />
                  </label>
                )}
              </div>

              <div className="manage-footer">
                <button className="btn btn-primary" type="submit" disabled={running}>
                  {running ? <LoaderCircle size={15} className="spin-inline" /> : <Play size={15} />}
                  Esegui funzione
                </button>
              </div>
            </form>
          </div>

          <div className="config-section" style={{ marginTop: "18px" }}>
            <div className="config-section-header">
              <div>
                <h2>Risultato</h2>
                <p>Output grezzo della funzione interna, utile per fare debug rapido prima di richiamarla da altri script.</p>
              </div>
            </div>
            <div className="testapi-result">
              <pre>{result || "Nessun test eseguito finora."}</pre>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
