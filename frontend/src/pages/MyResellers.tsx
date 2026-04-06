import { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { ChevronRight } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import api from "../api/client";

interface Reseller {
  id: number;
  username: string;
  master: number | null;
  credito: number;
  idtelegram: number | null;
  ruolo: string;
}

export default function MyResellers() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [resellers, setResellers] = useState<Reseller[]>([]);
  const [loading, setLoading] = useState(true);

  const canAccess = user?.ruolo === "admin" || user?.ruolo === "master";
  if (!canAccess) return <Navigate to="/dashboard" replace />;

  useEffect(() => {
    api.get("/reseller/my-resellers")
      .then((r) => setResellers(r.data))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="pg">
      <div className="pg-title">I Miei Reseller</div>

      {loading ? (
        <div className="loading-wrap"><div className="spinner" /></div>
      ) : resellers.length === 0 ? (
        <div className="wip-wrap">
          <p>Nessun reseller associato al tuo account.</p>
        </div>
      ) : (
        <div className="table-card">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Username</th>
                  <th>Credito</th>
                  <th>Ruolo</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {resellers.map((r) => (
                  <tr key={r.id} onClick={() => navigate(`/resellers/${r.id}`)}>
                    <td style={{ color: "var(--txt-muted)", fontSize: ".78rem" }}>{r.id}</td>
                    <td style={{ fontWeight: 600 }}>{r.username}</td>
                    <td>{r.credito}</td>
                    <td>
                      <span className={`role-badge ${r.ruolo}`}>{r.ruolo}</span>
                    </td>
                    <td style={{ textAlign: "right", color: "var(--txt-muted)" }}>
                      <ChevronRight size={15} />
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
