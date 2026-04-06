import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";

export default function ProtectedRoute() {
  const { token, loading } = useAuth();

  if (loading) {
    return (
      <div className="loading-container">
        <div className="spinner" />
      </div>
    );
  }

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
