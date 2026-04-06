import { useEffect, useRef } from "react";
import { Coins, User, Shield } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";

export default function Dashboard() {
  const { user } = useAuth();
  const cardsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const els = cardsRef.current?.querySelectorAll(".fi");
    if (!els) return;
    const observer = new IntersectionObserver(
      (entries) => entries.forEach((e) => e.isIntersecting && e.target.classList.add("visible")),
      { threshold: 0.1 }
    );
    els.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);

  return (
    <div className="pg">
      <div className="pg-title">
        Dashboard
      </div>

      <div className="cards-grid" ref={cardsRef}>
        <div className="stat-card fi">
          <div className="stat-icon"><User size={18} /></div>
          <div className="stat-label">Username</div>
          <div className="stat-value" style={{ fontSize: "1.2rem" }}>
            {user?.username}
          </div>
        </div>

        <div className="stat-card fi" style={{ transitionDelay: ".08s" }}>
          <div className="stat-icon"><Coins size={18} /></div>
          <div className="stat-label">Credito disponibile</div>
          <div className="stat-value">{user?.credito ?? 0}</div>
        </div>

        <div className="stat-card fi" style={{ transitionDelay: ".16s" }}>
          <div className="stat-icon"><Shield size={18} /></div>
          <div className="stat-label">Ruolo</div>
          <div
            className="stat-value"
            style={{ fontSize: "1.2rem", textTransform: "capitalize" }}
          >
            {user?.ruolo}
          </div>
        </div>
      </div>
    </div>
  );
}
