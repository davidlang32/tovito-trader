import { useState, useMemo, useCallback } from 'react';
import {
  PieChart as PieChartIcon, Layers, BarChart3, AlertTriangle,
  ArrowUpRight, ArrowDownRight, Loader2, AlertCircle, ChevronUp, ChevronDown,
  TrendingUp, TrendingDown, Shield, Search, Info, Calendar, Clock
} from 'lucide-react';
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip as ReTooltip, Sector
} from 'recharts';
import { useApi } from '../hooks/useApi';
import { useTheme } from '../context/ThemeContext';

// ============================================================
// HELPERS
// ============================================================

const formatCurrency = (val) => {
  if (val === undefined || val === null) return '$--';
  return '$' + val.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

const formatCurrencyCompact = (val) => {
  if (val === undefined || val === null) return '$--';
  if (Math.abs(val) >= 1000000) return `$${(val / 1000000).toFixed(1)}M`;
  if (Math.abs(val) >= 1000) return `$${(val / 1000).toFixed(1)}k`;
  return `$${val.toFixed(2)}`;
};

const formatPct = (v) => v != null ? `${v >= 0 ? '+' : ''}${v.toFixed(2)}%` : '--';

// Consistent donut colors — vibrant, distinct, accessible
const DONUT_COLORS = [
  '#10b981', // emerald-500
  '#3b82f6', // blue-500
  '#f59e0b', // amber-500
  '#8b5cf6', // violet-500
  '#ef4444', // red-500
  '#ec4899', // pink-500
  '#06b6d4', // cyan-500
  '#f97316', // orange-500
  '#6366f1', // indigo-500
  '#84cc16', // lime-500
];

const TYPE_COLORS = {
  Stock: '#3b82f6',
  Equity: '#3b82f6',
  Option: '#8b5cf6',
  'Call Option': '#10b981',
  'Put Option': '#ef4444',
  Cash: '#6b7280',
  Other: '#9ca3af',
};

// ============================================================
// SECTION HEADER
// ============================================================

const SectionHeader = ({ icon: Icon, title, subtitle, iconColor = 'text-emerald-600', iconBg = 'bg-emerald-50' }) => (
  <div className="flex items-center gap-3 mb-5">
    <div className={`p-2 rounded-lg ${iconBg}`}>
      <Icon className={`w-5 h-5 ${iconColor}`} />
    </div>
    <div>
      <h3 className="text-lg font-semibold text-gray-900 dark:text-slate-100">{title}</h3>
      {subtitle && <p className="text-sm text-gray-500 dark:text-slate-400">{subtitle}</p>}
    </div>
  </div>
);

// ============================================================
// PORTFOLIO OVERVIEW CARDS
// ============================================================

const OverviewCard = ({ label, value, subtitle, icon: Icon, colorClass }) => (
  <div className="bg-white dark:bg-slate-800/50 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700/50 p-5 relative overflow-hidden">
    <div className={`absolute left-0 top-0 bottom-0 w-1 ${colorClass || 'bg-gray-200 dark:bg-slate-600'}`} />
    <div className="flex items-start justify-between">
      <div>
        <p className="text-xs text-gray-500 dark:text-slate-400 font-medium uppercase tracking-wider">{label}</p>
        <p className="text-2xl font-bold text-gray-900 dark:text-slate-100 mt-1">{value}</p>
        {subtitle && <p className="text-sm text-gray-500 dark:text-slate-400 mt-0.5">{subtitle}</p>}
      </div>
      {Icon && (
        <div className="p-2.5 rounded-lg bg-gray-50 dark:bg-slate-700 flex-shrink-0">
          <Icon className="w-5 h-5 text-gray-400 dark:text-slate-500" />
        </div>
      )}
    </div>
  </div>
);

const PortfolioOverview = ({ holdings, position }) => {
  const totalUnrealizedPl = holdings?.total_unrealized_pl || 0;
  const totalMarketValue = holdings?.total_market_value || 0;
  const unrealizedPct = totalMarketValue > 0
    ? (totalUnrealizedPl / (totalMarketValue - totalUnrealizedPl)) * 100
    : 0;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      <OverviewCard
        label="Total Market Value"
        value={formatCurrency(totalMarketValue)}
        subtitle={`${holdings?.position_count || 0} positions`}
        icon={Layers}
        colorClass="bg-blue-400"
      />
      <OverviewCard
        label="Unrealized P&L"
        value={formatCurrency(totalUnrealizedPl)}
        subtitle={formatPct(unrealizedPct)}
        icon={totalUnrealizedPl >= 0 ? TrendingUp : TrendingDown}
        colorClass={totalUnrealizedPl >= 0 ? 'bg-emerald-400' : 'bg-red-400'}
      />
      <OverviewCard
        label="Your Fund Share"
        value={`${position?.portfolio_percentage?.toFixed(1) || '--'}%`}
        subtitle={`${position?.current_shares?.toLocaleString('en-US', { maximumFractionDigits: 4 }) || '--'} shares`}
        icon={PieChartIcon}
        colorClass="bg-purple-400"
      />
      <OverviewCard
        label="As Of"
        value={holdings?.snapshot_date || '--'}
        subtitle="Latest snapshot"
        icon={BarChart3}
        colorClass="bg-gray-300"
      />
    </div>
  );
};

// ============================================================
// INTERACTIVE DONUT CHART (Allocation by Symbol)
// ============================================================

const AllocationDonut = ({ holdings }) => {
  const [activeIndex, setActiveIndex] = useState(0);
  const { darkMode } = useTheme();

  const renderActiveShape = useCallback((props) => {
    const {
      cx, cy, innerRadius, outerRadius, startAngle, endAngle,
      fill, payload, percent, value
    } = props;

    return (
      <g>
        <text x={cx} y={cy - 12} textAnchor="middle" fill={darkMode ? '#e2e8f0' : '#111827'} fontSize={18} fontWeight={700}>
          {payload.name}
        </text>
        <text x={cx} y={cy + 10} textAnchor="middle" fill={darkMode ? '#94a3b8' : '#6b7280'} fontSize={13}>
          {formatCurrencyCompact(value)}
        </text>
        <text x={cx} y={cy + 28} textAnchor="middle" fill={darkMode ? '#64748b' : '#9ca3af'} fontSize={11}>
          {(percent * 100).toFixed(1)}%
        </text>
        <Sector
          cx={cx} cy={cy}
          innerRadius={innerRadius}
          outerRadius={outerRadius + 8}
          startAngle={startAngle}
          endAngle={endAngle}
          fill={fill}
        />
        <Sector
          cx={cx} cy={cy}
          innerRadius={innerRadius - 4}
          outerRadius={innerRadius - 1}
          startAngle={startAngle}
          endAngle={endAngle}
          fill={fill}
        />
      </g>
    );
  }, [darkMode]);

  const chartData = useMemo(() => {
    if (!holdings?.by_symbol?.length) return [];
    return holdings.by_symbol.map((item, i) => ({
      name: item.name,
      value: item.value,
      color: DONUT_COLORS[i % DONUT_COLORS.length],
    }));
  }, [holdings]);

  if (!chartData.length) {
    return (
      <div className="h-[300px] flex items-center justify-center text-gray-400 dark:text-slate-500">
        <p className="text-sm">No holdings data available</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col lg:flex-row items-center gap-6">
      {/* Chart */}
      <div className="w-full lg:w-1/2" style={{ height: 300 }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={chartData}
              cx="50%"
              cy="50%"
              innerRadius={75}
              outerRadius={120}
              paddingAngle={2}
              dataKey="value"
              activeIndex={activeIndex}
              activeShape={renderActiveShape}
              onMouseEnter={(_, index) => setActiveIndex(index)}
            >
              {chartData.map((entry, i) => (
                <Cell key={i} fill={entry.color} stroke={darkMode ? '#1e293b' : 'white'} strokeWidth={2} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
      </div>

      {/* Legend */}
      <div className="w-full lg:w-1/2 space-y-2">
        {chartData.map((item, i) => {
          const totalValue = chartData.reduce((sum, d) => sum + d.value, 0);
          const pct = totalValue > 0 ? (item.value / totalValue * 100) : 0;

          return (
            <div
              key={item.name}
              className={`flex items-center gap-3 p-2 rounded-lg cursor-pointer transition ${
                activeIndex === i ? 'bg-gray-50 dark:bg-slate-700/50 shadow-sm' : 'hover:bg-gray-50 dark:hover:bg-slate-700/50'
              }`}
              onMouseEnter={() => setActiveIndex(i)}
            >
              <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ background: item.color }} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-gray-700 dark:text-slate-300 truncate">{item.name}</span>
                  <span className="text-sm font-bold text-gray-900 dark:text-slate-100 ml-2">{formatCurrencyCompact(item.value)}</span>
                </div>
                <div className="w-full bg-gray-100 dark:bg-slate-700 rounded-full h-1.5 mt-1">
                  <div
                    className="h-full rounded-full transition-all duration-300"
                    style={{ width: `${pct}%`, background: item.color }}
                  />
                </div>
              </div>
              <span className="text-xs text-gray-400 dark:text-slate-500 font-medium w-12 text-right">{pct.toFixed(1)}%</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ============================================================
// ALLOCATION BY TYPE (Stocks vs Options)
// ============================================================

const AllocationByType = ({ holdings }) => {
  const typeData = useMemo(() => {
    if (!holdings?.by_type) return [];
    const total = Object.values(holdings.by_type).reduce((s, v) => s + Math.abs(v), 0);
    return Object.entries(holdings.by_type)
      .map(([type, value]) => ({
        type,
        value: Math.abs(value),
        pct: total > 0 ? (Math.abs(value) / total * 100) : 0,
        color: TYPE_COLORS[type] || TYPE_COLORS.Other,
        isNegative: value < 0,
      }))
      .sort((a, b) => b.value - a.value);
  }, [holdings]);

  if (!typeData.length) return null;

  return (
    <div className="space-y-3">
      {typeData.map(item => (
        <div key={item.type}>
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-2">
              <div className="w-2.5 h-2.5 rounded-sm" style={{ background: item.color }} />
              <span className="text-sm font-medium text-gray-700 dark:text-slate-300">{item.type}</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-sm font-semibold text-gray-900 dark:text-slate-100">
                {item.isNegative ? '-' : ''}{formatCurrencyCompact(item.value)}
              </span>
              <span className="text-xs text-gray-400 dark:text-slate-500 w-12 text-right">{item.pct.toFixed(1)}%</span>
            </div>
          </div>
          <div className="w-full bg-gray-100 dark:bg-slate-700 rounded-full h-3 overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{ width: `${item.pct}%`, background: item.color, opacity: 0.85 }}
            />
          </div>
        </div>
      ))}
    </div>
  );
};

// ============================================================
// HOLDINGS TABLE (Sortable)
// ============================================================

const SORT_FIELDS = [
  { key: 'symbol', label: 'Symbol' },
  { key: 'market_value', label: 'Value' },
  { key: 'weight_pct', label: 'Weight' },
  { key: 'unrealized_pl', label: 'P&L ($)' },
  { key: 'unrealized_pl_pct', label: 'P&L (%)' },
  { key: 'cost_basis', label: 'Cost Basis' },
  { key: 'quantity', label: 'Qty' },
];

const HoldingsTable = ({ holdings }) => {
  const [sortBy, setSortBy] = useState('market_value');
  const [sortDir, setSortDir] = useState('desc');
  const [search, setSearch] = useState('');

  const sortedHoldings = useMemo(() => {
    if (!holdings?.holdings) return [];

    let filtered = holdings.holdings;

    // Filter by search
    if (search.trim()) {
      const q = search.toLowerCase();
      filtered = filtered.filter(h =>
        h.symbol.toLowerCase().includes(q) ||
        h.instrument_type.toLowerCase().includes(q)
      );
    }

    // Sort
    return [...filtered].sort((a, b) => {
      const aVal = a[sortBy] ?? 0;
      const bVal = b[sortBy] ?? 0;

      if (sortBy === 'symbol') {
        return sortDir === 'asc'
          ? String(aVal).localeCompare(String(bVal))
          : String(bVal).localeCompare(String(aVal));
      }

      return sortDir === 'asc' ? aVal - bVal : bVal - aVal;
    });
  }, [holdings, sortBy, sortDir, search]);

  const handleSort = (field) => {
    if (sortBy === field) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortDir('desc');
    }
  };

  const SortIcon = ({ field }) => {
    if (sortBy !== field) return <ChevronDown className="w-3 h-3 text-gray-300 dark:text-slate-600" />;
    return sortDir === 'asc'
      ? <ChevronUp className="w-3 h-3 text-gray-600 dark:text-slate-400" />
      : <ChevronDown className="w-3 h-3 text-gray-600 dark:text-slate-400" />;
  };

  return (
    <div className="bg-white dark:bg-slate-800/50 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700/50 p-6 mb-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-4 gap-3">
        <SectionHeader
          icon={Layers}
          title="All Holdings"
          subtitle={`${sortedHoldings.length} position${sortedHoldings.length !== 1 ? 's' : ''}`}
          iconColor="text-blue-600 dark:text-blue-400"
          iconBg="bg-blue-50 dark:bg-blue-900/30"
        />
        <div className="relative flex-shrink-0">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search holdings..."
            className="pl-8 pr-3 py-1.5 text-sm border border-gray-200 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200 dark:placeholder-slate-500 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent w-48"
          />
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[700px]">
          <thead>
            <tr className="border-b border-gray-100 dark:border-slate-700/50">
              {SORT_FIELDS.map(f => (
                <th
                  key={f.key}
                  onClick={() => handleSort(f.key)}
                  className={`text-left py-2.5 px-3 text-xs font-semibold uppercase tracking-wider cursor-pointer hover:bg-gray-50 dark:hover:bg-slate-700/50 transition select-none ${
                    f.key === 'symbol' ? '' : 'text-right'
                  } ${sortBy === f.key ? 'text-gray-700 dark:text-slate-300' : 'text-gray-400 dark:text-slate-500'}`}
                >
                  <div className={`flex items-center gap-1 ${f.key !== 'symbol' ? 'justify-end' : ''}`}>
                    {f.label}
                    <SortIcon field={f.key} />
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedHoldings.length === 0 ? (
              <tr>
                <td colSpan={SORT_FIELDS.length} className="text-center py-8 text-gray-400 dark:text-slate-500 text-sm">
                  {search ? 'No holdings match your search' : 'No holdings data available'}
                </td>
              </tr>
            ) : (
              sortedHoldings.map((h, i) => (
                <tr
                  key={`${h.symbol}-${i}`}
                  className="border-b border-gray-50 dark:border-slate-700/30 hover:bg-gray-50/50 dark:hover:bg-slate-700/30 transition"
                >
                  {/* Symbol */}
                  <td className="py-3 px-3">
                    <div className="flex items-center gap-2">
                      <div
                        className="w-2 h-8 rounded-full flex-shrink-0"
                        style={{ background: DONUT_COLORS[i % DONUT_COLORS.length] }}
                      />
                      <div>
                        <span className="font-semibold text-gray-900 dark:text-slate-100 text-sm">{h.symbol}</span>
                        <p className="text-[10px] text-gray-400 dark:text-slate-500">{h.instrument_type}</p>
                      </div>
                    </div>
                  </td>

                  {/* Market Value */}
                  <td className="py-3 px-3 text-right">
                    <span className="font-semibold text-gray-900 dark:text-slate-100 text-sm">{formatCurrency(h.market_value)}</span>
                  </td>

                  {/* Weight */}
                  <td className="py-3 px-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <div className="w-12 bg-gray-100 dark:bg-slate-700 rounded-full h-1.5 overflow-hidden">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${Math.min(h.weight_pct, 100)}%`,
                            background: DONUT_COLORS[i % DONUT_COLORS.length],
                          }}
                        />
                      </div>
                      <span className="text-sm text-gray-600 dark:text-slate-400 w-12 text-right">{h.weight_pct.toFixed(1)}%</span>
                    </div>
                  </td>

                  {/* Unrealized P&L ($) */}
                  <td className="py-3 px-3 text-right">
                    <span className={`font-semibold text-sm ${
                      (h.unrealized_pl || 0) >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'
                    }`}>
                      {h.unrealized_pl != null ? formatCurrency(h.unrealized_pl) : '--'}
                    </span>
                  </td>

                  {/* Unrealized P&L (%) */}
                  <td className="py-3 px-3 text-right">
                    <div className="flex items-center justify-end gap-1">
                      {h.unrealized_pl_pct != null && (
                        h.unrealized_pl_pct >= 0
                          ? <ArrowUpRight className="w-3 h-3 text-emerald-500" />
                          : <ArrowDownRight className="w-3 h-3 text-red-500" />
                      )}
                      <span className={`text-sm font-medium ${
                        (h.unrealized_pl_pct || 0) >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'
                      }`}>
                        {h.unrealized_pl_pct != null ? formatPct(h.unrealized_pl_pct) : '--'}
                      </span>
                    </div>
                  </td>

                  {/* Cost Basis */}
                  <td className="py-3 px-3 text-right">
                    <span className="text-sm text-gray-600 dark:text-slate-400">{h.cost_basis != null ? formatCurrency(h.cost_basis) : '--'}</span>
                  </td>

                  {/* Quantity */}
                  <td className="py-3 px-3 text-right">
                    <span className="text-sm text-gray-600 dark:text-slate-400 font-mono">
                      {h.quantity.toLocaleString('en-US', { maximumFractionDigits: 4 })}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Summary footer */}
      {holdings && sortedHoldings.length > 0 && (
        <div className="flex flex-wrap gap-6 mt-4 pt-3 border-t border-gray-100 dark:border-slate-700/50 text-xs text-gray-500 dark:text-slate-400">
          <div>
            <span>Total Value: </span>
            <span className="font-bold text-gray-700 dark:text-slate-300">{formatCurrency(holdings.total_market_value)}</span>
          </div>
          <div>
            <span>Total Unrealized: </span>
            <span className={`font-bold ${holdings.total_unrealized_pl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
              {formatCurrency(holdings.total_unrealized_pl)}
            </span>
          </div>
        </div>
      )}
    </div>
  );
};

// ============================================================
// CONCENTRATION ANALYSIS
// ============================================================

// Cash-equivalent symbols (money market funds, treasury ETFs, etc.)
const CASH_EQUIVALENTS = ['SGOV', 'BIL', 'SHV', 'SPAXX', 'FDRXX', 'VMFXX', 'CASH'];

const getDiversificationGrade = (hhi, holdings) => {
  // Check if the fund is sitting mostly in cash/cash-equivalents
  if (holdings?.holdings?.length > 0) {
    const totalValue = holdings.total_market_value || 0;
    if (totalValue > 0) {
      const cashValue = holdings.holdings
        .filter(h => {
          const sym = (h.symbol || '').toUpperCase();
          return CASH_EQUIVALENTS.includes(sym) || (h.instrument_type || '').toLowerCase() === 'cash';
        })
        .reduce((sum, h) => sum + Math.abs(h.market_value || 0), 0);
      const cashPct = (cashValue / totalValue) * 100;
      if (cashPct >= 60) {
        return {
          grade: '$',
          label: 'Sitting in Cash',
          color: 'text-blue-600 dark:text-blue-400',
          bg: 'bg-blue-50 dark:bg-blue-900/30',
          bar: '#3b82f6',
          isCash: true,
        };
      }
    }
  }

  if (hhi <= 1500) return { grade: 'A', label: 'Well Diversified', color: 'text-emerald-600 dark:text-emerald-400', bg: 'bg-emerald-50 dark:bg-emerald-900/30', bar: '#10b981' };
  if (hhi <= 2500) return { grade: 'B', label: 'Moderately Diversified', color: 'text-blue-600 dark:text-blue-400', bg: 'bg-blue-50 dark:bg-blue-900/30', bar: '#3b82f6' };
  if (hhi <= 4000) return { grade: 'C', label: 'Somewhat Concentrated', color: 'text-amber-600 dark:text-amber-400', bg: 'bg-amber-50 dark:bg-amber-900/30', bar: '#f59e0b' };
  if (hhi <= 6000) return { grade: 'D', label: 'Highly Concentrated', color: 'text-orange-600 dark:text-orange-400', bg: 'bg-orange-50 dark:bg-orange-900/30', bar: '#f97316' };
  return { grade: 'F', label: 'Very Concentrated', color: 'text-red-600 dark:text-red-400', bg: 'bg-red-50 dark:bg-red-900/30', bar: '#ef4444' };
};

const ConcentrationAnalysis = ({ holdings }) => {
  // Fetch historical performers (1 year + YTD ≈ 730 days)
  const { data: histPerformers } = useApi('/analysis/historical-performers?days=730');

  const analysis = useMemo(() => {
    if (!holdings?.holdings?.length) return null;

    const items = holdings.holdings;
    const total = holdings.total_market_value || 0;
    if (total <= 0) return null;

    // Sort by weight descending
    const sorted = [...items].sort((a, b) => (b.weight_pct || 0) - (a.weight_pct || 0));

    // Top holding
    const top1 = sorted[0];
    const top3Weight = sorted.slice(0, 3).reduce((s, h) => s + (h.weight_pct || 0), 0);
    const top5Weight = sorted.slice(0, 5).reduce((s, h) => s + (h.weight_pct || 0), 0);

    // Herfindahl-Hirschman Index (HHI)
    // Sum of squared weights (out of 100). <1500 = diversified, 1500-2500 = moderate, >2500 = concentrated
    const hhi = Math.round(items.reduce((sum, h) => sum + Math.pow(h.weight_pct || 0, 2), 0));

    // Best and worst performers
    const withPl = items.filter(h => h.unrealized_pl_pct != null);
    const bestPerformer = withPl.length > 0
      ? withPl.reduce((best, h) => (h.unrealized_pl_pct || 0) > (best.unrealized_pl_pct || 0) ? h : best)
      : null;
    const worstPerformer = withPl.length > 0
      ? withPl.reduce((worst, h) => (h.unrealized_pl_pct || 0) < (worst.unrealized_pl_pct || 0) ? h : worst)
      : null;

    const gradeInfo = getDiversificationGrade(hhi, holdings);

    return {
      top1,
      top3Weight,
      top5Weight,
      hhi,
      gradeInfo,
      positionCount: items.length,
      bestPerformer,
      worstPerformer,
    };
  }, [holdings]);

  if (!analysis) {
    return (
      <div className="bg-white dark:bg-slate-800/50 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700/50 p-6 mb-6">
        <SectionHeader
          icon={Shield}
          title="Portfolio Health"
          subtitle="Concentration and diversification analysis"
          iconColor="text-amber-600 dark:text-amber-400"
          iconBg="bg-amber-50 dark:bg-amber-900/30"
        />
        <div className="text-center py-8 text-gray-400 dark:text-slate-500 text-sm">Not enough data for analysis</div>
      </div>
    );
  }

  const { top1, top3Weight, top5Weight, hhi, gradeInfo, positionCount, bestPerformer, worstPerformer } = analysis;

  return (
    <div className="bg-white dark:bg-slate-800/50 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700/50 p-6 mb-6">
      <SectionHeader
        icon={Shield}
        title="Portfolio Health"
        subtitle="How concentrated or diversified the fund is"
        iconColor="text-amber-600 dark:text-amber-400"
        iconBg="bg-amber-50 dark:bg-amber-900/30"
      />

      {/* Diversification Grade */}
      <div className="flex items-center gap-4 mb-6 p-4 rounded-xl border border-gray-100 dark:border-slate-700/50 bg-gray-50/50 dark:bg-slate-800/50">
        <div className={`w-16 h-16 rounded-2xl flex items-center justify-center ${gradeInfo.bg}`}>
          <span className={`text-3xl font-black ${gradeInfo.color}`}>{gradeInfo.grade}</span>
        </div>
        <div className="flex-1">
          <p className={`text-sm font-bold ${gradeInfo.color}`}>{gradeInfo.label}</p>
          {gradeInfo.isCash ? (
            <p className="text-xs text-gray-500 dark:text-slate-400 mt-0.5">
              The fund is currently in cash or short-term treasuries collecting interest and waiting on the next big trade setup.
            </p>
          ) : (
            <>
              <p className="text-xs text-gray-500 dark:text-slate-400 mt-0.5">
                Concentration score: {hhi.toLocaleString()} / 10,000
              </p>
              <div className="w-full bg-gray-200 dark:bg-slate-600 rounded-full h-2 mt-2">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{ width: `${Math.min(hhi / 100, 100)}%`, background: gradeInfo.bar }}
                />
              </div>
              <div className="flex justify-between text-[10px] text-gray-400 dark:text-slate-500 mt-0.5">
                <span>Diversified</span>
                <span>Concentrated</span>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {/* Largest Holding */}
        <div className="p-3 rounded-xl bg-blue-50/50 dark:bg-blue-900/20 border border-blue-100 dark:border-blue-800">
          <p className="text-[10px] text-blue-500 dark:text-blue-400 font-semibold uppercase tracking-wider mb-1">Largest Position</p>
          <p className="text-lg font-bold text-gray-900 dark:text-slate-100">{top1?.symbol || '--'}</p>
          <p className="text-xs text-gray-500 dark:text-slate-400">{top1?.weight_pct?.toFixed(1) || '--'}% of portfolio</p>
        </div>

        {/* Top 3 */}
        <div className="p-3 rounded-xl bg-purple-50/50 dark:bg-purple-900/20 border border-purple-100 dark:border-purple-800">
          <p className="text-[10px] text-purple-500 dark:text-purple-400 font-semibold uppercase tracking-wider mb-1">Top 3 Holdings</p>
          <p className="text-lg font-bold text-gray-900 dark:text-slate-100">{top3Weight.toFixed(1)}%</p>
          <p className="text-xs text-gray-500 dark:text-slate-400">of total portfolio</p>
        </div>

        {/* Best Performer — historical */}
        <div className="p-3 rounded-xl bg-emerald-50/50 dark:bg-emerald-900/20 border border-emerald-100 dark:border-emerald-800">
          <p className="text-[10px] text-emerald-500 dark:text-emerald-400 font-semibold uppercase tracking-wider mb-1">Top Performer</p>
          {histPerformers?.top_performers?.length > 0 ? (
            <>
              <p className="text-lg font-bold text-emerald-700 dark:text-emerald-300">{histPerformers.top_performers[0].symbol}</p>
              <p className="text-xs text-emerald-600 dark:text-emerald-400">
                {histPerformers.top_performers[0].best_unrealized_pl_pct != null
                  ? formatPct(histPerformers.top_performers[0].best_unrealized_pl_pct)
                  : '--'}
              </p>
              <p className="text-[10px] text-gray-400 dark:text-slate-500 mt-0.5">
                Peak P&L (past year)
              </p>
            </>
          ) : (
            <>
              <p className="text-lg font-bold text-emerald-700 dark:text-emerald-300">{bestPerformer?.symbol || '--'}</p>
              <p className="text-xs text-emerald-600 dark:text-emerald-400">
                {bestPerformer ? formatPct(bestPerformer.unrealized_pl_pct) : '--'}
              </p>
            </>
          )}
        </div>

        {/* Worst Performer — historical */}
        <div className="p-3 rounded-xl bg-red-50/50 dark:bg-red-900/20 border border-red-100 dark:border-red-800">
          <p className="text-[10px] text-red-500 dark:text-red-400 font-semibold uppercase tracking-wider mb-1">Needs Attention</p>
          {histPerformers?.bottom_performers?.length > 0 ? (
            <>
              <p className="text-lg font-bold text-red-700 dark:text-red-300">{histPerformers.bottom_performers[0].symbol}</p>
              <p className="text-xs text-red-600 dark:text-red-400">
                {histPerformers.bottom_performers[0].worst_unrealized_pl_pct != null
                  ? formatPct(histPerformers.bottom_performers[0].worst_unrealized_pl_pct)
                  : '--'}
              </p>
              <p className="text-[10px] text-gray-400 dark:text-slate-500 mt-0.5">
                Worst P&L (past year)
              </p>
            </>
          ) : (
            <>
              <p className="text-lg font-bold text-red-700 dark:text-red-300">{worstPerformer?.symbol || '--'}</p>
              <p className="text-xs text-red-600 dark:text-red-400">
                {worstPerformer ? formatPct(worstPerformer.unrealized_pl_pct) : '--'}
              </p>
            </>
          )}
        </div>
      </div>

      {/* Historical Performers (expanded) */}
      {histPerformers?.top_performers?.length > 1 && (
        <div className="mt-4 p-4 rounded-xl border border-gray-100 dark:border-slate-700/50 bg-gray-50/50 dark:bg-slate-800/50">
          <div className="flex items-center gap-2 mb-3">
            <Clock className="w-4 h-4 text-gray-400 dark:text-slate-500" />
            <p className="text-xs font-bold text-gray-600 dark:text-slate-400 uppercase tracking-wider">
              All-Time Performers
              {histPerformers.period_start && histPerformers.period_end && (
                <span className="font-normal text-gray-400 dark:text-slate-500 normal-case ml-1">
                  ({histPerformers.period_start} to {histPerformers.period_end})
                </span>
              )}
            </p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {/* Top performers */}
            <div>
              <p className="text-[10px] text-emerald-500 dark:text-emerald-400 font-semibold uppercase tracking-wider mb-1.5">Best Trades</p>
              <div className="space-y-1.5">
                {histPerformers.top_performers.map((p, i) => (
                  <div key={p.symbol} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-bold text-gray-400 dark:text-slate-500 w-4">{i + 1}.</span>
                      <span className="text-sm font-semibold text-gray-700 dark:text-slate-300">{p.symbol}</span>
                    </div>
                    <span className="text-sm font-bold text-emerald-600 dark:text-emerald-400">
                      {p.best_unrealized_pl_pct != null ? formatPct(p.best_unrealized_pl_pct) : '--'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
            {/* Bottom performers */}
            <div>
              <p className="text-[10px] text-red-500 dark:text-red-400 font-semibold uppercase tracking-wider mb-1.5">Toughest Trades</p>
              <div className="space-y-1.5">
                {histPerformers.bottom_performers.map((p, i) => (
                  <div key={p.symbol} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-bold text-gray-400 dark:text-slate-500 w-4">{i + 1}.</span>
                      <span className="text-sm font-semibold text-gray-700 dark:text-slate-300">{p.symbol}</span>
                    </div>
                    <span className="text-sm font-bold text-red-600 dark:text-red-400">
                      {p.worst_unrealized_pl_pct != null ? formatPct(p.worst_unrealized_pl_pct) : '--'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SGOV / Cash Strategy Explanation */}
      {gradeInfo.isCash && (
        <div className="flex items-start gap-2 mt-4 p-4 bg-blue-50 dark:bg-blue-900/30 rounded-xl border border-blue-200 dark:border-blue-800">
          <Info className="w-4 h-4 text-blue-500 flex-shrink-0 mt-0.5" />
          <div className="text-[11px] text-blue-700 dark:text-blue-300 leading-relaxed">
            <p className="font-semibold text-blue-800 dark:text-blue-200 mb-1">Why is the fund in cash or SGOV?</p>
            <p>
              When market conditions are uncertain, sideways, or trending downward, the fund manager may
              move to a defensive position by holding cash or short-term Treasury ETFs like <strong>SGOV</strong> (iShares
              0-3 Month Treasury Bond ETF). This is a deliberate strategy to:
            </p>
            <ul className="list-disc ml-4 mt-1.5 space-y-0.5">
              <li>Protect your capital during volatile or declining markets</li>
              <li>Earn a small yield (~4-5% annualized) while waiting for better opportunities</li>
              <li>Avoid taking on unnecessary risk when the risk/reward ratio is unfavorable</li>
            </ul>
            <p className="mt-1.5">
              The fund will redeploy into equities and options when the manager identifies favorable trading conditions.
            </p>
          </div>
        </div>
      )}

      {/* Info note */}
      <div className="flex items-start gap-2 mt-4 p-3 bg-gray-50 dark:bg-slate-800 rounded-lg">
        <Info className="w-4 h-4 text-gray-400 dark:text-slate-500 flex-shrink-0 mt-0.5" />
        <p className="text-[11px] text-gray-500 dark:text-slate-400 leading-relaxed">
          The concentration score uses the Herfindahl-Hirschman Index (HHI). A lower score means the
          portfolio is spread across more positions, reducing risk. Scores below 1,500 indicate good
          diversification, while scores above 4,000 suggest the fund may be heavily weighted in just a
          few positions.
          {gradeInfo.isCash && ' When the fund is mostly in cash or treasury ETFs, the concentration metric is less relevant — the focus shifts to capital preservation.'}
        </p>
      </div>
    </div>
  );
};

// ============================================================
// PORTFOLIO PAGE
// ============================================================

const PortfolioPage = () => {
  const { data: holdings, loading: holdingsLoading, error: holdingsError } = useApi('/analysis/holdings');
  const { data: position } = useApi('/investor/position');

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 pb-20 lg:pb-8">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-slate-100">Fund Portfolio</h2>
        <p className="text-gray-500 dark:text-slate-400 text-sm">What the fund is invested in and how it's allocated</p>
      </div>

      {holdingsLoading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
        </div>
      ) : holdingsError ? (
        <div className="bg-white dark:bg-slate-800/50 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700/50 p-12 text-center">
          <AlertCircle className="w-10 h-10 text-gray-300 dark:text-slate-600 mx-auto mb-3" />
          <p className="text-gray-500 dark:text-slate-400">Unable to load portfolio data</p>
        </div>
      ) : (
        <>
          {/* 1. Overview Cards */}
          <PortfolioOverview holdings={holdings} position={position} />

          {/* 2. Allocation Charts (Donut + Type breakdown side by side) */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
            {/* Donut Chart - 2/3 width */}
            <div className="lg:col-span-2 bg-white dark:bg-slate-800/50 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700/50 p-6">
              <SectionHeader
                icon={PieChartIcon}
                title="Current Allocation by Position"
                subtitle="Where the fund is invested right now"
                iconColor="text-violet-600 dark:text-violet-400"
                iconBg="bg-violet-50 dark:bg-violet-900/30"
              />
              <AllocationDonut holdings={holdings} />
            </div>

            {/* Type Breakdown - 1/3 width */}
            <div className="bg-white dark:bg-slate-800/50 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700/50 p-6">
              <SectionHeader
                icon={BarChart3}
                title="By Asset Type"
                subtitle="Stocks, options, and more"
                iconColor="text-indigo-600 dark:text-indigo-400"
                iconBg="bg-indigo-50 dark:bg-indigo-900/30"
              />
              <AllocationByType holdings={holdings} />
            </div>
          </div>

          {/* 3. Holdings Table */}
          <HoldingsTable holdings={holdings} />

          {/* 4. Concentration Analysis */}
          <ConcentrationAnalysis holdings={holdings} />
        </>
      )}
    </div>
  );
};

export default PortfolioPage;
