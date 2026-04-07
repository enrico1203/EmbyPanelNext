import { useEffect, useMemo, useState } from "react";
import { Navigate } from "react-router-dom";
import { CalendarClock, LoaderCircle, Play, Save, RefreshCcw } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import api from "../api/client";

interface SchedulerTask {
  id: string;
  name: string;
  description: string;
  timeout: number;
  interval_hours: number;
  enabled: boolean;
  running: boolean;
  last_run: string | null;
  last_status: string | null;
  last_output: string | null;
}

export default function Scheduler() {
  const { user } = useAuth();
  const [tasks, setTasks] = useState<SchedulerTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [runningTaskId, setRunningTaskId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  if (user?.ruolo !== "admin") return <Navigate to="/dashboard" replace />;

  const hasRunningTask = useMemo(() => tasks.some((task) => task.running), [tasks]);

  const load = async (keepState = false) => {
    try {
      const response = await api.get("/admin/scheduler");
      setTasks(response.data.tasks);
      if (!keepState) {
        setError("");
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Errore durante il caricamento scheduler.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    if (!hasRunningTask) return;
    const timer = window.setInterval(() => {
      load(true);
    }, 5000);
    return () => window.clearInterval(timer);
  }, [hasRunningTask]);

  const updateTask = (taskId: string, changes: Partial<SchedulerTask>) => {
    setSuccess("");
    setTasks((prev) =>
      prev.map((task) => (task.id === taskId ? { ...task, ...changes } : task))
    );
  };

  const handleSave = async () => {
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await api.put("/admin/scheduler", {
        tasks: tasks.map((task) => ({
          id: task.id,
          interval_hours: Math.max(0, Number(task.interval_hours) || 0),
          enabled: task.enabled,
        })),
      });
      await load(true);
      setSuccess("Schedulazioni salvate con successo.");
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Errore durante il salvataggio.");
    } finally {
      setSaving(false);
    }
  };

  const handleRunNow = async (taskId: string) => {
    setRunningTaskId(taskId);
    setError("");
    setSuccess("");
    try {
      const response = await api.post(`/admin/scheduler/${taskId}/run`);
      setTasks(response.data.tasks);
      setSuccess("Task avviata manualmente.");
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Errore durante l'avvio della task.");
    } finally {
      setRunningTaskId(null);
    }
  };

  return (
    <div className="pg">
      <div className="manage-header">
        <div>
          <div className="pg-title" style={{ marginBottom: "0.35rem" }}>Scheduler</div>
          <p className="manage-subtitle">
            Le task girano nel container dedicato `nextscheduler`, leggono `schedules.json` e puoi avviarle manualmente da qui.
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
          <button className="btn btn-ghost" type="button" onClick={() => load(true)} disabled={loading}>
            <RefreshCcw size={15} /> Aggiorna
          </button>
          <button className="btn btn-primary" type="button" onClick={handleSave} disabled={loading || saving}>
            <Save size={15} /> {saving ? "Salvataggio..." : "Salva"}
          </button>
        </div>
      </div>

      {error && <div className="login-error">{error}</div>}
      {success && <div className="save-success">{success}</div>}

      {loading ? (
        <div className="loading-wrap"><div className="spinner" /></div>
      ) : (
        <div className="scheduler-grid">
          {tasks.map((task) => (
            <section className="scheduler-card" key={task.id}>
              <div className="scheduler-card-head">
                <div>
                  <div className="scheduler-card-title">
                    <CalendarClock size={16} />
                    <span>{task.name}</span>
                  </div>
                  <p className="scheduler-card-desc">{task.description}</p>
                </div>
                <span className={`scheduler-status ${task.running ? "running" : task.last_status ?? "idle"}`}>
                  {task.running ? "In esecuzione" : task.last_status ?? "Mai eseguita"}
                </span>
              </div>

              <div className="scheduler-controls">
                <label className="config-field">
                  <span>Ogni quante ore</span>
                  <input
                    type="number"
                    min="0"
                    value={task.interval_hours}
                    onChange={(e) =>
                      updateTask(task.id, { interval_hours: Math.max(0, Number(e.target.value) || 0) })
                    }
                  />
                </label>
                <label className="scheduler-toggle">
                  <input
                    type="checkbox"
                    checked={task.enabled}
                    onChange={(e) => updateTask(task.id, { enabled: e.target.checked })}
                  />
                  <span>Abilitata</span>
                </label>
              </div>

              <div className="scheduler-meta">
                <div><strong>Timeout:</strong> {Math.round(task.timeout / 60)} min</div>
                <div><strong>Ultima esecuzione:</strong> {task.last_run ?? "Mai"}</div>
              </div>

              <div className="scheduler-actions">
                <button
                  className="btn btn-primary"
                  type="button"
                  onClick={() => handleRunNow(task.id)}
                  disabled={task.running || runningTaskId === task.id}
                >
                  {runningTaskId === task.id ? <LoaderCircle size={15} className="spin-inline" /> : <Play size={15} />}
                  Avvia ora
                </button>
              </div>

              <div className="scheduler-log-box">
                <div className="scheduler-log-title">Ultimo log</div>
                <pre>{task.last_output ?? "Nessun log disponibile."}</pre>
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
