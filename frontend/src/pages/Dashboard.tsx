import { useEffect, useRef, useState } from "react";
import { Coins, User, Shield, Tv, Users, AlertTriangle, Clock, TrendingUp, Zap } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import api from "../api/client";

interface Stats {
  emby_users: number;
  jelly_users: number;
  plex_users: number;
  plex_available_slots: number;
  total_users: number;
  total_resellers: number;
  my_resellers: number;
  expiring_7: number;
  expired: number;
  dashboard_message?: string | null;
  monthly_recharges_remaining?: number | null;
  cat_url: string | null;
}

/* ── Animated counter hook ────────────────────────────────── */
function useCountUp(target: number, duration = 900, started = false) {
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (!started || target === 0) { setValue(target); return; }
    const start = performance.now();
    const tick = (now: number) => {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3); // easeOutCubic
      setValue(Math.round(eased * target));
      if (progress < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }, [target, started, duration]);
  return value;
}

/* ── Skeleton ─────────────────────────────────────────────── */
function SkeletonCard({ delay = "0s" }: { delay?: string }) {
  return (
    <div className="stat-card" style={{ transitionDelay: delay }}>
      <div style={{
        width: 40, height: 40, borderRadius: 11,
        background: "var(--bg-3)", marginBottom: 14,
        animation: "sk-pulse 1.4s ease-in-out infinite",
        animationDelay: delay,
      }} />
      <div style={{
        height: 9, width: "50%", borderRadius: 5,
        background: "var(--bg-3)", marginBottom: 10,
        animation: "sk-pulse 1.4s ease-in-out infinite",
        animationDelay: delay,
      }} />
      <div style={{
        height: 30, width: "38%", borderRadius: 8,
        background: "var(--bg-3)",
        animation: "sk-pulse 1.4s ease-in-out infinite",
        animationDelay: delay,
      }} />
    </div>
  );
}

function SkeletonSection({ count, label }: { count: number; label: string }) {
  return (
    <div className="section-group" style={{ marginBottom: 18 }}>
      <div style={{
        height: 9, width: 110, borderRadius: 5,
        background: "var(--bg-3)", marginBottom: 14,
        animation: "sk-pulse 1.4s ease-in-out infinite",
      }} />
      <div className="cards-grid">
        {Array.from({ length: count }).map((_, i) => (
          <SkeletonCard key={`${label}-${i}`} delay={`${i * 0.07}s`} />
        ))}
      </div>
    </div>
  );
}

/* ── Section label ────────────────────────────────────────── */
function SectionLabel({ children, dotColor }: { children: string; dotColor?: string }) {
  return (
    <div className="section-label-v2" style={{ "--section-dot": dotColor } as React.CSSProperties}>
      <div className="section-label-v2-dot" />
      <div className="section-label-v2-text">{children}</div>
      <div className="section-label-v2-line" />
    </div>
  );
}

/* ── Dashboard message parser ─────────────────────────────── */
function parseDashboardMessage(message?: string | null) {
  const lines = (message ?? "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  if (!lines.length) return { title: "", paragraphs: [] as string[], items: [] as string[] };
  const [rawTitle, ...rest] = lines;
  const title = rawTitle.replace(/^!+|!+$/g, "").trim();
  const paragraphs: string[] = [];
  const items: string[] = [];
  rest.forEach((line) => {
    if (/^[-•]\s*/.test(line)) { items.push(line.replace(/^[-•]\s*/, "").trim()); return; }
    paragraphs.push(line);
  });
  return { title, paragraphs, items };
}

/* ── Stat Card ────────────────────────────────────────────── */
interface StatCardProps {
  icon: React.ReactNode;
  label: string;
  value?: number | string | React.ReactNode;
  accent?: string;
  delay?: string;
  hero?: boolean;
  warn?: boolean;
  subLabel?: string;
  progress?: { value: number; max: number };
  animated?: boolean;
  numericValue?: number;
  started?: boolean;
}

function StatCard({
  icon, label, value, accent, delay, hero, warn, subLabel, progress, animated, numericValue, started,
}: StatCardProps) {
  const counted = useCountUp(numericValue ?? 0, 900, (animated && started) ? true : false);
  const displayValue = animated && typeof numericValue === "number" ? counted : value;

  const pct = progress ? Math.round((progress.value / Math.max(progress.max, 1)) * 100) : null;

  return (
    <div
      className={[
        "stat-card fi",
        hero ? "stat-card--hero" : "",
        warn ? "stat-card--warn" : "",
      ].filter(Boolean).join(" ")}
      style={{
        "--card-accent": accent,
        transitionDelay: delay,
      } as React.CSSProperties}
    >
      <div className="stat-card-top">
        <div>
          <div className="stat-label">{label}</div>
          <div className="stat-value">{displayValue}</div>
          {subLabel && (
            <div style={{ fontSize: ".75rem", color: "var(--txt-soft)", marginTop: 4 }}>
              {subLabel}
            </div>
          )}
        </div>
        <div className="stat-icon">{icon}</div>
      </div>

      {pct !== null && (
        <div className="stat-progress">
          <div
            className="stat-progress-fill"
            style={{ width: `${pct}%` }}
          />
        </div>
      )}
    </div>
  );
}

/* ── Main Component ───────────────────────────────────────── */
export default function Dashboard() {
  const { user } = useAuth();
  const cardsRef = useRef<HTMLDivElement>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [countersStarted, setCountersStarted] = useState(false);
  const isAdmin = user?.ruolo === "admin";
  const isMaster = user?.ruolo === "master";
  const parsedMessage = parseDashboardMessage(stats?.dashboard_message);

  useEffect(() => {
    api.get("/dashboard/stats").then(r => {
      setStats(r.data);
      setTimeout(() => setCountersStarted(true), 80);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    const els = cardsRef.current?.querySelectorAll(".fi");
    if (!els) return;
    const observer = new IntersectionObserver(
      (entries) => entries.forEach((e) => e.isIntersecting && e.target.classList.add("visible")),
      { threshold: 0.05 }
    );
    els.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [stats]);

  const totalPlexCapacity = stats
    ? stats.plex_users + stats.plex_available_slots
    : 0;

  return (
    <div className="pg" ref={cardsRef}>
      <div className="pg-title">
        Dashboard
      </div>

      {/* ── Comunicazione ── */}
      {stats && (stats.dashboard_message || (stats.monthly_recharges_remaining !== null && stats.monthly_recharges_remaining !== undefined)) && (
        <div
          className="fi visible"
          style={{
            marginTop: 4,
            marginBottom: 24,
            padding: "20px 22px",
            borderRadius: 18,
            border: "1px solid rgba(245,184,75,.28)",
            background:
              "linear-gradient(145deg, rgba(245,184,75,.18), rgba(245,184,75,.06) 55%, rgba(255,255,255,.01))",
            boxShadow: "0 12px 36px rgba(0,0,0,.1)",
          }}
        >
          {stats.dashboard_message && (
            <>
              <div style={{
                display: "flex", alignItems: "center", gap: 7,
                fontSize: ".68rem", fontWeight: 800, textTransform: "uppercase",
                letterSpacing: ".15em", color: "#d18b18", marginBottom: 12,
              }}>
                <Zap size={12} />
                Comunicazione
              </div>
              {parsedMessage.title && (
                <div style={{
                  color: "var(--txt)", fontSize: "1.1rem", fontWeight: 900,
                  lineHeight: 1.3, marginBottom: parsedMessage.paragraphs.length || parsedMessage.items.length ? 10 : 0,
                }}>
                  {parsedMessage.title}
                </div>
              )}
              {parsedMessage.paragraphs.map((p, i) => (
                <div key={i} style={{ color: "var(--txt)", lineHeight: 1.7, fontSize: ".95rem", marginBottom: 8 }}>
                  {p}
                </div>
              ))}
              {parsedMessage.items.length > 0 && (
                <ul style={{ margin: 0, paddingLeft: "1.2rem", color: "var(--txt)", lineHeight: 1.72, fontSize: ".95rem" }}>
                  {parsedMessage.items.map((item) => (
                    <li key={item} style={{ marginBottom: 5 }}>{item}</li>
                  ))}
                </ul>
              )}
            </>
          )}
          {stats.monthly_recharges_remaining !== null && stats.monthly_recharges_remaining !== undefined && (
            <div style={{
              marginTop: stats.dashboard_message ? 14 : 0,
              paddingTop: stats.dashboard_message ? 14 : 0,
              borderTop: stats.dashboard_message ? "1px solid rgba(245,184,75,.2)" : "none",
              display: "flex", alignItems: "baseline", gap: 9, flexWrap: "wrap",
            }}>
              <span style={{ fontSize: ".85rem", color: "var(--txt-soft)", fontWeight: 700 }}>
                Ricariche residue questo mese:
              </span>
              <span style={{ fontSize: "1.3rem", fontWeight: 800, color: "var(--txt)" }}>
                {stats.monthly_recharges_remaining}
              </span>
            </div>
          )}
        </div>
      )}

      {/* ── Account ── */}
      <div className="section-group">
        <SectionLabel dotColor="var(--red)">Account</SectionLabel>
        <div className="cards-grid">
          <StatCard icon={<User size={17} />} label="Username" value={<span style={{ fontSize: "1.3rem" }}>{user?.username}</span>} delay="0s" />
          <StatCard icon={<Coins size={17} />} label="Credito disponibile" value={user?.credito ?? 0} accent="#f5b84b" delay=".06s" />
          <StatCard icon={<Shield size={17} />} label="Ruolo" value={<span style={{ fontSize: "1.3rem", textTransform: "capitalize" }}>{user?.ruolo}</span>} delay=".12s" />
        </div>
      </div>

      {/* ── Skeleton ── */}
      {!stats && (
        <>
          <SkeletonSection count={5} label="streaming" />
          <SkeletonSection count={2} label="scadenze" />
        </>
      )}

      {stats && (
        <>
          {/* ── Utenti Streaming ── */}
          <div className="section-group">
            <SectionLabel dotColor="#6c8ef7">Utenti Streaming</SectionLabel>

            {/* Hero card: totale */}
            <div className="cards-grid" style={{ marginBottom: 10 }}>
              <StatCard
                hero
                icon={<TrendingUp size={20} />}
                label="Totale utenti attivi"
                value={stats.total_users}
                numericValue={stats.total_users}
                animated
                started={countersStarted}
                accent="#6c8ef7"
                delay="0s"
                subLabel={`Emby ${stats.emby_users} · Jellyfin ${stats.jelly_users} · Plex ${stats.plex_users}`}
              />
            </div>

            <div className="cards-grid">
              <StatCard
                icon={<Tv size={17} />}
                label="Utenti Emby"
                numericValue={stats.emby_users}
                animated
                started={countersStarted}
                accent="#f5b84b"
                delay=".04s"
              />
              <StatCard
                icon={<Tv size={17} />}
                label="Utenti Jellyfin"
                numericValue={stats.jelly_users}
                animated
                started={countersStarted}
                accent="#00a4dc"
                delay=".08s"
              />
              <StatCard
                icon={<Tv size={17} />}
                label="Utenti Plex"
                numericValue={stats.plex_users}
                animated
                started={countersStarted}
                accent="#e5a00d"
                delay=".12s"
              />
              <StatCard
                icon={<Tv size={17} />}
                label="Posti liberi Plex"
                numericValue={stats.plex_available_slots}
                animated
                started={countersStarted}
                accent="#3dd5a5"
                delay=".16s"
                subLabel={`su ${totalPlexCapacity} totali`}
                progress={{ value: stats.plex_available_slots, max: totalPlexCapacity }}
              />
            </div>
          </div>

          {/* ── Scadenze ── */}
          <div className="section-group">
            <SectionLabel dotColor="#e74c3c">Scadenze</SectionLabel>
            <div className="cards-grid">
              <StatCard
                icon={<AlertTriangle size={17} />}
                label="Scaduti"
                numericValue={stats.expired}
                animated
                started={countersStarted}
                accent="#e74c3c"
                warn={stats.expired > 0}
                delay="0s"
              />
              <StatCard
                icon={<Clock size={17} />}
                label="Scadono entro 7 giorni"
                numericValue={stats.expiring_7}
                animated
                started={countersStarted}
                accent="#e67e22"
                warn={stats.expiring_7 > 0}
                delay=".06s"
              />
            </div>
          </div>

          {/* ── Reseller ── */}
          {(isAdmin || isMaster) && (
            <div className="section-group">
              <SectionLabel dotColor="#3dd5a5">Reseller</SectionLabel>
              <div className="cards-grid">
                {isAdmin && (
                  <StatCard
                    icon={<Users size={17} />}
                    label="Totale reseller"
                    numericValue={stats.total_resellers}
                    animated
                    started={countersStarted}
                    accent="#3dd5a5"
                    delay="0s"
                  />
                )}
                <StatCard
                  icon={<Users size={17} />}
                  label="Miei reseller"
                  numericValue={stats.my_resellers}
                  animated
                  started={countersStarted}
                  accent="#a78bfa"
                  delay=".06s"
                />
              </div>
            </div>
          )}

          {/* ── Gattino ── */}
          {stats.cat_url && (
            <div className="section-group">
              <SectionLabel dotColor="#f472b6">Gatto del giorno</SectionLabel>
              <div style={{
                borderRadius: 14, overflow: "hidden",
                display: "inline-block", maxWidth: 380,
                border: "1px solid var(--border)",
                boxShadow: "0 8px 28px rgba(0,0,0,.25)",
              }}>
                <img
                  src={stats.cat_url}
                  alt="Gatto casuale"
                  style={{ width: "100%", maxWidth: 380, maxHeight: 280, objectFit: "cover", display: "block" }}
                />
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
