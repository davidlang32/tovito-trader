import { useState, useEffect, useCallback, createContext, useContext, useRef } from 'react';
import { API_BASE_URL } from '../config';

const AuthContext = createContext(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
};

// Token expiration constants (match backend)
const ACCESS_TOKEN_MINUTES = 30;
const WARN_BEFORE_SECONDS = 120; // warn 2 minutes before expiry
const CHECK_INTERVAL_MS = 30000; // check every 30 seconds

const parseJwt = (token) => {
  try {
    const payload = token.split('.')[1];
    return JSON.parse(atob(payload));
  } catch {
    return null;
  }
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [tokens, setTokens] = useState(() => {
    const saved = localStorage.getItem('tokens');
    return saved ? JSON.parse(saved) : null;
  });
  const [loading, setLoading] = useState(true);
  const [sessionExpired, setSessionExpired] = useState(false);
  const [sessionWarning, setSessionWarning] = useState(false);

  // Track if we're currently refreshing to avoid multiple simultaneous refreshes
  const refreshingRef = useRef(false);
  const warningTimerRef = useRef(null);
  const expiryTimerRef = useRef(null);

  const logout = useCallback(() => {
    setUser(null);
    setTokens(null);
    setSessionWarning(false);
    localStorage.removeItem('tokens');
    if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
    if (expiryTimerRef.current) clearTimeout(expiryTimerRef.current);
  }, []);

  const handleSessionExpired = useCallback(() => {
    setSessionWarning(false);
    setSessionExpired(true);
    setUser(null);
    setTokens(null);
    localStorage.removeItem('tokens');
    if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
    if (expiryTimerRef.current) clearTimeout(expiryTimerRef.current);
  }, []);

  const refreshTokens = useCallback(async () => {
    if (refreshingRef.current || !tokens?.refresh_token) return false;
    refreshingRef.current = true;

    try {
      const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: tokens.refresh_token })
      });

      if (res.ok) {
        const data = await res.json();
        const newTokens = {
          access_token: data.access_token,
          refresh_token: data.refresh_token
        };
        setTokens(newTokens);
        localStorage.setItem('tokens', JSON.stringify(newTokens));
        setSessionWarning(false);
        refreshingRef.current = false;
        return true;
      } else {
        // Refresh token also expired — session over
        handleSessionExpired();
        refreshingRef.current = false;
        return false;
      }
    } catch {
      refreshingRef.current = false;
      return false;
    }
  }, [tokens, handleSessionExpired]);

  // Setup session timers when tokens change
  useEffect(() => {
    if (!tokens?.access_token) return;

    const payload = parseJwt(tokens.access_token);
    if (!payload?.exp) return;

    const now = Date.now() / 1000;
    const expiresIn = payload.exp - now;

    // Clear old timers
    if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
    if (expiryTimerRef.current) clearTimeout(expiryTimerRef.current);

    if (expiresIn <= 0) {
      // Already expired, try to refresh
      refreshTokens().then(success => {
        if (!success) handleSessionExpired();
      });
      return;
    }

    // Set warning timer (2 min before expiry)
    const warnInMs = Math.max((expiresIn - WARN_BEFORE_SECONDS) * 1000, 0);
    warningTimerRef.current = setTimeout(() => {
      setSessionWarning(true);
    }, warnInMs);

    // Set auto-refresh timer (try to refresh 30 sec before expiry)
    const refreshInMs = Math.max((expiresIn - 30) * 1000, 0);
    expiryTimerRef.current = setTimeout(() => {
      refreshTokens().then(success => {
        if (!success) handleSessionExpired();
      });
    }, refreshInMs);

    return () => {
      if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
      if (expiryTimerRef.current) clearTimeout(expiryTimerRef.current);
    };
  }, [tokens, refreshTokens, handleSessionExpired]);

  const extendSession = useCallback(async () => {
    const success = await refreshTokens();
    if (success) {
      setSessionWarning(false);
    }
    return success;
  }, [refreshTokens]);

  const dismissExpired = useCallback(() => {
    setSessionExpired(false);
  }, []);

  const fetchUser = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/auth/me`, {
        headers: { Authorization: `Bearer ${tokens.access_token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setUser(data);
      } else if (res.status === 401) {
        // Token expired — try refresh
        const refreshed = await refreshTokens();
        if (!refreshed) {
          handleSessionExpired();
        }
      } else {
        logout();
      }
    } catch (err) {
      console.error('Failed to fetch user:', err);
    } finally {
      setLoading(false);
    }
  }, [tokens, logout, refreshTokens, handleSessionExpired]);

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
    setSessionExpired(false);
    setSessionWarning(false);

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
    setSessionExpired(false);
    setSessionWarning(false);
    setUser({ name: tokenData.investor_name, email: '' });
  }, []);

  const getAuthHeaders = useCallback(() => ({
    Authorization: `Bearer ${tokens?.access_token}`,
    'Content-Type': 'application/json'
  }), [tokens]);

  return (
    <AuthContext.Provider value={{
      user, tokens, loading,
      login, loginWithTokens, logout, getAuthHeaders,
      sessionExpired, sessionWarning, extendSession, dismissExpired,
    }}>
      {children}
    </AuthContext.Provider>
  );
};
