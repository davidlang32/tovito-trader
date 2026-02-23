import { useState, useEffect, useCallback, useRef, createContext, useContext } from 'react';
import {
  TrendingUp, TrendingDown, DollarSign, PieChart,
  LogOut, RefreshCw, ArrowUpRight, ArrowDownRight,
  User, FileText, Clock, AlertCircle,
  Eye, EyeOff, Loader2, ArrowLeft, CheckCircle2, Mail,
  HelpCircle, Play, BookOpen, BarChart3, Download, Calendar,
  Shield, Activity, Table2, ChevronRight
} from 'lucide-react';
import { createChart } from 'lightweight-charts';

// ============================================================
// CONFIGURATION
// ============================================================

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// ============================================================
// AUTH CONTEXT
// ============================================================

const AuthContext = createContext(null);

const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
};

const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [tokens, setTokens] = useState(() => {
    const saved = localStorage.getItem('tokens');
    return saved ? JSON.parse(saved) : null;
  });
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    setUser(null);
    setTokens(null);
    localStorage.removeItem('tokens');
  }, []);

  const fetchUser = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/auth/me`, {
        headers: { Authorization: `Bearer ${tokens.access_token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setUser(data);
      } else {
        logout();
      }
    } catch (err) {
      console.error('Failed to fetch user:', err);
    } finally {
      setLoading(false);
    }
  }, [tokens, logout]);

  useEffect(() => {
    if (tokens?.access_token) {
      fetchUser();
    } else {
      setLoading(false);
    }
  }, [tokens, fetchUser]);

  const login = async (email, password) => {
    const res = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || 'Login failed');
    }

    const newTokens = {
      access_token: data.access_token,
      refresh_token: data.refresh_token
    };

    setTokens(newTokens);
    localStorage.setItem('tokens', JSON.stringify(newTokens));

    setUser({
      name: data.investor_name,
      email: email
    });

    return data;
  };

  const loginWithTokens = useCallback((tokenData) => {
    const newTokens = {
      access_token: tokenData.access_token,
      refresh_token: tokenData.refresh_token
    };
    setTokens(newTokens);
    localStorage.setItem('tokens', JSON.stringify(newTokens));
    // Set initial user from token response; fetchUser useEffect will
    // fire when tokens change and populate the full user object from /auth/me
    setUser({ name: tokenData.investor_name, email: '' });
  }, []);

  const getAuthHeaders = useCallback(() => ({
    Authorization: `Bearer ${tokens?.access_token}`,
    'Content-Type': 'application/json'
  }), [tokens]);

  return (
    <AuthContext.Provider value={{ user, tokens, loading, login, loginWithTokens, logout, getAuthHeaders }}>
      {children}
    </AuthContext.Provider>
  );
};

// ============================================================
// API HOOKS
// ============================================================

const useApi = (endpoint, options = {}) => {
  const { getAuthHeaders } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}${endpoint}`, {
        headers: getAuthHeaders(),
        ...options
      });
      if (!res.ok) throw new Error('Failed to fetch');
      const json = await res.json();
      setData(json);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [endpoint, getAuthHeaders, options]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refetch: fetchData };
};

// ============================================================
// COMPONENTS: LOGIN
// ============================================================

const LoginPage = ({ onForgotPassword, onAccountSetup }) => {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await login(email, password);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-900 via-blue-800 to-indigo-900 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-8">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-100 rounded-full mb-4">
            <TrendingUp className="w-8 h-8 text-blue-600" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Tovito Trader</h1>
          <p className="text-gray-500 mt-1">Investor Portal</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center gap-2">
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
              <span className="text-sm">{error}</span>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
              placeholder="you@example.com"
              required
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="block text-sm font-medium text-gray-700">Password</label>
              <button
                type="button"
                onClick={onForgotPassword}
                className="text-sm text-blue-600 hover:text-blue-800 transition"
              >
                Forgot password?
              </button>
            </div>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition pr-12"
                placeholder="••••••••"
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 rounded-lg transition flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {loading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Signing in...
              </>
            ) : (
              'Sign In'
            )}
          </button>
        </form>

        <p className="text-center text-sm text-gray-500 mt-6">
          First time?{' '}
          <button
            type="button"
            onClick={onAccountSetup}
            className="text-blue-600 hover:text-blue-800 transition font-medium"
          >
            Set up your account
          </button>
        </p>
      </div>
    </div>
  );
};

// ============================================================
// COMPONENTS: ACCOUNT SETUP (First-Time Registration)
// ============================================================

const AccountSetupPage = ({ onBackToLogin }) => {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE_URL}/auth/initiate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email })
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || 'Something went wrong');
      }

      setSubmitted(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const isAlreadySetUp = error.toLowerCase().includes('already set up');

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-900 via-blue-800 to-indigo-900 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-8">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-100 rounded-full mb-4">
            <Shield className="w-8 h-8 text-blue-600" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Set Up Your Account</h1>
          <p className="text-gray-500 mt-1">
            {submitted
              ? "Check your email"
              : "Enter the email your fund administrator registered for you"}
          </p>
        </div>

        {submitted ? (
          <div className="space-y-5">
            <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
                <span className="text-sm">
                  If that email is registered, you'll receive a setup link. The link expires in 24 hours.
                </span>
              </div>
              <p className="text-sm text-green-600 mt-2">
                {"Didn't receive an email? Contact us at "}
                <a href="mailto:support@tovitotrader.com" className="font-medium underline">
                  support@tovitotrader.com
                </a>
              </p>
            </div>
            <button
              onClick={onBackToLogin}
              className="w-full bg-gray-100 hover:bg-gray-200 text-gray-700 font-medium py-3 rounded-lg transition flex items-center justify-center gap-2"
            >
              <ArrowLeft className="w-5 h-5" />
              Back to Sign In
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
                <div className="flex items-center gap-2">
                  <AlertCircle className="w-5 h-5 flex-shrink-0" />
                  <span className="text-sm">{error}</span>
                </div>
                {isAlreadySetUp && (
                  <button
                    type="button"
                    onClick={onBackToLogin}
                    className="mt-2 text-sm text-blue-600 hover:text-blue-800 underline"
                  >
                    Go to Sign In
                  </button>
                )}
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                placeholder="you@example.com"
                required
                autoFocus
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 rounded-lg transition flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Sending...
                </>
              ) : (
                'Send Setup Link'
              )}
            </button>

            <button
              type="button"
              onClick={onBackToLogin}
              className="w-full text-gray-500 hover:text-gray-700 text-sm font-medium py-2 transition flex items-center justify-center gap-1"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to Sign In
            </button>
          </form>
        )}
      </div>
    </div>
  );
};

// ============================================================
// COMPONENTS: FORGOT PASSWORD
// ============================================================

const ForgotPasswordPage = ({ onBackToLogin }) => {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE_URL}/auth/forgot-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email })
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || 'Something went wrong');
      }

      setSubmitted(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-900 via-blue-800 to-indigo-900 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-8">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-100 rounded-full mb-4">
            <Mail className="w-8 h-8 text-blue-600" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Reset Password</h1>
          <p className="text-gray-500 mt-1">
            {submitted
              ? "Check your email"
              : "Enter your email to receive a reset link"}
          </p>
        </div>

        {submitted ? (
          <div className="space-y-5">
            <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
              <span className="text-sm">
                If that email is registered, you'll receive a password reset link. The link expires in 1 hour.
              </span>
            </div>
            <button
              onClick={onBackToLogin}
              className="w-full bg-gray-100 hover:bg-gray-200 text-gray-700 font-medium py-3 rounded-lg transition flex items-center justify-center gap-2"
            >
              <ArrowLeft className="w-5 h-5" />
              Back to Sign In
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center gap-2">
                <AlertCircle className="w-5 h-5 flex-shrink-0" />
                <span className="text-sm">{error}</span>
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                placeholder="you@example.com"
                required
                autoFocus
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 rounded-lg transition flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Sending...
                </>
              ) : (
                'Send Reset Link'
              )}
            </button>

            <button
              type="button"
              onClick={onBackToLogin}
              className="w-full text-gray-500 hover:text-gray-700 text-sm font-medium py-2 transition flex items-center justify-center gap-1"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to Sign In
            </button>
          </form>
        )}
      </div>
    </div>
  );
};

// ============================================================
// COMPONENTS: VERIFY / FIRST-TIME PASSWORD SETUP
// ============================================================

const VerifyPage = ({ token, onBackToLogin, onRequestNewSetup }) => {
  const { loginWithTokens } = useAuth();
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }

    setLoading(true);

    try {
      const res = await fetch(`${API_BASE_URL}/auth/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, password })
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || 'Failed to set up account');
      }

      setSuccess(true);

      // Auto-login: store tokens and set user context
      // Clean URL to remove the token parameter
      window.history.replaceState({}, '', '/');
      loginWithTokens(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const isExpiredOrInvalid = error.toLowerCase().includes('expired') || error.toLowerCase().includes('invalid');

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-900 via-blue-800 to-indigo-900 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-8">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-100 rounded-full mb-4">
            {success
              ? <CheckCircle2 className="w-8 h-8 text-green-600" />
              : <Shield className="w-8 h-8 text-blue-600" />
            }
          </div>
          <h1 className="text-2xl font-bold text-gray-900">
            {success ? 'Account Created' : 'Welcome to Tovito Trader'}
          </h1>
          <p className="text-gray-500 mt-1">
            {success
              ? 'Redirecting to your dashboard...'
              : 'Create your password to get started'}
          </p>
        </div>

        {success ? (
          <div className="space-y-5">
            <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
              <span className="text-sm">Account set up successfully. Loading your dashboard...</span>
            </div>
            <div className="flex justify-center">
              <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
                <div className="flex items-center gap-2">
                  <AlertCircle className="w-5 h-5 flex-shrink-0" />
                  <span className="text-sm">{error}</span>
                </div>
                {isExpiredOrInvalid && (
                  <button
                    type="button"
                    onClick={onRequestNewSetup}
                    className="mt-2 text-sm text-blue-600 hover:text-blue-800 underline"
                  >
                    Request a new setup link
                  </button>
                )}
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition pr-12"
                  placeholder="Create a secure password"
                  required
                  minLength={8}
                  autoFocus
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                >
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
              <p className="text-xs text-gray-400 mt-1">
                Min 8 characters with uppercase, lowercase, number, and special character
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Confirm Password</label>
              <div className="relative">
                <input
                  type={showConfirm ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition pr-12"
                  placeholder="Confirm your password"
                  required
                  minLength={8}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirm(!showConfirm)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                >
                  {showConfirm ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 rounded-lg transition flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Setting up...
                </>
              ) : (
                'Create Account'
              )}
            </button>

            <button
              type="button"
              onClick={onBackToLogin}
              className="w-full text-gray-500 hover:text-gray-700 text-sm font-medium py-2 transition flex items-center justify-center gap-1"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to Sign In
            </button>
          </form>
        )}
      </div>
    </div>
  );
};

// ============================================================
// COMPONENTS: RESET PASSWORD
// ============================================================

const ResetPasswordPage = ({ token, onBackToLogin, onRequestNewLink }) => {
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }

    setLoading(true);

    try {
      const res = await fetch(`${API_BASE_URL}/auth/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, new_password: password })
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || 'Failed to reset password');
      }

      setSuccess(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const isExpiredOrInvalid = error.toLowerCase().includes('expired') || error.toLowerCase().includes('invalid');

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-900 via-blue-800 to-indigo-900 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-8">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-100 rounded-full mb-4">
            {success
              ? <CheckCircle2 className="w-8 h-8 text-green-600" />
              : <TrendingUp className="w-8 h-8 text-blue-600" />
            }
          </div>
          <h1 className="text-2xl font-bold text-gray-900">
            {success ? 'Password Reset' : 'Set New Password'}
          </h1>
          <p className="text-gray-500 mt-1">
            {success
              ? 'Your password has been updated'
              : 'Enter your new password below'}
          </p>
        </div>

        {success ? (
          <div className="space-y-5">
            <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
              <span className="text-sm">Password reset successful. You can now sign in with your new password.</span>
            </div>
            <button
              onClick={onBackToLogin}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 rounded-lg transition flex items-center justify-center gap-2"
            >
              Sign In
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
                <div className="flex items-center gap-2">
                  <AlertCircle className="w-5 h-5 flex-shrink-0" />
                  <span className="text-sm">{error}</span>
                </div>
                {isExpiredOrInvalid && (
                  <button
                    type="button"
                    onClick={onRequestNewLink}
                    className="mt-2 text-sm text-blue-600 hover:text-blue-800 underline"
                  >
                    Request a new reset link
                  </button>
                )}
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">New Password</label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition pr-12"
                  placeholder="••••••••"
                  required
                  minLength={8}
                  autoFocus
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                >
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
              <p className="text-xs text-gray-400 mt-1">
                Min 8 characters with uppercase, lowercase, number, and special character
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Confirm Password</label>
              <div className="relative">
                <input
                  type={showConfirm ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition pr-12"
                  placeholder="••••••••"
                  required
                  minLength={8}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirm(!showConfirm)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                >
                  {showConfirm ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 rounded-lg transition flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Resetting...
                </>
              ) : (
                'Reset Password'
              )}
            </button>

            <button
              type="button"
              onClick={onBackToLogin}
              className="w-full text-gray-500 hover:text-gray-700 text-sm font-medium py-2 transition flex items-center justify-center gap-1"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to Sign In
            </button>
          </form>
        )}
      </div>
    </div>
  );
};

// ============================================================
// COMPONENTS: DASHBOARD
// ============================================================

const StatCard = ({ title, value, subtitle, icon: Icon, trend, trendValue }) => (
  <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
    <div className="flex items-start justify-between">
      <div>
        <p className="text-sm text-gray-500 font-medium">{title}</p>
        <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
        {subtitle && <p className="text-sm text-gray-500 mt-1">{subtitle}</p>}
      </div>
      <div className={`p-3 rounded-lg ${trend === 'up' ? 'bg-green-100' : trend === 'down' ? 'bg-red-100' : 'bg-gray-100'}`}>
        <Icon className={`w-6 h-6 ${trend === 'up' ? 'text-green-600' : trend === 'down' ? 'text-red-600' : 'text-gray-600'}`} />
      </div>
    </div>
    {trendValue !== undefined && (
      <div className={`flex items-center gap-1 mt-3 text-sm ${trendValue >= 0 ? 'text-green-600' : 'text-red-600'}`}>
        {trendValue >= 0 ? <ArrowUpRight className="w-4 h-4" /> : <ArrowDownRight className="w-4 h-4" />}
        <span>{trendValue >= 0 ? '+' : ''}{trendValue.toFixed(2)}%</span>
        <span className="text-gray-500 ml-1">total return</span>
      </div>
    )}
  </div>
);

const TransactionRow = ({ transaction }) => {
  const isContribution = transaction.type === 'Contribution';
  return (
    <div className="flex items-center justify-between py-3 border-b border-gray-100 last:border-0">
      <div className="flex items-center gap-3">
        <div className={`p-2 rounded-lg ${isContribution ? 'bg-green-100' : 'bg-red-100'}`}>
          {isContribution ? 
            <ArrowDownRight className="w-4 h-4 text-green-600" /> : 
            <ArrowUpRight className="w-4 h-4 text-red-600" />
          }
        </div>
        <div>
          <p className="font-medium text-gray-900">{transaction.type}</p>
          <p className="text-sm text-gray-500">{transaction.date}</p>
        </div>
      </div>
      <div className="text-right">
        <p className={`font-semibold ${isContribution ? 'text-green-600' : 'text-red-600'}`}>
          {isContribution ? '+' : '-'}${Math.abs(transaction.amount).toLocaleString('en-US', { minimumFractionDigits: 2 })}
        </p>
        <p className="text-sm text-gray-500">{transaction.shares.toFixed(4)} shares</p>
      </div>
    </div>
  );
};

// ============================================================
// TUTORIALS PAGE
// ============================================================

import { TUTORIALS } from './tutorialData.js';

const CATEGORY_INFO = {
  'all': { label: 'All Tutorials', icon: BookOpen },
  'getting-started': { label: 'Getting Started', icon: Play },
  'admin': { label: 'Admin Operations', icon: FileText },
  'launching': { label: 'Launching Apps', icon: ArrowUpRight },
};

const TutorialDetail = ({ tutorial, onBack }) => {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="font-bold text-gray-900">{tutorial.title}</h1>
            <p className="text-xs text-gray-500">{tutorial.duration} min</p>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-8">
        {tutorial.videoUrl && (
          <div className="bg-black rounded-xl overflow-hidden mb-8 shadow-lg">
            <video
              controls
              preload="metadata"
              className="w-full"
              style={{ maxHeight: '480px' }}
            >
              <source src={tutorial.videoUrl} type="video/mp4" />
              Your browser does not support video playback.
            </video>
          </div>
        )}

        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-2">About This Tutorial</h2>
          <p className="text-gray-600">{tutorial.description}</p>
        </div>

        {tutorial.guideUrl && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-gray-900">Step-by-Step Guide</h3>
                <p className="text-sm text-gray-500 mt-1">
                  View the screenshot guide with detailed instructions for each step.
                </p>
              </div>
              <a
                href={tutorial.guideUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition text-sm font-medium flex items-center gap-2"
              >
                <BookOpen className="w-4 h-4" />
                Open Guide
              </a>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

const TutorialsPage = ({ onBack }) => {
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedTutorial, setSelectedTutorial] = useState(null);

  if (selectedTutorial) {
    return <TutorialDetail tutorial={selectedTutorial} onBack={() => setSelectedTutorial(null)} />;
  }

  const filtered = selectedCategory === 'all'
    ? TUTORIALS
    : TUTORIALS.filter(t => t.category === selectedCategory);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <button
                onClick={onBack}
                className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <div className="p-2 bg-blue-100 rounded-lg">
                <HelpCircle className="w-6 h-6 text-blue-600" />
              </div>
              <div>
                <h1 className="font-bold text-gray-900">Help & Tutorials</h1>
                <p className="text-xs text-gray-500">Learn how to use the platform</p>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex gap-2 mb-8 flex-wrap">
          {Object.entries(CATEGORY_INFO).map(([key, { label }]) => (
            <button
              key={key}
              onClick={() => setSelectedCategory(key)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                selectedCategory === key
                  ? 'bg-blue-600 text-white'
                  : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filtered.map(tutorial => (
            <button
              key={tutorial.id}
              onClick={() => setSelectedTutorial(tutorial)}
              className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 text-left hover:shadow-md hover:border-gray-200 transition group"
            >
              <div className="bg-gray-100 rounded-lg h-36 mb-4 flex items-center justify-center group-hover:bg-blue-50 transition">
                {tutorial.videoUrl ? (
                  <Play className="w-10 h-10 text-gray-300 group-hover:text-blue-400 transition" />
                ) : (
                  <BookOpen className="w-10 h-10 text-gray-300 group-hover:text-blue-400 transition" />
                )}
              </div>

              <div className="flex items-start justify-between gap-2">
                <h3 className="font-semibold text-gray-900 group-hover:text-blue-600 transition">
                  {tutorial.title}
                </h3>
                <span className="text-xs text-gray-400 whitespace-nowrap">{tutorial.duration}</span>
              </div>
              <p className="text-sm text-gray-500 mt-1 line-clamp-2">{tutorial.description}</p>

              <div className="mt-3 flex items-center gap-2">
                <span className={`text-xs px-2 py-0.5 rounded-full ${
                  tutorial.category === 'getting-started' ? 'bg-green-100 text-green-700' :
                  tutorial.category === 'admin' ? 'bg-purple-100 text-purple-700' :
                  'bg-orange-100 text-orange-700'
                }`}>
                  {CATEGORY_INFO[tutorial.category]?.label || tutorial.category}
                </span>
                {tutorial.videoUrl && (
                  <span className="text-xs text-gray-400 flex items-center gap-1">
                    <Play className="w-3 h-3" /> Video
                  </span>
                )}
                {tutorial.guideUrl && (
                  <span className="text-xs text-gray-400 flex items-center gap-1">
                    <BookOpen className="w-3 h-3" /> Guide
                  </span>
                )}
              </div>
            </button>
          ))}
        </div>

        {filtered.length === 0 && (
          <div className="text-center py-12 text-gray-500">
            <HelpCircle className="w-12 h-12 mx-auto mb-3 text-gray-300" />
            <p>No tutorials in this category yet.</p>
          </div>
        )}
      </main>
    </div>
  );
};

// ============================================================
// INTERACTIVE BENCHMARK CHART (TradingView Lightweight Charts)
// ============================================================

const RANGE_OPTIONS = [
  { label: '30D', value: 30 },
  { label: '90D', value: 90 },
  { label: '6M', value: 180 },
  { label: '1Y', value: 365 },
  { label: 'All', value: 730 },
];

const BENCHMARK_COLORS = {
  'SPY':     { line: '#2d8a4e', label: 'S&P 500 (SPY)' },
  'QQQ':     { line: '#8e44ad', label: 'Nasdaq 100 (QQQ)' },
  'BTC-USD': { line: '#e67e22', label: 'Bitcoin (BTC)' },
};

const FUND_COLOR = '#1e3a5f';
const MOUNTAIN_TOP = 'rgba(74, 144, 217, 0.4)';
const MOUNTAIN_BOTTOM = 'rgba(74, 144, 217, 0.0)';
const MOUNTAIN_LINE = '#4a90d9';

const BenchmarkChart = () => {
  const { getAuthHeaders } = useAuth();
  const [days, setDays] = useState(90);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [retryCount, setRetryCount] = useState(0);
  const [tooltipData, setTooltipData] = useState(null);
  const [latestData, setLatestData] = useState(null);

  const chartContainerRef = useRef(null);
  const chartRef = useRef(null);
  const seriesMapRef = useRef({});
  const tooltipRef = useRef(null);

  useEffect(() => {
    let cancelled = false;

    const fetchAndRender = async () => {
      setLoading(true);
      setError(false);
      setTooltipData(null);

      try {
        const res = await fetch(`${API_BASE_URL}/nav/benchmark-data?days=${days}`, {
          headers: getAuthHeaders(),
        });
        if (!res.ok) throw new Error('Fetch failed');
        const data = await res.json();
        if (cancelled) return;

        // Store latest values for the legend
        const latest = {
          nav: data.fund.length ? data.fund[data.fund.length - 1].nav_per_share : null,
          fund_pct: data.fund.length ? data.fund[data.fund.length - 1].pct_change : null,
        };
        Object.entries(data.benchmarks).forEach(([tk, series]) => {
          latest[tk] = series.length ? series[series.length - 1].pct_change : null;
        });
        setLatestData(latest);

        renderChart(data);
      } catch {
        if (!cancelled) setError(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchAndRender();

    return () => {
      cancelled = true;
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
      seriesMapRef.current = {};
    };
  }, [days, retryCount, getAuthHeaders]);

  const renderChart = (data) => {
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }
    seriesMapRef.current = {};

    const container = chartContainerRef.current;
    if (!container) return;

    const chart = createChart(container, {
      width: container.clientWidth,
      height: 380,
      layout: {
        background: { color: '#fafafa' },
        textColor: '#555',
        fontFamily: 'system-ui, -apple-system, sans-serif',
        fontSize: 11,
      },
      grid: {
        vertLines: { color: '#f0f0f0' },
        horzLines: { color: '#f0f0f0' },
      },
      crosshair: {
        mode: 0,
        vertLine: { color: '#9ca3af', width: 1, style: 2, labelBackgroundColor: '#374151' },
        horzLine: { color: '#9ca3af', width: 1, style: 2, labelBackgroundColor: '#374151' },
      },
      timeScale: {
        borderColor: '#e5e7eb',
        timeVisible: false,
        rightOffset: 5,
        barSpacing: Math.max(3, Math.min(12, 600 / (data.fund.length || 90))),
      },
      rightPriceScale: {
        borderColor: '#e5e7eb',
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
      leftPriceScale: {
        visible: true,
        borderColor: '#e5e7eb',
        scaleMargins: { top: 0.05, bottom: 0.05 },
      },
    });
    chartRef.current = chart;

    // 1. NAV mountain (area series on left price scale)
    const navSeries = chart.addAreaSeries({
      topColor: MOUNTAIN_TOP,
      bottomColor: MOUNTAIN_BOTTOM,
      lineColor: MOUNTAIN_LINE,
      lineWidth: 1,
      priceScaleId: 'left',
      priceFormat: { type: 'custom', formatter: (p) => '$' + p.toFixed(4) },
      lastValueVisible: true,
      crosshairMarkerVisible: false,
    });
    navSeries.setData(
      data.fund.map(d => ({ time: d.date, value: d.nav_per_share }))
    );
    seriesMapRef.current['NAV'] = navSeries;

    // 2. Fund % line (right price scale, bold)
    const fundPctSeries = chart.addLineSeries({
      color: FUND_COLOR,
      lineWidth: 3,
      priceScaleId: 'right',
      priceFormat: { type: 'custom', formatter: (p) => p.toFixed(1) + '%' },
      lastValueVisible: false,
      crosshairMarkerVisible: true,
      crosshairMarkerRadius: 4,
    });
    fundPctSeries.setData(
      data.fund.map(d => ({ time: d.date, value: d.pct_change }))
    );
    seriesMapRef.current['Tovito'] = fundPctSeries;

    // 3. Benchmark lines
    Object.entries(data.benchmarks).forEach(([tk, series]) => {
      if (!series || !series.length) return;
      const style = BENCHMARK_COLORS[tk] || { line: '#95a5a6', label: tk };

      const lineSeries = chart.addLineSeries({
        color: style.line,
        lineWidth: 1.5,
        lineStyle: tk === 'BTC-USD' ? 2 : (tk === 'QQQ' ? 1 : 0),
        priceScaleId: 'right',
        priceFormat: { type: 'custom', formatter: (p) => p.toFixed(1) + '%' },
        lastValueVisible: false,
        crosshairMarkerVisible: true,
        crosshairMarkerRadius: 3,
      });
      lineSeries.setData(
        series.map(d => ({ time: d.date, value: d.pct_change }))
      );
      seriesMapRef.current[tk] = lineSeries;
    });

    // Crosshair tooltip
    chart.subscribeCrosshairMove((param) => {
      if (!param.time || !param.seriesData || param.seriesData.size === 0) {
        setTooltipData(null);
        return;
      }

      const values = {};
      for (const [key, series] of Object.entries(seriesMapRef.current)) {
        const d = param.seriesData.get(series);
        if (d && d.value !== undefined) {
          values[key] = d.value;
        }
      }

      setTooltipData({ time: param.time, values });
    });

    // Responsive resize
    const ro = new ResizeObserver(() => {
      if (container && chartRef.current) {
        chartRef.current.applyOptions({ width: container.clientWidth });
      }
    });
    ro.observe(container);

    chart.timeScale().fitContent();
  };

  const formatPct = (v) => v != null ? `${v >= 0 ? '+' : ''}${v.toFixed(2)}%` : '—';
  const pctColor = (v) => v == null ? 'text-gray-400' : v >= 0 ? 'text-green-600' : 'text-red-600';

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-blue-600" />
          <h3 className="text-lg font-semibold text-gray-900">Fund vs. Benchmarks</h3>
        </div>
        <div className="flex gap-1">
          {RANGE_OPTIONS.map(opt => (
            <button
              key={opt.value}
              onClick={() => setDays(opt.value)}
              className={`px-3 py-1 rounded text-xs font-medium transition ${
                days === opt.value
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Chart area */}
      {loading ? (
        <div className="h-[380px] flex items-center justify-center">
          <Loader2 className="w-8 h-8 animate-spin text-blue-400" />
        </div>
      ) : error ? (
        <div className="h-[380px] flex flex-col items-center justify-center text-gray-400">
          <AlertCircle className="w-8 h-8 mb-2" />
          <p className="text-sm">Chart unavailable</p>
          <button
            onClick={() => setRetryCount(c => c + 1)}
            className="mt-2 text-xs text-blue-500 hover:underline"
          >
            Retry
          </button>
        </div>
      ) : (
        <div className="relative">
          <div ref={chartContainerRef} className="w-full rounded-lg overflow-hidden" />

          {/* Floating tooltip */}
          {tooltipData && (
            <div
              ref={tooltipRef}
              className="absolute top-2 left-2 bg-white/95 backdrop-blur border border-gray-200 rounded-lg shadow-lg px-3 py-2 text-xs z-10 pointer-events-none"
            >
              <div className="font-semibold text-gray-700 mb-1 border-b border-gray-100 pb-1">
                {typeof tooltipData.time === 'string' ? tooltipData.time : tooltipData.time}
              </div>
              {tooltipData.values['NAV'] != null && (
                <div className="flex justify-between gap-4">
                  <span className="text-gray-500">NAV</span>
                  <span className="font-medium text-blue-700">${tooltipData.values['NAV'].toFixed(4)}</span>
                </div>
              )}
              {tooltipData.values['Tovito'] != null && (
                <div className="flex justify-between gap-4">
                  <span style={{ color: FUND_COLOR }} className="font-medium">Tovito</span>
                  <span className={`font-medium ${pctColor(tooltipData.values['Tovito'])}`}>
                    {formatPct(tooltipData.values['Tovito'])}
                  </span>
                </div>
              )}
              {Object.entries(BENCHMARK_COLORS).map(([tk, style]) =>
                tooltipData.values[tk] != null ? (
                  <div key={tk} className="flex justify-between gap-4">
                    <span style={{ color: style.line }}>{style.label}</span>
                    <span className={`font-medium ${pctColor(tooltipData.values[tk])}`}>
                      {formatPct(tooltipData.values[tk])}
                    </span>
                  </div>
                ) : null
              )}
            </div>
          )}
        </div>
      )}

      {/* Legend bar */}
      {!loading && !error && latestData && (
        <div className="flex flex-wrap gap-4 mt-3 pt-3 border-t border-gray-100 text-xs">
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-0.5 rounded" style={{ background: MOUNTAIN_LINE, display: 'inline-block' }} />
            <span className="text-gray-500">NAV:</span>
            <span className="font-semibold text-blue-700">
              {latestData.nav != null ? `$${latestData.nav.toFixed(4)}` : '—'}
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-0.5 rounded" style={{ background: FUND_COLOR, display: 'inline-block', height: 3 }} />
            <span className="text-gray-500">Tovito:</span>
            <span className={`font-semibold ${pctColor(latestData.fund_pct)}`}>
              {formatPct(latestData.fund_pct)}
            </span>
          </div>
          {Object.entries(BENCHMARK_COLORS).map(([tk, style]) => (
            <div key={tk} className="flex items-center gap-1.5">
              <span className="w-3 h-0.5 rounded" style={{ background: style.line, display: 'inline-block' }} />
              <span className="text-gray-500">{style.label}:</span>
              <span className={`font-semibold ${pctColor(latestData[tk])}`}>
                {formatPct(latestData[tk])}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};


// ============================================================
// REPORTS PAGE
// ============================================================

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

const ReportsPage = ({ onBack }) => {
  const { getAuthHeaders } = useAuth();
  const [reportType, setReportType] = useState('monthly');
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [year, setYear] = useState(2026);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [generating, setGenerating] = useState(false);
  const [jobId, setJobId] = useState(null);
  const [jobStatus, setJobStatus] = useState(null);
  const [error, setError] = useState(null);

  // Poll for job completion
  useEffect(() => {
    if (!jobId) return;
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/reports/status/${jobId}`, {
          headers: getAuthHeaders(),
        });
        if (!res.ok) throw new Error('Status check failed');
        const data = await res.json();
        setJobStatus(data);
        if (data.status === 'completed' || data.status === 'failed') {
          clearInterval(interval);
          setGenerating(false);
        }
      } catch {
        clearInterval(interval);
        setGenerating(false);
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [jobId, getAuthHeaders]);

  const handleGenerate = async () => {
    setGenerating(true);
    setJobStatus(null);
    setError(null);

    let endpoint, body;
    if (reportType === 'monthly') {
      endpoint = '/reports/monthly';
      body = { month, year };
    } else if (reportType === 'custom') {
      if (!startDate || !endDate) { setError('Please select both dates'); setGenerating(false); return; }
      endpoint = '/reports/custom';
      body = { start_date: startDate, end_date: endDate };
    } else {
      endpoint = `/reports/ytd?year=${year}`;
      body = null;
    }

    try {
      const res = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: 'POST',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Request failed');
      }
      const data = await res.json();
      setJobId(data.job_id);
      setJobStatus(data);
    } catch (e) {
      setError(e.message);
      setGenerating(false);
    }
  };

  const handleDownload = async () => {
    if (!jobStatus?.download_url) return;
    const res = await fetch(`${API_BASE_URL}${jobStatus.download_url}`, {
      headers: getAuthHeaders(),
    });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'report.pdf';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center h-16 gap-4">
            <button onClick={onBack} className="p-2 hover:bg-gray-100 rounded-lg">
              <ArrowLeft className="w-5 h-5 text-gray-600" />
            </button>
            <div className="flex items-center gap-2">
              <FileText className="w-5 h-5 text-blue-600" />
              <h1 className="font-bold text-gray-900">Generate Reports</h1>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Report Type Tabs */}
        <div className="flex gap-2 mb-6">
          {[
            { key: 'monthly', label: 'Monthly Statement', icon: Calendar },
            { key: 'custom', label: 'Custom Range', icon: Table2 },
            { key: 'ytd', label: 'Year-to-Date', icon: Activity },
          ].map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => { setReportType(key); setJobStatus(null); setError(null); }}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition ${
                reportType === key
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'
              }`}
            >
              <Icon className="w-4 h-4" />
              {label}
            </button>
          ))}
        </div>

        {/* Report Config */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-6">
          {reportType === 'monthly' && (
            <div className="flex gap-4 items-end">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Month</label>
                <select
                  value={month}
                  onChange={e => setMonth(Number(e.target.value))}
                  className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
                >
                  {MONTHS.map((m, i) => (
                    <option key={i} value={i + 1}>{m}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Year</label>
                <select
                  value={year}
                  onChange={e => setYear(Number(e.target.value))}
                  className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
                >
                  <option value={2026}>2026</option>
                  <option value={2027}>2027</option>
                </select>
              </div>
              <button
                onClick={handleGenerate}
                disabled={generating}
                className="px-6 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
              >
                {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                Generate
              </button>
            </div>
          )}

          {reportType === 'custom' && (
            <div className="flex gap-4 items-end">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Start Date</label>
                <input
                  type="date"
                  value={startDate}
                  onChange={e => setStartDate(e.target.value)}
                  className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">End Date</label>
                <input
                  type="date"
                  value={endDate}
                  onChange={e => setEndDate(e.target.value)}
                  className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
                />
              </div>
              <button
                onClick={handleGenerate}
                disabled={generating}
                className="px-6 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
              >
                {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                Generate
              </button>
            </div>
          )}

          {reportType === 'ytd' && (
            <div className="flex gap-4 items-end">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Year</label>
                <select
                  value={year}
                  onChange={e => setYear(Number(e.target.value))}
                  className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
                >
                  <option value={2026}>2026</option>
                  <option value={2027}>2027</option>
                </select>
              </div>
              <button
                onClick={handleGenerate}
                disabled={generating}
                className="px-6 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
              >
                {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                Generate
              </button>
            </div>
          )}
        </div>

        {/* Status / Download */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4 text-red-700 text-sm">
            {error}
          </div>
        )}

        {jobStatus && (
          <div className={`rounded-lg p-4 mb-4 text-sm ${
            jobStatus.status === 'completed' ? 'bg-green-50 border border-green-200 text-green-700'
            : jobStatus.status === 'failed' ? 'bg-red-50 border border-red-200 text-red-700'
            : 'bg-blue-50 border border-blue-200 text-blue-700'
          }`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {jobStatus.status === 'completed' ? (
                  <CheckCircle2 className="w-5 h-5" />
                ) : jobStatus.status === 'failed' ? (
                  <AlertCircle className="w-5 h-5" />
                ) : (
                  <Loader2 className="w-5 h-5 animate-spin" />
                )}
                <span>{jobStatus.message}</span>
              </div>
              {jobStatus.status === 'completed' && (
                <button
                  onClick={handleDownload}
                  className="px-4 py-1.5 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 flex items-center gap-1.5"
                >
                  <Download className="w-4 h-4" />
                  Download PDF
                </button>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
};


// ============================================================
// PORTFOLIO ANALYSIS
// ============================================================

const DonutChart = ({ data, size = 180 }) => {
  if (!data || data.length === 0) return null;
  const total = data.reduce((sum, d) => sum + d.value, 0);
  if (total === 0) return null;

  const colors = ['#1e3a5f', '#4a90d9', '#2d8a4e', '#8e44ad', '#e67e22', '#c0392b', '#f39c12', '#95a5a6', '#1abc9c'];
  const radius = size / 2 - 5;
  const cx = size / 2;
  const cy = size / 2;

  let cumAngle = -Math.PI / 2;
  const slices = data.map((d, i) => {
    const angle = (d.value / total) * 2 * Math.PI;
    const startAngle = cumAngle;
    cumAngle += angle;
    const endAngle = cumAngle;
    const largeArc = angle > Math.PI ? 1 : 0;
    const innerR = radius * 0.55;

    const x1 = cx + radius * Math.cos(startAngle);
    const y1 = cy + radius * Math.sin(startAngle);
    const x2 = cx + radius * Math.cos(endAngle);
    const y2 = cy + radius * Math.sin(endAngle);
    const ix1 = cx + innerR * Math.cos(endAngle);
    const iy1 = cy + innerR * Math.sin(endAngle);
    const ix2 = cx + innerR * Math.cos(startAngle);
    const iy2 = cy + innerR * Math.sin(startAngle);

    const path = `M ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2} L ${ix1} ${iy1} A ${innerR} ${innerR} 0 ${largeArc} 0 ${ix2} ${iy2} Z`;

    return <path key={i} d={path} fill={colors[i % colors.length]} opacity={0.85} />;
  });

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      {slices}
    </svg>
  );
};

const PortfolioAnalysis = () => {
  const [tab, setTab] = useState('holdings');
  const { data: holdings, loading: hLoading } = useApi('/analysis/holdings');
  const { data: risk, loading: rLoading } = useApi('/analysis/risk-metrics');
  const { data: monthly, loading: mLoading } = useApi('/analysis/monthly-performance');

  const formatCurrency = (val) =>
    val != null ? '$' + val.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—';
  const formatPct = (v) => v != null ? `${v >= 0 ? '+' : ''}${v.toFixed(2)}%` : '—';
  const pctColor = (v) => v == null ? 'text-gray-400' : v >= 0 ? 'text-green-600' : 'text-red-600';

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-8">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Activity className="w-5 h-5 text-blue-600" />
          <h3 className="text-lg font-semibold text-gray-900">Portfolio Analysis</h3>
        </div>
        <div className="flex gap-1">
          {[
            { key: 'holdings', label: 'Holdings' },
            { key: 'risk', label: 'Risk Metrics' },
            { key: 'monthly', label: 'Monthly Returns' },
          ].map(t => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-3 py-1 rounded text-xs font-medium transition ${
                tab === t.key
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Holdings Tab */}
      {tab === 'holdings' && (
        hLoading ? (
          <div className="h-48 flex items-center justify-center">
            <Loader2 className="w-6 h-6 animate-spin text-blue-400" />
          </div>
        ) : !holdings || holdings.position_count === 0 ? (
          <div className="text-center py-8 text-gray-400">
            <PieChart className="w-8 h-8 mx-auto mb-2" />
            <p className="text-sm">No holdings data available</p>
          </div>
        ) : (
          <div>
            {/* Summary + Donut */}
            <div className="flex gap-6 mb-4">
              <DonutChart data={holdings.by_symbol} />
              <div className="flex-1">
                <div className="grid grid-cols-3 gap-4 mb-3">
                  <div>
                    <p className="text-xs text-gray-500">Total Value</p>
                    <p className="text-lg font-bold text-gray-900">{formatCurrency(holdings.total_market_value)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">Unrealized P&L</p>
                    <p className={`text-lg font-bold ${pctColor(holdings.total_unrealized_pl)}`}>
                      {formatCurrency(holdings.total_unrealized_pl)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">Positions</p>
                    <p className="text-lg font-bold text-gray-900">{holdings.position_count}</p>
                  </div>
                </div>
                {/* Legend */}
                <div className="flex flex-wrap gap-2">
                  {(holdings.by_symbol || []).map((s, i) => {
                    const colors = ['#1e3a5f', '#4a90d9', '#2d8a4e', '#8e44ad', '#e67e22', '#c0392b', '#f39c12', '#95a5a6', '#1abc9c'];
                    return (
                      <span key={s.name} className="flex items-center gap-1 text-xs text-gray-600">
                        <span className="w-2 h-2 rounded-full inline-block" style={{ background: colors[i % colors.length] }} />
                        {s.name}
                      </span>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Holdings Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500 border-b border-gray-200 text-xs">
                    <th className="pb-2 font-medium">Symbol</th>
                    <th className="pb-2 font-medium">Type</th>
                    <th className="pb-2 font-medium text-right">Market Value</th>
                    <th className="pb-2 font-medium text-right">Cost Basis</th>
                    <th className="pb-2 font-medium text-right">P&L</th>
                    <th className="pb-2 font-medium text-right">P&L%</th>
                    <th className="pb-2 font-medium text-right">Weight</th>
                  </tr>
                </thead>
                <tbody>
                  {holdings.holdings.map(h => (
                    <tr key={h.symbol} className="border-b border-gray-50 hover:bg-gray-50">
                      <td className="py-2 font-medium text-gray-900">{h.symbol}</td>
                      <td className="py-2 text-gray-500 text-xs">{h.instrument_type}</td>
                      <td className="py-2 text-right">{formatCurrency(h.market_value)}</td>
                      <td className="py-2 text-right text-gray-500">{formatCurrency(h.cost_basis)}</td>
                      <td className={`py-2 text-right font-medium ${pctColor(h.unrealized_pl)}`}>
                        {formatCurrency(h.unrealized_pl)}
                      </td>
                      <td className={`py-2 text-right font-medium ${pctColor(h.unrealized_pl_pct)}`}>
                        {formatPct(h.unrealized_pl_pct)}
                      </td>
                      <td className="py-2 text-right text-gray-500">{h.weight_pct?.toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {holdings.snapshot_date && (
              <p className="text-xs text-gray-400 mt-2">As of {holdings.snapshot_date}</p>
            )}
          </div>
        )
      )}

      {/* Risk Metrics Tab */}
      {tab === 'risk' && (
        rLoading ? (
          <div className="h-48 flex items-center justify-center">
            <Loader2 className="w-6 h-6 animate-spin text-blue-400" />
          </div>
        ) : !risk ? (
          <div className="text-center py-8 text-gray-400">
            <Shield className="w-8 h-8 mx-auto mb-2" />
            <p className="text-sm">Insufficient data for risk metrics</p>
          </div>
        ) : (
          <div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { label: 'Sharpe Ratio', value: risk.sharpe_ratio != null ? risk.sharpe_ratio.toFixed(2) : '—', sub: 'Risk-adjusted return', good: risk.sharpe_ratio > 1 },
                { label: 'Max Drawdown', value: `${risk.max_drawdown_pct.toFixed(2)}%`, sub: risk.max_drawdown_start ? `${risk.max_drawdown_start} → ${risk.max_drawdown_end}` : '—', good: false },
                { label: 'Volatility', value: `${risk.annualized_volatility_pct.toFixed(2)}%`, sub: 'Annualized', good: null },
                { label: 'Win Rate', value: `${risk.win_rate_pct.toFixed(1)}%`, sub: `${risk.positive_days}W / ${risk.negative_days}L`, good: risk.win_rate_pct > 50 },
                { label: 'Best Day', value: `+${risk.best_day_pct.toFixed(2)}%`, sub: risk.best_day_date || '—', good: true },
                { label: 'Worst Day', value: `${risk.worst_day_pct.toFixed(2)}%`, sub: risk.worst_day_date || '—', good: false },
                { label: 'Annualized Return', value: `${risk.annualized_return_pct >= 0 ? '+' : ''}${risk.annualized_return_pct.toFixed(2)}%`, sub: `${risk.trading_days} trading days`, good: risk.annualized_return_pct > 0 },
                { label: 'Total Return', value: `${risk.total_return_pct >= 0 ? '+' : ''}${risk.total_return_pct.toFixed(2)}%`, sub: `${risk.period_start} → ${risk.period_end}`, good: risk.total_return_pct > 0 },
              ].map(m => (
                <div key={m.label} className="p-3 bg-gray-50 rounded-lg">
                  <p className="text-xs text-gray-500 mb-1">{m.label}</p>
                  <p className={`text-lg font-bold ${m.good === true ? 'text-green-600' : m.good === false ? 'text-red-600' : 'text-gray-900'}`}>
                    {m.value}
                  </p>
                  <p className="text-xs text-gray-400 mt-0.5 truncate">{m.sub}</p>
                </div>
              ))}
            </div>
          </div>
        )
      )}

      {/* Monthly Returns Tab */}
      {tab === 'monthly' && (
        mLoading ? (
          <div className="h-48 flex items-center justify-center">
            <Loader2 className="w-6 h-6 animate-spin text-blue-400" />
          </div>
        ) : !monthly || monthly.months.length === 0 ? (
          <div className="text-center py-8 text-gray-400">
            <Table2 className="w-8 h-8 mx-auto mb-2" />
            <p className="text-sm">No monthly data available</p>
          </div>
        ) : (
          <div>
            {/* Best / Worst summary */}
            <div className="flex gap-4 mb-4">
              <div className="flex items-center gap-2 px-3 py-1.5 bg-green-50 rounded-lg text-xs">
                <TrendingUp className="w-3.5 h-3.5 text-green-600" />
                <span className="text-gray-600">Best:</span>
                <span className="font-semibold text-green-600">{monthly.best_month} ({formatPct(monthly.best_month_return)})</span>
              </div>
              <div className="flex items-center gap-2 px-3 py-1.5 bg-red-50 rounded-lg text-xs">
                <TrendingDown className="w-3.5 h-3.5 text-red-600" />
                <span className="text-gray-600">Worst:</span>
                <span className="font-semibold text-red-600">{monthly.worst_month} ({formatPct(monthly.worst_month_return)})</span>
              </div>
            </div>

            {/* Monthly grid */}
            <div className="space-y-1">
              {monthly.months.map(m => {
                const maxAbsReturn = Math.max(...monthly.months.map(x => Math.abs(x.return_pct)), 1);
                const barWidth = Math.min(100, (Math.abs(m.return_pct) / maxAbsReturn) * 100);
                return (
                  <div key={m.month} className="flex items-center gap-3 py-1.5">
                    <span className="w-20 text-xs font-medium text-gray-600 shrink-0">{m.month_label}</span>
                    <div className="flex-1 h-7 bg-gray-50 rounded relative overflow-hidden">
                      <div
                        className={`absolute inset-y-0 left-0 rounded ${m.return_pct >= 0 ? 'bg-green-100' : 'bg-red-100'}`}
                        style={{ width: `${barWidth}%` }}
                      />
                      <div className="relative px-2 h-full flex items-center">
                        <span className={`text-xs font-semibold ${pctColor(m.return_pct)}`}>
                          {formatPct(m.return_pct)}
                        </span>
                      </div>
                    </div>
                    <span className="text-xs text-gray-400 w-14 text-right shrink-0">{m.trading_days}d</span>
                    <span className="text-xs text-gray-400 w-28 text-right shrink-0">
                      ${m.start_nav.toFixed(4)} → ${m.end_nav.toFixed(4)}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )
      )}
    </div>
  );
};


// ============================================================
// DASHBOARD
// ============================================================

const Dashboard = () => {
  const { user, logout } = useAuth();
  const [dashboardView, setDashboardView] = useState('main');
  const { data: position, refetch: refetchPosition } = useApi('/investor/position');
  const { data: navData } = useApi('/nav/current');
  const { data: performance } = useApi('/nav/performance');
  const { data: transactions } = useApi('/investor/transactions?limit=5');

  const formatCurrency = (val) => {
    if (val === undefined || val === null) return '$--';
    return '$' + val.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };

  if (dashboardView === 'help') {
    return <TutorialsPage onBack={() => setDashboardView('main')} />;
  }

  if (dashboardView === 'reports') {
    return <ReportsPage onBack={() => setDashboardView('main')} />;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-100 rounded-lg">
                <TrendingUp className="w-6 h-6 text-blue-600" />
              </div>
              <div>
                <h1 className="font-bold text-gray-900">Tovito Trader</h1>
                <p className="text-xs text-gray-500">Investor Portal</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <button
                onClick={refetchPosition}
                className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition"
                title="Refresh"
              >
                <RefreshCw className="w-5 h-5" />
              </button>
              <button
                onClick={() => setDashboardView('reports')}
                className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition"
                title="Generate Reports"
              >
                <FileText className="w-5 h-5" />
              </button>
              <button
                onClick={() => setDashboardView('help')}
                className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition"
                title="Help & Tutorials"
              >
                <HelpCircle className="w-5 h-5" />
              </button>
              <div className="flex items-center gap-3">
                <div className="text-right">
                  <p className="text-sm font-medium text-gray-900">{user?.name}</p>
                  <p className="text-xs text-gray-500">{user?.email}</p>
                </div>
                <button
                  onClick={logout}
                  className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition"
                  title="Sign out"
                >
                  <LogOut className="w-5 h-5" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Welcome */}
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-gray-900">Welcome back, {user?.name?.split(' ')[0]}</h2>
          <p className="text-gray-500">{"Here's your portfolio overview as of "}{position?.as_of_date || 'today'}</p>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <StatCard
            title="Portfolio Value"
            value={formatCurrency(position?.current_value)}
            subtitle={`${position?.current_shares?.toLocaleString('en-US', { maximumFractionDigits: 4 })} shares`}
            icon={DollarSign}
            trend={position?.total_return_percent >= 0 ? 'up' : 'down'}
            trendValue={position?.total_return_percent}
          />
          <StatCard
            title="Total Return"
            value={formatCurrency(position?.total_return_dollars)}
            subtitle={`${position?.total_return_percent?.toFixed(2)}% gain`}
            icon={position?.total_return_percent >= 0 ? TrendingUp : TrendingDown}
            trend={position?.total_return_percent >= 0 ? 'up' : 'down'}
          />
          <StatCard
            title="NAV per Share"
            value={`$${navData?.nav_per_share?.toFixed(4) || '--'}`}
            subtitle={`${navData?.daily_change_percent?.toFixed(2) || '0.00'}% today`}
            icon={PieChart}
            trend={navData?.daily_change_percent >= 0 ? 'up' : 'down'}
          />
          <StatCard
            title="Portfolio Share"
            value={`${position?.portfolio_percentage?.toFixed(2) || '--'}%`}
            subtitle="of total fund"
            icon={User}
          />
        </div>

        {/* Benchmark Comparison Chart */}
        <BenchmarkChart />

        {/* Portfolio Analysis */}
        <PortfolioAnalysis />

        {/* Two Column Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Performance Card */}
          <div className="lg:col-span-2 bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Fund Performance</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="text-center p-4 bg-gray-50 rounded-lg">
                <p className="text-sm text-gray-500">Daily</p>
                <p className={`text-xl font-bold ${performance?.daily_return >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {performance?.daily_return >= 0 ? '+' : ''}{performance?.daily_return?.toFixed(2) || '0.00'}%
                </p>
              </div>
              <div className="text-center p-4 bg-gray-50 rounded-lg">
                <p className="text-sm text-gray-500">Month-to-Date</p>
                <p className={`text-xl font-bold ${performance?.mtd_return >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {performance?.mtd_return >= 0 ? '+' : ''}{performance?.mtd_return?.toFixed(2) || '0.00'}%
                </p>
              </div>
              <div className="text-center p-4 bg-gray-50 rounded-lg">
                <p className="text-sm text-gray-500">Year-to-Date</p>
                <p className={`text-xl font-bold ${performance?.ytd_return >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {performance?.ytd_return >= 0 ? '+' : ''}{performance?.ytd_return?.toFixed(2) || '0.00'}%
                </p>
              </div>
              <div className="text-center p-4 bg-gray-50 rounded-lg">
                <p className="text-sm text-gray-500">Since Inception</p>
                <p className={`text-xl font-bold ${performance?.since_inception >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {performance?.since_inception >= 0 ? '+' : ''}{performance?.since_inception?.toFixed(2) || '0.00'}%
                </p>
              </div>
            </div>
            
            <div className="mt-6 pt-6 border-t border-gray-100">
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-500">Fund Size</span>
                <span className="font-semibold">{formatCurrency(performance?.total_portfolio_value)}</span>
              </div>
              <div className="flex items-center justify-between text-sm mt-2">
                <span className="text-gray-500">Active Investors</span>
                <span className="font-semibold">{performance?.total_investors || '--'}</span>
              </div>
              <div className="flex items-center justify-between text-sm mt-2">
                <span className="text-gray-500">Inception Date</span>
                <span className="font-semibold">{performance?.inception_date || '--'}</span>
              </div>
            </div>
          </div>

          {/* Recent Transactions */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900">Recent Transactions</h3>
              <FileText className="w-5 h-5 text-gray-400" />
            </div>
            
            {transactions?.transactions?.length > 0 ? (
              <div>
                {transactions.transactions.map((tx, i) => (
                  <TransactionRow key={i} transaction={tx} />
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <Clock className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                <p>No transactions yet</p>
              </div>
            )}
            
            <div className="mt-4 pt-4 border-t border-gray-100 text-sm text-gray-500">
              <div className="flex justify-between">
                <span>Total Contributions</span>
                <span className="text-green-600 font-medium">{formatCurrency(transactions?.total_contributions)}</span>
              </div>
              <div className="flex justify-between mt-1">
                <span>Total Withdrawals</span>
                <span className="text-red-600 font-medium">{formatCurrency(transactions?.total_withdrawals)}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Account Summary */}
        <div className="mt-6 bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Account Summary</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            <div>
              <p className="text-sm text-gray-500">Net Investment</p>
              <p className="text-xl font-bold text-gray-900">{formatCurrency(position?.net_investment)}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Initial Capital</p>
              <p className="text-xl font-bold text-gray-900">{formatCurrency(position?.initial_capital)}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Current Shares</p>
              <p className="text-xl font-bold text-gray-900">{position?.current_shares?.toLocaleString('en-US', { maximumFractionDigits: 4 }) || '--'}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Investor ID</p>
              <p className="text-xl font-bold text-gray-900">{position?.investor_id || '--'}</p>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-200 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <p className="text-center text-sm text-gray-500">
            © 2026 Tovito Trader. All data as of market close.
          </p>
        </div>
      </footer>
    </div>
  );
};

// ============================================================
// MAIN APP
// ============================================================

const App = () => {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
};

const AppContent = () => {
  const { user, loading } = useAuth();
  const [page, setPage] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get('token');
    if (token && window.location.pathname.includes('verify')) {
      return { name: 'verify', token };
    }
    if (token && window.location.pathname.includes('reset-password')) {
      return { name: 'reset-password', token };
    }
    return { name: 'login' };
  });

  const navigateToLogin = () => {
    window.history.replaceState({}, '', window.location.pathname.split('?')[0]);
    setPage({ name: 'login' });
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  if (user) return <Dashboard />;

  if (page.name === 'forgot-password') {
    return (
      <ForgotPasswordPage
        onBackToLogin={navigateToLogin}
      />
    );
  }

  if (page.name === 'account-setup') {
    return (
      <AccountSetupPage
        onBackToLogin={navigateToLogin}
      />
    );
  }

  if (page.name === 'verify') {
    return (
      <VerifyPage
        token={page.token}
        onBackToLogin={navigateToLogin}
        onRequestNewSetup={() => setPage({ name: 'account-setup' })}
      />
    );
  }

  if (page.name === 'reset-password') {
    return (
      <ResetPasswordPage
        token={page.token}
        onBackToLogin={navigateToLogin}
        onRequestNewLink={() => setPage({ name: 'forgot-password' })}
      />
    );
  }

  return (
    <LoginPage
      onForgotPassword={() => setPage({ name: 'forgot-password' })}
      onAccountSetup={() => setPage({ name: 'account-setup' })}
    />
  );
};

export default App;
