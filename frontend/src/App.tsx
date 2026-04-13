import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ThemeProvider } from "./contexts/ThemeContext";
import { AuthProvider } from "./contexts/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Regole from "./pages/Regole";
import PublicPrezzi from "./pages/PublicPrezzi";
import Settings from "./pages/Settings";
import ManageResellers from "./pages/ManageResellers";
import MyResellers from "./pages/MyResellers";
import ResellerDetail from "./pages/ResellerDetail";
import Prezzi from "./pages/Prezzi";
import Movimenti from "./pages/Movimenti";
import Gestione from "./pages/Gestione";
import GestioneUtenti from "./pages/GestioneUtenti";
import Scheduler from "./pages/Scheduler";
import TestApi from "./pages/TestApi";
import Inconsistenze from "./pages/Inconsistenze";
import Funzioni from "./pages/Funzioni";
import ListaEmby from "./pages/ListaEmby";
import ListaJelly from "./pages/ListaJelly";
import ListaPlex from "./pages/ListaPlex";
import EmbyUserDetail from "./pages/EmbyUserDetail";
import JellyUserDetail from "./pages/JellyUserDetail";
import PlexUserDetail from "./pages/PlexUserDetail";
import CreateEmbyUser from "./pages/CreateEmbyUser";
import CreateJellyUser from "./pages/CreateJellyUser";
import CreatePlexUser from "./pages/CreatePlexUser";
import ImpostaMessaggio from "./pages/ImpostaMessaggio";

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route element={<ProtectedRoute />}>
              <Route element={<Layout />}>
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/regole" element={<Regole />} />
                <Route path="/prezzi" element={<PublicPrezzi />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="/admin/resellers" element={<ManageResellers />} />
                <Route path="/admin/gestione" element={<Gestione />} />
                <Route path="/admin/gestione-utenti" element={<GestioneUtenti />} />
                <Route path="/admin/scheduler" element={<Scheduler />} />
                <Route path="/admin/testapi" element={<TestApi />} />
                <Route path="/admin/inconsistenze" element={<Inconsistenze />} />
                <Route path="/admin/funzioni" element={<Funzioni />} />
                <Route path="/crea/emby" element={<CreateEmbyUser />} />
                <Route path="/crea/jellyfin" element={<CreateJellyUser />} />
                <Route path="/crea/plex" element={<CreatePlexUser />} />
                <Route path="/resellers" element={<MyResellers />} />
                <Route path="/resellers/messaggio" element={<ImpostaMessaggio />} />
                <Route path="/resellers/:id" element={<ResellerDetail />} />
                <Route path="/admin/prezzi" element={<Prezzi />} />
                <Route path="/movimenti" element={<Movimenti />} />
                <Route path="/lista/emby" element={<ListaEmby />} />
                <Route path="/lista/emby/:invito" element={<EmbyUserDetail />} />
                <Route path="/lista/jelly" element={<ListaJelly />} />
                <Route path="/lista/jelly/:invito" element={<JellyUserDetail />} />
                <Route path="/lista/plex" element={<ListaPlex />} />
                <Route path="/lista/plex/:invito" element={<PlexUserDetail />} />
              </Route>
            </Route>
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}
