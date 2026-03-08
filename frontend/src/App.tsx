import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './stores/authStore';
import ErrorBoundary from './components/ErrorBoundary';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Users from './pages/Users';
import Servers from './pages/Servers';
import UsersOnServers from './pages/UsersOnServers';
import Subscriptions from './pages/Subscriptions';
import SubscriptionPlans from './pages/SubscriptionPlans';
import Traffic from './pages/Traffic';
import ImportConfig from './pages/ImportConfig';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />;
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Navigate to="/dashboard" replace />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <ErrorBoundary context="Dashboard"><Dashboard /></ErrorBoundary>
            </ProtectedRoute>
          }
        />
        <Route
          path="/users"
          element={
            <ProtectedRoute>
              <ErrorBoundary context="Users"><Users /></ErrorBoundary>
            </ProtectedRoute>
          }
        />
        <Route
          path="/servers"
          element={
            <ProtectedRoute>
              <ErrorBoundary context="Servers"><Servers /></ErrorBoundary>
            </ProtectedRoute>
          }
        />
        <Route
          path="/users-on-servers"
          element={
            <ProtectedRoute>
              <ErrorBoundary context="UsersOnServers"><UsersOnServers /></ErrorBoundary>
            </ProtectedRoute>
          }
        />
        <Route
          path="/subscriptions"
          element={
            <ProtectedRoute>
              <ErrorBoundary context="Subscriptions"><Subscriptions /></ErrorBoundary>
            </ProtectedRoute>
          }
        />
        <Route
          path="/subscription-plans"
          element={
            <ProtectedRoute>
              <ErrorBoundary context="SubscriptionPlans"><SubscriptionPlans /></ErrorBoundary>
            </ProtectedRoute>
          }
        />
        <Route
          path="/traffic"
          element={
            <ProtectedRoute>
              <ErrorBoundary context="Traffic"><Traffic /></ErrorBoundary>
            </ProtectedRoute>
          }
        />
        <Route
          path="/import"
          element={
            <ProtectedRoute>
              <ErrorBoundary context="ImportConfig"><ImportConfig /></ErrorBoundary>
            </ProtectedRoute>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}

export default App
