import { useState, useEffect, useMemo, useRef } from 'react';
import { Link } from 'react-router-dom';
import {
  DollarSign, TrendingUp, TrendingDown, PieChart,
  ArrowUpRight, ArrowDownRight, Clock, ChevronRight, ChevronDown, ChevronUp,
  Loader2, AlertCircle
} from 'lucide-react';
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceDot
} from 'recharts';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import { useApi } from '../hooks/useApi';
import { API_BASE_URL } from '../config';

// ============================================================
// HELPERS
// ============================================================

const formatCurrency = (val) => {
  if (val === undefined || val === null) return '$--';
  return '$' + val.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

const formatPct = (v) => v != null ? `${v >= 0 ? '+' : ''}${v.toFixed(2)}%` : '--';

const getGreeting = () => {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
};

// ============================================================
// STAT CARD
// ============================================================

const StatCard = ({ title, value, subtitle, icon: Icon, trend, trendValue, accentColor }) => (
  <div className={`bg-white dark:bg-slate-800/50 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700/50 p-5 relative overflow-hidden`}>
    <div className={`absolute left-0 top-0 bottom-0 w-1 ${
      accentColor || (trend === 'up' ? 'bg-emerald-400' : trend === 'down' ? 'bg-red-400' : 'bg-gray-200 dark:bg-slate-700')
    }`} />
    <div className="flex items-start justify-between">
      <div className="min-w-0">
        <p className="text-xs text-gray-500 dark:text-slate-400 font-medium uppercase tracking-wider">{title}</p>
        <p className="text-2xl font-bold text-gray-900 dark:text-slate-100 mt-1">{value}</p>
        {subtitle && <p className="text-sm text-gray-500 dark:text-slate-400 mt-0.5">{subtitle}</p>}
      </div>
      <div className={`p-2.5 rounded-lg flex-shrink-0 ${
        trend === 'up' ? 'bg-emerald-50 dark:bg-emerald-900/30' : trend === 'down' ? 'bg-red-50 dark:bg-red-900/30' : 'bg-gray-50 dark:bg-slate-900/50'
      }`}>
        <Icon className={`w-5 h-5 ${
          trend === 'up' ? 'text-emerald-600 dark:text-emerald-400' : trend === 'down' ? 'text-red-600 dark:text-red-400' : 'text-gray-400 dark:text-slate-500'
        }`} />
      </div>
    </div>
    {trendValue !== undefined && (
      <div className={`flex items-center gap-1 mt-2.5 text-sm ${trendValue >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
        {trendValue >= 0 ? <ArrowUpRight className="w-3.5 h-3.5" /> : <ArrowDownRight className="w-3.5 h-3.5" />}
        <span className="font-medium">{trendValue >= 0 ? '+' : ''}{trendValue.toFixed(2)}%</span>
        <span className="text-gray-400 dark:text-slate-500 ml-1">total return</span>
      </div>
    )}
  </div>
);

// ============================================================
// PORTFOLIO VALUE CHART
// ============================================================

const RANGE_OPTIONS = [
  { label: '1M', value: 30 },
  { label: '3M', value: 90 },
  { label: '6M', value: 180 },
  { label: 'YTD', value: 'ytd' },
  { label: 'All', value: 730 },
];

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-white/95 dark:bg-slate-800/95 backdrop-blur border border-gray-200 dark:border-slate-600 rounded-lg shadow-lg px-3 py-2 text-xs">
      <p className="font-semibold text-gray-700 dark:text-slate-300 mb-1">{d.date}</p>
      <div className="flex justify-between gap-4">
        <span className="text-gray-500 dark:text-slate-400">Value</span>
        <span className="font-semibold text-gray-900 dark:text-slate-100">{formatCurrency(d.portfolio_value)}</span>
      </div>
      {d.daily_change_pct != null && (
        <div className="flex justify-between gap-4">
          <span className="text-gray-500 dark:text-slate-400">Daily</span>
          <span className={`font-medium ${d.daily_change_pct >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
            {formatPct(d.daily_change_pct)}
          </span>
        </div>
      )}
      {d.transaction_type && (
        <div className="flex justify-between gap-4 mt-1 pt-1 border-t border-gray-100 dark:border-slate-700/50">
          <span className={d.transaction_type === 'Contribution' || d.transaction_type === 'Initial' ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}>
            {d.transaction_type === 'Initial' ? 'Initial Deposit' : d.transaction_type}
          </span>
          <span className="font-medium">{formatCurrency(d.transaction_amount)}</span>
        </div>
      )}
    </div>
  );
};

const PortfolioValueChart = () => {
  const { getAuthHeaders } = useAuth();
  const { darkMode } = useTheme();
  const [range, setRange] = useState(90);
  const [chartData, setChartData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const axisColor = darkMode ? '#94a3b8' : '#9ca3af';
  const gridColor = darkMode ? '#334155' : '#e5e7eb';

  // Compute actual days parameter
  const daysParam = useMemo(() => {
    if (range === 'ytd') {
      const now = new Date();
      const jan1 = new Date(now.getFullYear(), 0, 1);
      return Math.ceil((now - jan1) / (1000 * 60 * 60 * 24)) + 1;
    }
    return range;
  }, [range]);

  // Fetch chart data when range changes
  const getAuthRef = useRef(getAuthHeaders);
  getAuthRef.current = getAuthHeaders;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(false);

    (async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/investor/value-history?days=${daysParam}`, {
          headers: getAuthRef.current(),
        });
        if (!res.ok) throw new Error('Failed to fetch');
        const data = await res.json();
        if (!cancelled) {
          setChartData(data.history || []);
          setLoading(false);
        }
      } catch {
        if (!cancelled) {
          setError(true);
          setLoading(false);
        }
      }
    })();

    return () => { cancelled = true; };
  }, [daysParam]);

  const transactions = useMemo(() => {
    if (!chartData) return [];
    return chartData.filter(d => d.transaction_type);
  }, [chartData]);

  return (
    <div className="bg-white dark:bg-slate-800/50 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700/50 p-6 mb-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-slate-100">Your Portfolio Value</h3>
          <p className="text-sm text-gray-500 dark:text-slate-400">Account value over time</p>
        </div>
        <div className="flex gap-1">
          {RANGE_OPTIONS.map(opt => (
            <button
              key={opt.label}
              onClick={() => setRange(opt.value)}
              className={`px-3 py-1 rounded text-xs font-medium transition ${
                range === opt.value
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'bg-gray-100 dark:bg-slate-700 text-gray-600 dark:text-slate-300 hover:bg-gray-200 dark:hover:bg-slate-600'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="h-[300px] flex items-center justify-center">
          <Loader2 className="w-8 h-8 animate-spin text-emerald-400" />
        </div>
      ) : error || !chartData || chartData.length < 2 ? (
        <div className="h-[300px] flex flex-col items-center justify-center text-gray-400 dark:text-slate-500">
          <AlertCircle className="w-8 h-8 mb-2" />
          <p className="text-sm">{error ? 'Chart unavailable' : 'Not enough data for this range'}</p>
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={chartData} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
            <defs>
              <linearGradient id="portfolioGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#10b981" stopOpacity={0.3} />
                <stop offset="100%" stopColor="#10b981" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11, fill: axisColor }}
              tickLine={false}
              axisLine={{ stroke: gridColor }}
              tickFormatter={(v) => {
                const d = new Date(v + 'T00:00:00');
                return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
              }}
              minTickGap={40}
            />
            <YAxis
              tick={{ fontSize: 11, fill: axisColor }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
              domain={['auto', 'auto']}
              width={55}
            />
            <Tooltip content={<CustomTooltip />} />
            <Area
              type="monotone"
              dataKey="portfolio_value"
              stroke="#10b981"
              strokeWidth={2}
              fill="url(#portfolioGradient)"
              dot={false}
              activeDot={{ r: 4, stroke: '#10b981', strokeWidth: 2, fill: darkMode ? '#1e293b' : 'white' }}
            />
            {/* Transaction markers */}
            {transactions.map((tx, i) => (
              <ReferenceDot
                key={i}
                x={tx.date}
                y={tx.portfolio_value}
                r={5}
                fill={tx.transaction_type === 'Contribution' || tx.transaction_type === 'Initial' ? '#10b981' : '#ef4444'}
                stroke={darkMode ? '#1e293b' : 'white'}
                strokeWidth={2}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  );
};

// ============================================================
// PERFORMANCE PILLS
// ============================================================

const PerformancePills = () => {
  const { data: perf } = useApi('/nav/performance');
  const { data: nav } = useApi('/nav/current');

  if (!perf) return null;

  const monthReturn = perf.mtd_return;
  const sinceInception = perf.since_inception_return;

  const pills = [];

  // Monthly return
  if (monthReturn != null) {
    pills.push({
      text: `${monthReturn >= 0 ? 'Up' : 'Down'} ${Math.abs(monthReturn).toFixed(1)}% this month`,
      color: monthReturn >= 0 ? 'bg-emerald-50 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800' : 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300 border-red-200 dark:border-red-800',
    });
  }

  // Since inception
  if (sinceInception != null) {
    pills.push({
      text: `${sinceInception >= 0 ? '+' : ''}${sinceInception.toFixed(1)}% since inception`,
      color: sinceInception >= 0 ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-800' : 'bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800',
    });
  }

  // Trading days
  if (nav?.date) {
    const inception = new Date('2026-01-01');
    const today = new Date(nav.date);
    const days = Math.ceil((today - inception) / (1000 * 60 * 60 * 24));
    pills.push({
      text: `${days} days since launch`,
      color: 'bg-gray-50 dark:bg-slate-800 text-gray-600 dark:text-slate-400 border-gray-200 dark:border-slate-700',
    });
  }

  return (
    <div className="flex flex-wrap gap-2 mb-6">
      {pills.map((pill, i) => (
        <span
          key={i}
          className={`inline-flex items-center px-3 py-1.5 rounded-full text-xs font-semibold border ${pill.color}`}
        >
          {pill.text}
        </span>
      ))}
    </div>
  );
};

// ============================================================
// RECENT ACTIVITY
// ============================================================

const TransactionRow = ({ transaction }) => {
  const isMoneyIn = transaction.type === 'Contribution' || transaction.type === 'Initial';
  const displayType = transaction.type === 'Initial' ? 'Initial Deposit' : transaction.type;
  return (
    <div className="flex items-center justify-between py-3 border-b border-gray-100 dark:border-slate-700/50 last:border-0">
      <div className="flex items-center gap-3">
        <div className={`p-2 rounded-lg ${isMoneyIn ? 'bg-emerald-50 dark:bg-emerald-900/30' : 'bg-red-50 dark:bg-red-900/30'}`}>
          {isMoneyIn ?
            <ArrowDownRight className="w-4 h-4 text-emerald-600 dark:text-emerald-400" /> :
            <ArrowUpRight className="w-4 h-4 text-red-600 dark:text-red-400" />
          }
        </div>
        <div>
          <p className="font-medium text-gray-900 dark:text-slate-100 text-sm">{displayType}</p>
          <p className="text-xs text-gray-500 dark:text-slate-400">{transaction.date}</p>
        </div>
      </div>
      <div className="text-right">
        <p className={`font-semibold text-sm ${isMoneyIn ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
          {isMoneyIn ? '+' : '-'}${Math.abs(transaction.amount).toLocaleString('en-US', { minimumFractionDigits: 2 })}
        </p>
        <p className="text-xs text-gray-500 dark:text-slate-400">
          {transaction.shares.toFixed(4)} shares {isMoneyIn ? 'received' : 'redeemed'}
        </p>
      </div>
    </div>
  );
};

const RecentActivity = () => {
  const { data: transactions } = useApi('/investor/transactions?limit=5');

  return (
    <div className="bg-white dark:bg-slate-800/50 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700/50 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-slate-100">Recent Activity</h3>
        <Link
          to="/activity"
          className="text-sm text-emerald-600 dark:text-emerald-400 hover:text-emerald-700 dark:hover:text-emerald-300 font-medium flex items-center gap-1"
        >
          View All
          <ChevronRight className="w-4 h-4" />
        </Link>
      </div>

      {transactions?.transactions?.length > 0 ? (
        <div className="divide-y divide-gray-100 dark:divide-slate-700/50">
          {transactions.transactions.map((tx, i) => (
            <TransactionRow key={i} transaction={tx} />
          ))}
        </div>
      ) : (
        <div className="text-center py-8 text-gray-500 dark:text-slate-400">
          <Clock className="w-8 h-8 mx-auto mb-2 text-gray-300 dark:text-slate-600" />
          <p className="text-sm">No transactions yet</p>
        </div>
      )}

      {transactions && (
        <div className="mt-4 pt-3 border-t border-gray-100 dark:border-slate-700/50 text-xs text-gray-500 dark:text-slate-400">
          <div className="flex justify-between">
            <span>Total Contributions</span>
            <span className="text-emerald-600 dark:text-emerald-400 font-semibold">{formatCurrency(transactions.total_contributions)}</span>
          </div>
          <div className="flex justify-between mt-1">
            <span>Total Withdrawals</span>
            <span className="text-red-600 dark:text-red-400 font-semibold">{formatCurrency(transactions.total_withdrawals)}</span>
          </div>
        </div>
      )}
    </div>
  );
};

// ============================================================
// ACCOUNT SUMMARY
// ============================================================

const AccountSummary = ({ position, performance }) => {
  return (
    <div className="bg-white dark:bg-slate-800/50 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700/50 p-6">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-slate-100 mb-4">Account Summary</h3>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-[10px] text-gray-400 dark:text-slate-500 uppercase tracking-wider font-semibold">Net Investment</p>
          <p className="text-lg font-bold text-gray-900 dark:text-slate-100 mt-0.5">{formatCurrency(position?.net_investment)}</p>
        </div>
        <div>
          <p className="text-[10px] text-gray-400 dark:text-slate-500 uppercase tracking-wider font-semibold">Initial Capital</p>
          <p className="text-lg font-bold text-gray-900 dark:text-slate-100 mt-0.5">{formatCurrency(position?.initial_capital)}</p>
        </div>
        <div>
          <p className="text-[10px] text-gray-400 dark:text-slate-500 uppercase tracking-wider font-semibold">Current Shares</p>
          <p className="text-lg font-bold text-gray-900 dark:text-slate-100 mt-0.5">{position?.current_shares?.toLocaleString('en-US', { maximumFractionDigits: 4 }) || '--'}</p>
        </div>
        <div>
          <p className="text-[10px] text-gray-400 dark:text-slate-500 uppercase tracking-wider font-semibold">Avg Cost/Share</p>
          <p className="text-lg font-bold text-gray-900 dark:text-slate-100 mt-0.5">${position?.avg_cost_per_share?.toFixed(4) || '--'}</p>
        </div>
        <div>
          <p className="text-[10px] text-gray-400 dark:text-slate-500 uppercase tracking-wider font-semibold">Fund Size</p>
          <p className="text-lg font-bold text-gray-900 dark:text-slate-100 mt-0.5">{formatCurrency(performance?.total_portfolio_value)}</p>
        </div>
        <div>
          <p className="text-[10px] text-gray-400 dark:text-slate-500 uppercase tracking-wider font-semibold">Inception Date</p>
          <p className="text-lg font-bold text-gray-900 dark:text-slate-100 mt-0.5">{performance?.inception_date || '--'}</p>
        </div>
      </div>
    </div>
  );
};

// ============================================================
// DASHBOARD PAGE
// ============================================================

const DashboardPage = () => {
  const { user } = useAuth();
  const { data: position } = useApi('/investor/position');
  const { data: navData } = useApi('/nav/current');
  const { data: performance } = useApi('/nav/performance');

  const firstName = user?.name?.split(' ')[0] || 'Investor';

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 pb-20 lg:pb-8">
      {/* Welcome Banner */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-slate-100">{getGreeting()}, {firstName}</h2>
        <p className="text-gray-500 dark:text-slate-400 text-sm">{"Here's your portfolio overview as of "}{position?.as_of_date || 'today'}</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard
          title="Portfolio Value"
          value={formatCurrency(position?.current_value)}
          subtitle={`${position?.current_shares?.toLocaleString('en-US', { maximumFractionDigits: 4 }) || '--'} shares`}
          icon={DollarSign}
          trend={position?.total_return_percent >= 0 ? 'up' : 'down'}
          trendValue={position?.total_return_percent}
        />
        <StatCard
          title="Total Return"
          value={formatCurrency(position?.total_return_dollars)}
          subtitle={`${formatPct(position?.total_return_percent)} gain`}
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
          title="Avg Cost/Share"
          value={`$${position?.avg_cost_per_share?.toFixed(4) || '--'}`}
          subtitle="cost basis per share"
          icon={DollarSign}
          accentColor="bg-blue-400"
        />
      </div>

      {/* Performance Pills */}
      <PerformancePills />

      {/* Portfolio Value Chart */}
      <PortfolioValueChart />

      {/* Recent Activity + Account Summary side by side on desktop */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <RecentActivity />
        <AccountSummary position={position} performance={performance} />
      </div>
    </div>
  );
};

export default DashboardPage;
