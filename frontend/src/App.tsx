import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ThemeProvider } from "./contexts/ThemeContext";
import { AuthProvider } from "./contexts/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Settings from "./pages/Settings";
import ManageResellers from "./pages/ManageResellers";
import MyResellers from "./pages/MyResellers";
import ResellerDetail from "./pages/ResellerDetail";
import Prezzi from "./pages/Prezzi";
import Movimenti from "./pages/Movimenti";
import Gestione from "./pages/Gestione";

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
                <Route path="/settings" element={<Settings />} />
                <Route path="/admin/resellers" element={<ManageResellers />} />
                <Route path="/admin/gestione" element={<Gestione />} />
                <Route path="/resellers" element={<MyResellers />} />
                <Route path="/resellers/:id" element={<ResellerDetail />} />
                <Route path="/admin/prezzi" element={<Prezzi />} />
                <Route path="/movimenti" element={<Movimenti />} />
              </Route>
            </Route>
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}
