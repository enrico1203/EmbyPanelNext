import { useEffect, useRef, useState } from "react";
import { Coins, User, Shield, Tv, Users, AlertTriangle, Clock, TrendingUp } from "lucide-react";
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
  cat_url: string | null;
}

function SkeletonCard({ delay = "0s" }: { delay?: string }) {
  return (
    <div className="stat-card" style={{ transitionDelay: delay }}>
      <div style={{
        width: 38, height: 38, borderRadius: 10,
        background: "var(--bg-3)", marginBottom: 14,
        animation: "sk-pulse 1.4s ease-in-out infinite",
        animationDelay: delay,
      }} />
      <div style={{
        height: 10, width: "55%", borderRadius: 6,
        background: "var(--bg-3)", marginBottom: 12,
        animation: "sk-pulse 1.4s ease-in-out infinite",
        animationDelay: delay,
      }} />
      <div style={{
        height: 28, width: "40%", borderRadius: 8,
        background: "var(--bg-3)",
        animation: "sk-pulse 1.4s ease-in-out infinite",
        animationDelay: delay,
      }} />
    </div>
  );
}

function SkeletonSection({ count, label }: { count: number; label: string }) {
  return (
    <>
      <div style={{
        height: 10, width: 120, borderRadius: 6,
        background: "var(--bg-3)", margin: "28px 0 16px",
        animation: "sk-pulse 1.4s ease-in-out infinite",
      }} />
      <div className="cards-grid">
        {Array.from({ length: count }).map((_, i) => (
          <SkeletonCard key={`${label}-${i}`} delay={`${i * 0.07}s`} />
        ))}
      </div>
    </>
  );
}

function SectionLabel({ children }: { children: string }) {
  return (
    <div style={{
      fontSize: ".7rem", fontWeight: 700, textTransform: "uppercase",
      letterSpacing: ".13em", color: "var(--txt-soft)",
      margin: "28px 0 10px", paddingBottom: 6,
      borderBottom: "1px solid var(--border)",
    }}>
      {children}
    </div>
  );
}

function StatCard({
  icon, label, value, accent, delay,
}: {
  icon: React.ReactNode;
  label: string;
  value: React.ReactNode;
  accent?: string;
  delay?: string;
}) {
  return (
    <div className="stat-card fi" style={{ transitionDelay: delay }}>
      <div
        className="stat-icon"
        style={accent ? {
          color: accent,
          background: `${accent}22`,
          border: `1px solid ${accent}44`,
        } : {}}
      >
        {icon}
      </div>
      <div className="stat-label">{label}</div>
      <div className="stat-value" style={{ color: "var(--txt)" }}>
        {value}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const cardsRef = useRef<HTMLDivElement>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const isAdmin = user?.ruolo === "admin";
  const isMaster = user?.ruolo === "master";

  useEffect(() => {
    api.get("/dashboard/stats").then(r => setStats(r.data)).catch(() => {});
  }, []);

  useEffect(() => {
    const els = cardsRef.current?.querySelectorAll(".fi");
    if (!els) return;
    const observer = new IntersectionObserver(
      (entries) => entries.forEach((e) => e.isIntersecting && e.target.classList.add("visible")),
      { threshold: 0.1 }
    );
    els.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, [stats]);

  return (
    <div className="pg" ref={cardsRef}>
      <div className="pg-title">Dashboard</div>

      {/* Info utente */}
      <div className="cards-grid">
        <StatCard icon={<User size={18} />} label="Username" value={<span style={{ fontSize: "1.2rem" }}>{user?.username}</span>} delay="0s" />
        <StatCard icon={<Coins size={18} />} label="Credito disponibile" value={user?.credito ?? 0} accent="#f5b84b" delay=".06s" />
        <StatCard icon={<Shield size={18} />} label="Ruolo" value={<span style={{ fontSize: "1.2rem", textTransform: "capitalize" }}>{user?.ruolo}</span>} delay=".12s" />
      </div>

      {!stats && (
        <>
          <SkeletonSection count={5} label="streaming" />
          <SkeletonSection count={2} label="scadenze" />
          <SkeletonSection count={2} label="reseller" />
        </>
      )}

      {stats && (
        <>
          {/* Utenti streaming */}
          <SectionLabel>Utenti Streaming</SectionLabel>
          <div className="cards-grid">
            <StatCard icon={<TrendingUp size={18} />} label="Totale utenti" value={stats.total_users} accent="#6c8ef7" delay=".0s" />
            <StatCard icon={<Tv size={18} />} label="Utenti Emby" value={stats.emby_users} accent="#f5b84b" delay=".06s" />
            <StatCard icon={<Tv size={18} />} label="Utenti Jellyfin" value={stats.jelly_users} accent="#00a4dc" delay=".12s" />
            <StatCard icon={<Tv size={18} />} label="Utenti Plex" value={stats.plex_users} accent="#e5a00d" delay=".18s" />
            <StatCard icon={<Tv size={18} />} label="Posti disponibili Plex" value={stats.plex_available_slots} accent="#f59e0b" delay=".24s" />
          </div>

          {/* Scadenze */}
          <SectionLabel>Scadenze</SectionLabel>
          <div className="cards-grid">
            <StatCard icon={<AlertTriangle size={18} />} label="Scaduti" value={stats.expired} accent="#e74c3c" delay=".0s" />
            <StatCard icon={<Clock size={18} />} label="Scadono entro 7 giorni" value={stats.expiring_7} accent="#e67e22" delay=".06s" />
          </div>

          {/* Reseller */}
          {(isAdmin || isMaster) && (
            <>
              <SectionLabel>Reseller</SectionLabel>
              <div className="cards-grid">
                {isAdmin && (
                  <StatCard icon={<Users size={18} />} label="Totale reseller" value={stats.total_resellers} accent="#3dd5a5" delay=".0s" />
                )}
                <StatCard icon={<Users size={18} />} label="Miei reseller" value={stats.my_resellers} accent="#a78bfa" delay=".06s" />
              </div>
            </>
          )}

          {/* Gattino */}
          {stats.cat_url && (
            <>
              <SectionLabel>Gatto del giorno</SectionLabel>
              <div style={{
                background: "var(--bg-2)", border: "1px solid var(--border)",
                borderRadius: 18, overflow: "hidden", display: "inline-block", maxWidth: 380,
              }}>
                <img
                  src={stats.cat_url}
                  alt="Gatto casuale"
                  style={{ width: "100%", maxWidth: 380, maxHeight: 280, objectFit: "cover", display: "block" }}
                />
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
