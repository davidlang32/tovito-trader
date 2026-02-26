import { useState, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { CheckCircle2, AlertTriangle, Loader2, TrendingUp } from 'lucide-react';
import { API_BASE_URL } from '../config';

const VerifyProspectPage = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const [status, setStatus] = useState('loading'); // loading | success | error | network

  useEffect(() => {
    if (!token) {
      setStatus('error');
      return;
    }

    let cancelled = false;

    const verify = async () => {
      try {
        const res = await fetch(
          `${API_BASE_URL}/public/verify-prospect?token=${encodeURIComponent(token)}`
        );
        if (!cancelled) {
          setStatus(res.ok ? 'success' : 'error');
        }
      } catch {
        if (!cancelled) setStatus('network');
      }
    };

    verify();

    return () => { cancelled = true; };
  }, [token]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-emerald-900 to-slate-900 flex items-center justify-center px-6">
      {/* Background elements */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute top-20 left-10 w-72 h-72 bg-emerald-500/10 rounded-full blur-3xl animate-pulse" />
        <div className="absolute bottom-20 right-10 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />
      </div>

      <div className="relative z-10 max-w-md w-full">
        {/* Logo */}
        <div className="flex items-center justify-center gap-3 mb-8">
          <div className="w-10 h-10 bg-emerald-500 rounded-xl flex items-center justify-center shadow-lg shadow-emerald-500/30">
            <TrendingUp className="w-6 h-6 text-white" />
          </div>
          <h1 className="text-white font-bold text-lg tracking-tight">TOVITO TRADER</h1>
        </div>

        {/* Loading */}
        {status === 'loading' && (
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-10 text-center shadow-2xl">
            <Loader2 className="w-10 h-10 text-emerald-400 animate-spin mx-auto mb-4" />
            <p className="text-slate-400 text-sm">Verifying your email...</p>
          </div>
        )}

        {/* Success */}
        {status === 'success' && (
          <div className="bg-slate-800/50 border border-emerald-500/30 rounded-2xl p-10 text-center shadow-2xl">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-emerald-500/10 rounded-full mb-5">
              <CheckCircle2 className="w-8 h-8 text-emerald-400" />
            </div>
            <h2 className="text-2xl font-bold text-white mb-3">Email Verified</h2>
            <p className="text-slate-400 text-sm leading-relaxed mb-6">
              Thank you for verifying your email address. A member of our team
              will be in touch shortly to discuss how Tovito Trader can help you
              achieve your investment goals.
            </p>
            <Link
              to="/"
              className="inline-flex items-center gap-2 bg-emerald-500 hover:bg-emerald-600 text-white px-6 py-2.5 rounded-xl text-sm font-semibold transition shadow-lg shadow-emerald-500/25"
            >
              Back to Home
            </Link>
          </div>
        )}

        {/* Error (invalid/expired) */}
        {status === 'error' && (
          <div className="bg-slate-800/50 border border-red-500/30 rounded-2xl p-10 text-center shadow-2xl">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-red-500/10 rounded-full mb-5">
              <AlertTriangle className="w-8 h-8 text-red-400" />
            </div>
            <h2 className="text-2xl font-bold text-white mb-3">Invalid or Expired Link</h2>
            <p className="text-slate-400 text-sm leading-relaxed mb-6">
              This verification link is invalid or has expired. Please submit a new
              inquiry and we will send you a fresh verification link.
            </p>
            <Link
              to="/#inquiry"
              className="inline-flex items-center gap-2 bg-emerald-500 hover:bg-emerald-600 text-white px-6 py-2.5 rounded-xl text-sm font-semibold transition shadow-lg shadow-emerald-500/25"
            >
              Submit New Inquiry
            </Link>
          </div>
        )}

        {/* Network error */}
        {status === 'network' && (
          <div className="bg-slate-800/50 border border-amber-500/30 rounded-2xl p-10 text-center shadow-2xl">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-amber-500/10 rounded-full mb-5">
              <AlertTriangle className="w-8 h-8 text-amber-400" />
            </div>
            <h2 className="text-2xl font-bold text-white mb-3">Connection Error</h2>
            <p className="text-slate-400 text-sm leading-relaxed mb-6">
              We could not reach our servers. Please check your internet connection
              and try clicking the verification link again.
            </p>
            <button
              onClick={() => window.location.reload()}
              className="inline-flex items-center gap-2 bg-emerald-500 hover:bg-emerald-600 text-white px-6 py-2.5 rounded-xl text-sm font-semibold transition shadow-lg shadow-emerald-500/25"
            >
              Try Again
            </button>
          </div>
        )}

        {/* Footer */}
        <p className="text-center text-slate-600 text-[10px] mt-6">
          &copy; 2026 Tovito Trader. All rights reserved.
        </p>
      </div>
    </div>
  );
};

export default VerifyProspectPage;
