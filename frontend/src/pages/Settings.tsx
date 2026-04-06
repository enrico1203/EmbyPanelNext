import { Wrench } from "lucide-react";

export default function Settings() {
  return (
    <div className="pg">
      <div className="pg-title">Impostazioni</div>
      <div className="wip-wrap">
        <div className="wip-icon"><Wrench size={26} /></div>
        <h2>Work in Progress</h2>
        <p>Questa sezione è in fase di sviluppo. Torna presto!</p>
      </div>
    </div>
  );
}
