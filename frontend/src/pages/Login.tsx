import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { motion } from "framer-motion";
import { useAuth } from "../contexts/AuthContext";

export default function Login() {
  const { login, token } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (token) return <Navigate to="/dashboard" replace />;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    const cleanedUsername = username.trim();
    if (!cleanedUsername) {
      setError("Inserisci lo username.");
      setLoading(false);
      return;
    }
    try {
      await login(cleanedUsername, password);
    } catch (err: any) {
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail;
      const code = err?.code ? String(err.code) : "";
      const message = err?.message ? String(err.message) : "";

      if (status === 401) {
        setError(detail || "Credenziali non valide. Controlla username e password.");
      } else if (status) {
        setError(`Errore API (${status}). ${detail || "Riprova tra poco."}`);
      } else {
        const debugParts = [code, message].filter(Boolean).join(" - ");
        setError(
          `Impossibile contattare api.emby.at. Controlla connessione, VPN, adblock o Cloudflare.${debugParts ? ` Dettaglio: ${debugParts}` : ""}`
        );
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-grid" />
      <div className="login-glow" />

      <motion.div
        className="login-card"
        initial={{ opacity: 0, y: 24, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      >
        <div className="login-logo">
          <div className="login-logo-box">SP</div>
          <div className="login-logo-text">
            Streaming <span>Panel</span> Next
          </div>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          {error && (
            <motion.div
              className="login-error"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
            >
              {error}
            </motion.div>
          )}
          <div>
            <label className="login-label">Username</label>
            <input
              className="login-input"
              type="text"
              placeholder="Inserisci username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
              required
            />
          </div>
          <div>
            <label className="login-label">Password</label>
            <input
              className="login-input"
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
              required
            />
          </div>
          <button className="login-btn" type="submit" disabled={loading}>
            {loading ? "Accesso in corso..." : "Accedi"}
          </button>
        </form>
      </motion.div>
    </div>
  );
}
