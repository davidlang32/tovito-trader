import { useState, useEffect, useCallback, createContext, useContext } from 'react';
import {
  TrendingUp, TrendingDown, DollarSign, PieChart,
  LogOut, RefreshCw, ArrowUpRight, ArrowDownRight,
  User, FileText, Clock, AlertCircle,
  Eye, EyeOff, Loader2
} from 'lucide-react';

// ============================================================
// CONFIGURATION
// ============================================================

const API_BASE_URL = 'http://localhost:8000';

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

  const getAuthHeaders = useCallback(() => ({
    Authorization: `Bearer ${tokens?.access_token}`,
    'Content-Type': 'application/json'
  }), [tokens]);

  return (
    <AuthContext.Provider value={{ user, tokens, loading, login, logout, getAuthHeaders }}>
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

const LoginPage = () => {
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
            <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
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
          First time? Contact your fund administrator.
        </p>
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

const Dashboard = () => {
  const { user, logout } = useAuth();
  const { data: position, refetch: refetchPosition } = useApi('/investor/position');
  const { data: navData } = useApi('/nav/current');
  const { data: performance } = useApi('/nav/performance');
  const { data: transactions } = useApi('/investor/transactions?limit=5');

  const formatCurrency = (val) => {
    if (val === undefined || val === null) return '$--';
    return '$' + val.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };

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

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return user ? <Dashboard /> : <LoginPage />;
};

export default App;
