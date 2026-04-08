import { useState } from "react";
import { Navigate } from "react-router-dom";
import { RefreshCcw, Wrench } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import api from "../api/client";

interface RenameResult {
  message: string;
  old_username: string;
  new_username: string;
  updated_reseller: number;
  updated_emby_users: number;
  updated_jelly_users: number;
  updated_plex_users: number;
  updated_movements: number;
}

export default function Funzioni() {
  const { user } = useAuth();
  const [oldUsername, setOldUsername] = useState("");
  const [newUsername, setNewUsername] = useState("");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<RenameResult | null>(null);

  if (user?.ruolo !== "admin") return <Navigate to="/dashboard" replace />;

  const resetForm = () => {
    setOldUsername("");
    setNewUsername("");
    setError("");
    setResult(null);
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    setResult(null);

    if (!oldUsername.trim() || !newUsername.trim()) {
      setError("Compila sia il vecchio username sia il nuovo username.");
      return;
    }

    setRunning(true);
    try {
      const response = await api.post("/admin/functions/rename-reseller-username", {
        old_username: oldUsername.trim(),
        new_username: newUsername.trim(),
      });
      setResult(response.data);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Errore durante la modifica username.");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="pg">
      <div className="manage-header">
        <div>
          <div className="pg-title" style={{ marginBottom: "0.35rem" }}>
            <Wrench size={18} />
            <span>Funzioni</span>
          </div>
          <p className="manage-subtitle">
            Raccolta di funzioni operative riservate agli admin.
          </p>
        </div>
        <button className="btn btn-ghost" type="button" onClick={resetForm} disabled={running}>
          <RefreshCcw size={15} /> Reset
        </button>
      </div>

      {error && <div className="login-error">{error}</div>}

      {result && (
        <div className="save-success">
          {result.message}
        </div>
      )}

      <section className="config-section">
        <div className="config-section-header">
          <div>
            <h2>Modifica username reseller</h2>
            <p>
              Aggiorna lo username del reseller nella tabella `reseller` e in tutti gli utenti Emby, Jellyfin e Plex associati.
            </p>
          </div>
        </div>

        <form className="manage-form" onSubmit={handleSubmit}>
          <div className="config-fields-grid">
            <label className="config-field">
              <span>Vecchio username</span>
              <input
                value={oldUsername}
                onChange={(e) => setOldUsername(e.target.value)}
                placeholder="es. mario"
                autoComplete="off"
                disabled={running}
              />
            </label>

            <label className="config-field">
              <span>Nuovo username</span>
              <input
                value={newUsername}
                onChange={(e) => setNewUsername(e.target.value)}
                placeholder="es. mario_new"
                autoComplete="off"
                disabled={running}
              />
            </label>
          </div>

          <div className="create-note" style={{ marginTop: "1rem" }}>
            La modifica aggiorna anche lo storico movimenti del reseller, cosi statistiche e pagina movimenti restano coerenti.
          </div>

          <div className="config-section-actions" style={{ marginTop: "1rem" }}>
            <button className="btn btn-primary" type="submit" disabled={running}>
              {running ? "Aggiornamento..." : "Esegui modifica"}
            </button>
          </div>
        </form>

        {result && (
          <div className="cards-grid" style={{ marginTop: "1.25rem" }}>
            <div className="stat-card">
              <div className="stat-label">Reseller aggiornato</div>
              <div className="stat-value">{result.updated_reseller}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Utenti Emby aggiornati</div>
              <div className="stat-value">{result.updated_emby_users}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Utenti Jellyfin aggiornati</div>
              <div className="stat-value">{result.updated_jelly_users}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Utenti Plex aggiornati</div>
              <div className="stat-value">{result.updated_plex_users}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Movimenti aggiornati</div>
              <div className="stat-value">{result.updated_movements}</div>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
