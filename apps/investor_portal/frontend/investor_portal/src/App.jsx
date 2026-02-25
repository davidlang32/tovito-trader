import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { Loader2, AlertTriangle, LogIn, Clock } from 'lucide-react';
import { AuthProvider, useAuth } from './context/AuthContext';
import Layout from './components/Layout';
import LandingPage from './pages/LandingPage';
import DashboardPage from './pages/DashboardPage';
import PerformancePage from './pages/PerformancePage';
import PortfolioPage from './pages/PortfolioPage';
import ActivityPage from './pages/ActivityPage';
import ReportsPage from './pages/ReportsPage';
import SettingsPage from './pages/SettingsPage';
import TutorialsPage from './pages/TutorialsPage';
import FundPreviewPage from './pages/FundPreviewPage';
import {
  LoginPage,
  AccountSetupPage,
  VerifyPage,
  ForgotPasswordPage,
  ResetPasswordPage
} from './pages/LoginPage';

// ============================================================
// SESSION WARNING BANNER
// ============================================================

const SessionWarningBanner = () => {
  const { sessionWarning, extendSession } = useAuth();
  if (!sessionWarning) return null;

  return (
    <div className="fixed top-0 left-0 right-0 z-[100] bg-amber-500 text-white px-4 py-3 shadow-lg animate-in fade-in">
      <div className="max-w-4xl mx-auto flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <Clock className="w-5 h-5 flex-shrink-0" />
          <p className="text-sm font-medium">
            Your session is about to expire. Would you like to stay signed in?
          </p>
        </div>
        <button
          onClick={extendSession}
          className="flex-shrink-0 px-4 py-1.5 bg-white text-amber-700 rounded-lg text-sm font-semibold hover:bg-amber-50 transition shadow-sm"
        >
          Stay Signed In
        </button>
      </div>
    </div>
  );
};

// ============================================================
// SESSION EXPIRED PAGE
// ============================================================

const SessionExpiredPage = () => {
  const { dismissExpired } = useAuth();
  const navigate = useNavigate();

  const handleLogin = () => {
    dismissExpired();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-8 text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-amber-100 rounded-full mb-5">
          <AlertTriangle className="w-8 h-8 text-amber-600" />
        </div>
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Session Expired</h1>
        <p className="text-gray-500 mb-6">
          Your session has ended for security purposes. Please sign in again to continue.
        </p>
        <button
          onClick={handleLogin}
          className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-medium py-3 rounded-xl transition flex items-center justify-center gap-2"
        >
          <LogIn className="w-5 h-5" />
          Sign In Again
        </button>
        <p className="text-xs text-gray-400 mt-4">
          Sessions expire after a period of inactivity to keep your account safe.
        </p>
      </div>
    </div>
  );
};

// ============================================================
// PROTECTED ROUTE
// ============================================================

const ProtectedRoute = ({ children }) => {
  const { user, loading, sessionExpired } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  if (sessionExpired) {
    return <SessionExpiredPage />;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return children;
};

// ============================================================
// PUBLIC ROUTE (redirect to dashboard if already logged in)
// ============================================================

const PublicRoute = ({ children }) => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  if (user) {
    return <Navigate to="/dashboard" replace />;
  }

  return children;
};

// ============================================================
// APP
// ============================================================

const App = () => {
  return (
    <BrowserRouter>
      <AuthProvider>
        <SessionWarningBanner />
        <Routes>
          {/* Public landing page — visible to everyone */}
          <Route path="/" element={<LandingPage />} />

          {/* Prospect fund preview — token-gated, no auth required */}
          <Route path="/fund-preview" element={<FundPreviewPage />} />

          {/* Auth pages — no sidebar, redirect if already logged in */}
          <Route path="/login" element={<PublicRoute><LoginPage /></PublicRoute>} />
          <Route path="/setup" element={<PublicRoute><AccountSetupPage /></PublicRoute>} />
          <Route path="/verify" element={<VerifyPage />} />
          <Route path="/forgot-password" element={<PublicRoute><ForgotPasswordPage /></PublicRoute>} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />

          {/* Authenticated pages — with sidebar layout */}
          <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="performance" element={<PerformancePage />} />
            <Route path="portfolio" element={<PortfolioPage />} />
            <Route path="activity" element={<ActivityPage />} />
            <Route path="reports" element={<ReportsPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="help" element={<TutorialsPage />} />
          </Route>

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
};

export default App;
