import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  TrendingUp, AlertCircle, Eye, EyeOff, Loader2, ArrowLeft,
  CheckCircle2, Mail, Shield, BarChart3, PieChart, Lock, Zap
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { API_BASE_URL } from '../config';

// ============================================================
// LOGIN PAGE — Premium Split-Panel Design
// ============================================================

export const LoginPage = () => {
  const navigate = useNavigate();
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
      navigate('/dashboard');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex">
      {/* Left panel — Brand & Features (hidden on mobile) */}
      <div className="hidden lg:flex lg:w-1/2 relative overflow-hidden bg-gradient-to-br from-slate-900 via-emerald-900 to-slate-900">
        {/* Animated background elements */}
        <div className="absolute inset-0">
          <div className="absolute top-20 left-10 w-72 h-72 bg-emerald-500/10 rounded-full blur-3xl animate-pulse" />
          <div className="absolute bottom-20 right-10 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />
          <div className="absolute top-1/2 left-1/3 w-48 h-48 bg-emerald-400/5 rounded-full blur-2xl animate-pulse" style={{ animationDelay: '2s' }} />
        </div>

        {/* Grid pattern overlay */}
        <div className="absolute inset-0 opacity-[0.03]" style={{
          backgroundImage: 'linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)',
          backgroundSize: '40px 40px'
        }} />

        <div className="relative z-10 flex flex-col justify-between p-12 w-full">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-emerald-500 rounded-xl flex items-center justify-center shadow-lg shadow-emerald-500/30">
              <TrendingUp className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-white font-bold text-lg tracking-tight">TOVITO TRADER</h1>
              <p className="text-emerald-400/80 text-xs font-medium">Investor Portal</p>
            </div>
          </div>

          {/* Hero text */}
          <div className="space-y-6">
            <div>
              <h2 className="text-4xl font-bold text-white leading-tight">
                Your wealth,<br />
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-blue-400">
                  at a glance.
                </span>
              </h2>
              <p className="text-slate-400 mt-3 text-base leading-relaxed max-w-md">
                Track your portfolio performance, monitor the fund in real-time,
                and manage your investments — all in one place.
              </p>
            </div>

            {/* Feature highlights */}
            <div className="space-y-3">
              <div className="flex items-center gap-3 text-slate-300">
                <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center flex-shrink-0">
                  <BarChart3 className="w-4 h-4 text-emerald-400" />
                </div>
                <span className="text-sm">Interactive performance charts vs S&P, Nasdaq & Bitcoin</span>
              </div>
              <div className="flex items-center gap-3 text-slate-300">
                <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center flex-shrink-0">
                  <PieChart className="w-4 h-4 text-blue-400" />
                </div>
                <span className="text-sm">Real-time portfolio allocation and fund holdings</span>
              </div>
              <div className="flex items-center gap-3 text-slate-300">
                <div className="w-8 h-8 rounded-lg bg-purple-500/10 flex items-center justify-center flex-shrink-0">
                  <Zap className="w-4 h-4 text-purple-400" />
                </div>
                <span className="text-sm">Request contributions and withdrawals with ease</span>
              </div>
              <div className="flex items-center gap-3 text-slate-300">
                <div className="w-8 h-8 rounded-lg bg-amber-500/10 flex items-center justify-center flex-shrink-0">
                  <Lock className="w-4 h-4 text-amber-400" />
                </div>
                <span className="text-sm">Bank-grade encryption for your data</span>
              </div>
            </div>
          </div>

          {/* Footer */}
          <p className="text-slate-500 text-xs">
            &copy; 2026 Tovito Trader. All rights reserved.
          </p>
        </div>
      </div>

      {/* Right panel — Login Form */}
      <div className="flex-1 flex items-center justify-center p-6 bg-gray-50">
        <div className="w-full max-w-md">
          {/* Mobile logo (hidden on desktop) */}
          <div className="lg:hidden text-center mb-8">
            <div className="inline-flex items-center justify-center w-14 h-14 bg-emerald-500 rounded-xl mb-3 shadow-lg shadow-emerald-500/30">
              <TrendingUp className="w-7 h-7 text-white" />
            </div>
            <h1 className="text-xl font-bold text-gray-900">Tovito Trader</h1>
            <p className="text-gray-500 text-sm">Investor Portal</p>
          </div>

          <div className="bg-white rounded-2xl shadow-xl border border-gray-100 p-8">
            <div className="mb-6">
              <h2 className="text-2xl font-bold text-gray-900">Welcome back</h2>
              <p className="text-gray-500 text-sm mt-1">Sign in to your investor account</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
              {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl flex items-center gap-2">
                  <AlertCircle className="w-5 h-5 flex-shrink-0" />
                  <span className="text-sm">{error}</span>
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Email address</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition bg-gray-50 focus:bg-white"
                  placeholder="you@example.com"
                  required
                  autoFocus
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="block text-sm font-medium text-gray-700">Password</label>
                  <button
                    type="button"
                    onClick={() => navigate('/forgot-password')}
                    className="text-sm text-emerald-600 hover:text-emerald-800 transition font-medium"
                  >
                    Forgot password?
                  </button>
                </div>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition pr-12 bg-gray-50 focus:bg-white"
                    placeholder="Enter your password"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition"
                  >
                    {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-semibold py-3 rounded-xl transition flex items-center justify-center gap-2 disabled:opacity-50 shadow-lg shadow-emerald-600/25 hover:shadow-emerald-600/40"
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

            <div className="mt-6 pt-5 border-t border-gray-100 text-center">
              <p className="text-sm text-gray-500">
                First time here?{' '}
                <button
                  type="button"
                  onClick={() => navigate('/setup')}
                  className="text-emerald-600 hover:text-emerald-800 transition font-semibold"
                >
                  Set up your account
                </button>
              </p>
            </div>
          </div>

          {/* Mobile footer */}
          <p className="lg:hidden text-center text-xs text-gray-400 mt-6">
            &copy; 2026 Tovito Trader. All rights reserved.
          </p>
        </div>
      </div>
    </div>
  );
};

// ============================================================
// ACCOUNT SETUP PAGE
// ============================================================

export const AccountSetupPage = () => {
  const navigate = useNavigate();
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
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-emerald-900 to-slate-900 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-8">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-emerald-100 rounded-2xl mb-4">
            <Shield className="w-8 h-8 text-emerald-600" />
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
            <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-xl">
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
              onClick={() => navigate('/login')}
              className="w-full bg-gray-100 hover:bg-gray-200 text-gray-700 font-medium py-3 rounded-xl transition flex items-center justify-center gap-2"
            >
              <ArrowLeft className="w-5 h-5" />
              Back to Sign In
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl">
                <div className="flex items-center gap-2">
                  <AlertCircle className="w-5 h-5 flex-shrink-0" />
                  <span className="text-sm">{error}</span>
                </div>
                {isAlreadySetUp && (
                  <button
                    type="button"
                    onClick={() => navigate('/login')}
                    className="mt-2 text-sm text-emerald-600 hover:text-emerald-800 underline"
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
                className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition"
                placeholder="you@example.com"
                required
                autoFocus
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-medium py-3 rounded-xl transition flex items-center justify-center gap-2 disabled:opacity-50"
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
              onClick={() => navigate('/login')}
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
// VERIFY PAGE (First-Time Password Setup)
// ============================================================

export const VerifyPage = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
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
      window.history.replaceState({}, '', '/dashboard');
      loginWithTokens(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const isExpiredOrInvalid = error.toLowerCase().includes('expired') || error.toLowerCase().includes('invalid');

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-emerald-900 to-slate-900 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-8">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-emerald-100 rounded-2xl mb-4">
            {success
              ? <CheckCircle2 className="w-8 h-8 text-green-600" />
              : <Shield className="w-8 h-8 text-emerald-600" />
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
            <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-xl flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
              <span className="text-sm">Account set up successfully. Loading your dashboard...</span>
            </div>
            <div className="flex justify-center">
              <Loader2 className="w-6 h-6 animate-spin text-emerald-600" />
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl">
                <div className="flex items-center gap-2">
                  <AlertCircle className="w-5 h-5 flex-shrink-0" />
                  <span className="text-sm">{error}</span>
                </div>
                {isExpiredOrInvalid && (
                  <button
                    type="button"
                    onClick={() => navigate('/setup')}
                    className="mt-2 text-sm text-emerald-600 hover:text-emerald-800 underline"
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
                  className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition pr-12"
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
                  className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition pr-12"
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
              className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-medium py-3 rounded-xl transition flex items-center justify-center gap-2 disabled:opacity-50"
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
              onClick={() => navigate('/login')}
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
// FORGOT PASSWORD PAGE
// ============================================================

export const ForgotPasswordPage = () => {
  const navigate = useNavigate();
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
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-emerald-900 to-slate-900 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-8">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-emerald-100 rounded-2xl mb-4">
            <Mail className="w-8 h-8 text-emerald-600" />
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
            <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-xl flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
              <span className="text-sm">
                If that email is registered, you'll receive a password reset link. The link expires in 1 hour.
              </span>
            </div>
            <button
              onClick={() => navigate('/login')}
              className="w-full bg-gray-100 hover:bg-gray-200 text-gray-700 font-medium py-3 rounded-xl transition flex items-center justify-center gap-2"
            >
              <ArrowLeft className="w-5 h-5" />
              Back to Sign In
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl flex items-center gap-2">
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
                className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition"
                placeholder="you@example.com"
                required
                autoFocus
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-medium py-3 rounded-xl transition flex items-center justify-center gap-2 disabled:opacity-50"
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
              onClick={() => navigate('/login')}
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
// RESET PASSWORD PAGE
// ============================================================

export const ResetPasswordPage = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
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
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-emerald-900 to-slate-900 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-8">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-emerald-100 rounded-2xl mb-4">
            {success
              ? <CheckCircle2 className="w-8 h-8 text-green-600" />
              : <TrendingUp className="w-8 h-8 text-emerald-600" />
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
            <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-xl flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
              <span className="text-sm">Password reset successful. You can now sign in with your new password.</span>
            </div>
            <button
              onClick={() => navigate('/login')}
              className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-medium py-3 rounded-xl transition flex items-center justify-center gap-2"
            >
              Sign In
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl">
                <div className="flex items-center gap-2">
                  <AlertCircle className="w-5 h-5 flex-shrink-0" />
                  <span className="text-sm">{error}</span>
                </div>
                {isExpiredOrInvalid && (
                  <button
                    type="button"
                    onClick={() => navigate('/forgot-password')}
                    className="mt-2 text-sm text-emerald-600 hover:text-emerald-800 underline"
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
                  className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition pr-12"
                  placeholder="Create a new password"
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
                  className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition pr-12"
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
              className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-medium py-3 rounded-xl transition flex items-center justify-center gap-2 disabled:opacity-50"
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
              onClick={() => navigate('/login')}
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
