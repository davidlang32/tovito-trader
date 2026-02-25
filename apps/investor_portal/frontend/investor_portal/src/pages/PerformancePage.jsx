import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import {
  TrendingUp, TrendingDown, ArrowUpRight, ArrowDownRight,
  ChevronDown, ChevronUp, Loader2, AlertCircle, Info, Award,
  Shield, Activity, BarChart3, Calendar, Target, Zap
} from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, Tooltip as ReTooltip,
  ResponsiveContainer, CartesianGrid, Legend
} from 'recharts';
import { createChart, AreaSeries, LineSeries } from 'lightweight-charts';
import { useAuth } from '../context/AuthContext';
import { useApi } from '../hooks/useApi';
import { API_BASE_URL } from '../config';

// ============================================================
// HELPERS
// ============================================================

const formatPct = (v) => v != null ? `${v >= 0 ? '+' : ''}${v.toFixed(2)}%` : '--';
const formatPctShort = (v) => v != null ? `${v >= 0 ? '+' : ''}${v.toFixed(1)}%` : '--';

// ============================================================
// SECTION HEADER
// ============================================================

const SectionHeader = ({ icon: Icon, title, subtitle, iconColor = 'text-emerald-600', iconBg = 'bg-emerald-50' }) => (
  <div className="flex items-center gap-3 mb-5">
    <div className={`p-2 rounded-lg ${iconBg}`}>
      <Icon className={`w-5 h-5 ${iconColor}`} />
    </div>
    <div>
      <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
      {subtitle && <p className="text-sm text-gray-500">{subtitle}</p>}
    </div>
  </div>
);

// ============================================================
// INTERACTIVE BENCHMARK CHART (TradingView Lightweight Charts)
// ============================================================

const CHART_RANGES = [
  { label: '30D', days: 30 },
  { label: '90D', days: 90 },
  { label: '6M', days: 180 },
  { label: '1Y', days: 365 },
  { label: 'All', days: 730 },
];

const CHART_COLORS = {
  fund: '#10b981',         // emerald-500 (the "star")
  fundArea: '#10b981',
  SPY: '#3b82f6',          // blue-500
  QQQ: '#a855f7',          // purple-500
  'BTC-USD': '#f59e0b',    // amber-500
};

const CHART_LABELS = {
  SPY: 'S&P 500',
  QQQ: 'Nasdaq 100',
  'BTC-USD': 'Bitcoin',
};

const BenchmarkChart = () => {
  const { getAuthHeaders } = useAuth();
  const chartContainerRef = useRef(null);
  const chartInstanceRef = useRef(null);
  const seriesRefs = useRef({});
  const [range, setRange] = useState(90);
  const [chartData, setChartData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [tooltip, setTooltip] = useState(null);
  const [visibleLines, setVisibleLines] = useState({
    fund: true,
    fundPct: true,
    SPY: true,
    QQQ: true,
    'BTC-USD': true,
  });

  const toggleLine = useCallback((key) => {
    setVisibleLines(prev => {
      const next = { ...prev, [key]: !prev[key] };
      // Apply visibility to existing series
      const ref = seriesRefs.current[key];
      if (ref) {
        ref.applyOptions({ visible: next[key] });
      }
      return next;
    });
  }, []);

  // Fetch data
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(false);

    (async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/nav/benchmark-data?days=${range}`, {
          headers: getAuthHeaders(),
        });
        if (!res.ok) throw new Error('Failed');
        const data = await res.json();
        if (!cancelled) {
          setChartData(data);
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
  }, [range, getAuthHeaders]);

  // Render chart
  useEffect(() => {
    if (!chartData || !chartContainerRef.current) return;

    // Clear previous chart
    if (chartInstanceRef.current) {
      chartInstanceRef.current.remove();
      chartInstanceRef.current = null;
    }

    const container = chartContainerRef.current;

    try {
      const chart = createChart(container, {
        layout: {
          background: { color: 'transparent' },
          textColor: '#9ca3af',
          fontFamily: 'Inter, system-ui, sans-serif',
          fontSize: 11,
        },
        grid: {
          vertLines: { color: 'rgba(229, 231, 235, 0.5)' },
          horzLines: { color: 'rgba(229, 231, 235, 0.5)' },
        },
        rightPriceScale: {
          borderVisible: false,
          scaleMargins: { top: 0.1, bottom: 0.1 },
        },
        leftPriceScale: {
          visible: true,
          borderVisible: false,
          scaleMargins: { top: 0.1, bottom: 0.1 },
        },
        timeScale: {
          borderVisible: false,
          timeVisible: false,
        },
        crosshair: {
          vertLine: { labelVisible: true },
          horzLine: { labelVisible: true },
        },
        handleScroll: true,
        handleScale: true,
        width: container.clientWidth,
        height: 380,
      });

      chartInstanceRef.current = chart;

      // Reset series refs
      seriesRefs.current = {};

      // Fund NAV area series (left price scale)
      const fundData = (chartData.fund || [])
        .map(d => ({
          time: d.date,
          value: d.nav_per_share,
        }))
        .filter(d => d.value != null);

      if (fundData.length > 0) {
        const navSeries = chart.addSeries(AreaSeries, {
          lineColor: CHART_COLORS.fund,
          topColor: 'rgba(16, 185, 129, 0.28)',
          bottomColor: 'rgba(16, 185, 129, 0.02)',
          lineWidth: 2,
          priceScaleId: 'left',
          title: 'NAV/Share',
          crosshairMarkerVisible: true,
          crosshairMarkerRadius: 4,
          visible: visibleLines.fund,
        });
        navSeries.setData(fundData);
        seriesRefs.current.fund = navSeries;
      }

      // Fund % change line (right price scale)
      const fundPctData = (chartData.fund || [])
        .map(d => ({ time: d.date, value: d.pct_change }))
        .filter(d => d.value != null);

      if (fundPctData.length > 0) {
        const fundLine = chart.addSeries(LineSeries, {
          color: CHART_COLORS.fund,
          lineWidth: 2,
          priceScaleId: 'right',
          title: 'Fund %',
          crosshairMarkerVisible: true,
          crosshairMarkerRadius: 3,
          priceFormat: { type: 'custom', formatter: (p) => `${p >= 0 ? '+' : ''}${p.toFixed(1)}%` },
          visible: visibleLines.fundPct,
        });
        fundLine.setData(fundPctData);
        seriesRefs.current.fundPct = fundLine;
      }

      // Benchmark lines (right price scale)
      const benchmarks = chartData.benchmarks || {};
      for (const [ticker, data] of Object.entries(benchmarks)) {
        const points = data
          .map(d => ({ time: d.date, value: d.pct_change }))
          .filter(d => d.value != null);

        if (points.length > 0) {
          const series = chart.addSeries(LineSeries, {
            color: CHART_COLORS[ticker] || '#9ca3af',
            lineWidth: 1.5,
            lineStyle: 0,
            priceScaleId: 'right',
            title: CHART_LABELS[ticker] || ticker,
            crosshairMarkerVisible: true,
            crosshairMarkerRadius: 3,
            priceFormat: { type: 'custom', formatter: (p) => `${p >= 0 ? '+' : ''}${p.toFixed(1)}%` },
            visible: visibleLines[ticker] !== false,
          });
          series.setData(points);
          seriesRefs.current[ticker] = series;
        }
      }

      chart.timeScale().fitContent();

      // Responsive resize
      const resizeObserver = new ResizeObserver(() => {
        if (chartInstanceRef.current && container) {
          chart.applyOptions({ width: container.clientWidth });
        }
      });
      resizeObserver.observe(container);

      return () => {
        resizeObserver.disconnect();
      };
    } catch (err) {
      console.error('Chart render error:', err);
      setError(true);
    }
  }, [chartData]); // eslint-disable-line react-hooks/exhaustive-deps
  // Note: visibleLines changes are handled via seriesRefs (no chart rebuild needed)

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (chartInstanceRef.current) {
        chartInstanceRef.current.remove();
        chartInstanceRef.current = null;
      }
    };
  }, []);

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-4 gap-3">
        <SectionHeader
          icon={TrendingUp}
          title="Fund vs Benchmarks"
          subtitle="How Tovito Trader compares to major indexes"
        />
        <div className="flex gap-1 flex-shrink-0">
          {CHART_RANGES.map(opt => (
            <button
              key={opt.label}
              onClick={() => setRange(opt.days)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                range === opt.days
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Legend bar — clickable toggles */}
      <div className="flex flex-wrap gap-2 mb-3 text-xs">
        <button
          onClick={() => toggleLine('fund')}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border transition ${
            visibleLines.fund
              ? 'border-emerald-200 bg-emerald-50'
              : 'border-gray-200 bg-gray-50 opacity-50'
          }`}
        >
          <div className="w-3 h-3 rounded-full" style={{ background: CHART_COLORS.fund }} />
          <span className={visibleLines.fund ? 'text-gray-700 font-medium' : 'text-gray-400 line-through'}>NAV Mountain</span>
        </button>
        <button
          onClick={() => toggleLine('fundPct')}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border transition ${
            visibleLines.fundPct
              ? 'border-emerald-200 bg-emerald-50'
              : 'border-gray-200 bg-gray-50 opacity-50'
          }`}
        >
          <div className="w-3 h-0.5 rounded" style={{ background: CHART_COLORS.fund, width: 12 }} />
          <span className={visibleLines.fundPct ? 'text-gray-700 font-medium' : 'text-gray-400 line-through'}>Fund %</span>
        </button>
        <button
          onClick={() => toggleLine('SPY')}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border transition ${
            visibleLines.SPY
              ? 'border-blue-200 bg-blue-50'
              : 'border-gray-200 bg-gray-50 opacity-50'
          }`}
        >
          <div className="w-3 h-0.5 rounded" style={{ background: CHART_COLORS.SPY, width: 12 }} />
          <span className={visibleLines.SPY ? 'text-gray-700' : 'text-gray-400 line-through'}>S&P 500</span>
        </button>
        <button
          onClick={() => toggleLine('QQQ')}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border transition ${
            visibleLines.QQQ
              ? 'border-purple-200 bg-purple-50'
              : 'border-gray-200 bg-gray-50 opacity-50'
          }`}
        >
          <div className="w-3 h-0.5 rounded" style={{ background: CHART_COLORS.QQQ, width: 12 }} />
          <span className={visibleLines.QQQ ? 'text-gray-700' : 'text-gray-400 line-through'}>Nasdaq 100</span>
        </button>
        <button
          onClick={() => toggleLine('BTC-USD')}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border transition ${
            visibleLines['BTC-USD']
              ? 'border-amber-200 bg-amber-50'
              : 'border-gray-200 bg-gray-50 opacity-50'
          }`}
        >
          <div className="w-3 h-0.5 rounded" style={{ background: CHART_COLORS['BTC-USD'], width: 12 }} />
          <span className={visibleLines['BTC-USD'] ? 'text-gray-700' : 'text-gray-400 line-through'}>Bitcoin</span>
        </button>
      </div>

      {loading ? (
        <div className="h-[380px] flex items-center justify-center">
          <Loader2 className="w-8 h-8 animate-spin text-emerald-400" />
        </div>
      ) : error ? (
        <div className="h-[380px] flex flex-col items-center justify-center text-gray-400">
          <AlertCircle className="w-8 h-8 mb-2" />
          <p className="text-sm">Chart unavailable</p>
          <button
            onClick={() => setRange(90)}
            className="mt-2 text-xs text-emerald-600 hover:underline"
          >
            Try 90-day range
          </button>
        </div>
      ) : (
        <div ref={chartContainerRef} className="w-full" style={{ height: 380 }} />
      )}

      <div className="flex items-start gap-2 mt-3 p-3 bg-gray-50 rounded-lg">
        <Info className="w-4 h-4 text-gray-400 flex-shrink-0 mt-0.5" />
        <div className="text-[11px] text-gray-500 leading-relaxed">
          <p>
            <strong>Left axis (green area):</strong> NAV per share — the actual price of one fund share over time.
            This is not your contributions — it shows how the fund's value per share has grown or declined.
          </p>
          <p className="mt-1">
            <strong>Right axis (colored lines):</strong> Percentage change from the start of the selected period,
            comparing the fund against major benchmarks.
          </p>
        </div>
      </div>
    </div>
  );
};

// ============================================================
// BENCHMARK COMPARISON CARDS ("How We Compare")
// ============================================================

const COMPARISON_RANGES = [
  { label: '30D', days: 30 },
  { label: '90D', days: 90 },
  { label: '6M', days: 180 },
  { label: 'YTD', days: 'ytd' },
  { label: 'All', days: 730 },
];

const ComparisonCard = ({ ticker, label, fundReturn, benchReturn, outperformance }) => {
  const winning = outperformance >= 0;
  const color = CHART_COLORS[ticker] || '#6b7280';

  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-5 hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />
          <span className="text-sm font-semibold text-gray-700">{label}</span>
          <span className="text-xs text-gray-400 font-mono">{ticker}</span>
        </div>
        {winning ? (
          <span className="px-2 py-0.5 bg-emerald-50 text-emerald-700 rounded-full text-[10px] font-bold uppercase tracking-wider">
            Beating
          </span>
        ) : (
          <span className="px-2 py-0.5 bg-amber-50 text-amber-700 rounded-full text-[10px] font-bold uppercase tracking-wider">
            Trailing
          </span>
        )}
      </div>

      {/* Visual bar comparison */}
      <div className="space-y-2 mb-3">
        <div>
          <div className="flex justify-between text-xs mb-0.5">
            <span className="text-gray-500">Tovito</span>
            <span className={`font-semibold ${fundReturn >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
              {formatPct(fundReturn)}
            </span>
          </div>
          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${Math.min(Math.max(Math.abs(fundReturn) * 3, 5), 100)}%`,
                background: fundReturn >= 0 ? '#10b981' : '#ef4444',
              }}
            />
          </div>
        </div>
        <div>
          <div className="flex justify-between text-xs mb-0.5">
            <span className="text-gray-500">{label}</span>
            <span className={`font-semibold ${benchReturn >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
              {formatPct(benchReturn)}
            </span>
          </div>
          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${Math.min(Math.max(Math.abs(benchReturn) * 3, 5), 100)}%`,
                background: color,
                opacity: 0.7,
              }}
            />
          </div>
        </div>
      </div>

      {/* Outperformance callout */}
      <div className={`text-center py-2 rounded-lg ${
        winning ? 'bg-emerald-50' : 'bg-amber-50'
      }`}>
        <span className={`text-lg font-bold ${winning ? 'text-emerald-700' : 'text-amber-700'}`}>
          {winning ? '+' : ''}{outperformance.toFixed(2)}%
        </span>
        <p className={`text-[10px] ${winning ? 'text-emerald-600' : 'text-amber-600'}`}>
          {winning ? 'ahead' : 'behind'}
        </p>
      </div>
    </div>
  );
};

const BenchmarkComparison = () => {
  const { getAuthHeaders } = useAuth();
  const [range, setRange] = useState(90);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const daysParam = useMemo(() => {
    if (range === 'ytd') {
      const now = new Date();
      const jan1 = new Date(now.getFullYear(), 0, 1);
      return Math.ceil((now - jan1) / (1000 * 60 * 60 * 24)) + 1;
    }
    return range;
  }, [range]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    (async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/analysis/benchmark-comparison?days=${daysParam}`, {
          headers: getAuthHeaders(),
        });
        if (!res.ok) throw new Error('Failed');
        const json = await res.json();
        if (!cancelled) {
          setData(json);
          setLoading(false);
        }
      } catch {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => { cancelled = true; };
  }, [daysParam, getAuthHeaders]);

  return (
    <div className="mb-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-4 gap-3">
        <SectionHeader
          icon={Target}
          title="How We Compare"
          subtitle="Tovito Trader vs major benchmarks"
          iconColor="text-blue-600"
          iconBg="bg-blue-50"
        />
        <div className="flex gap-1 flex-shrink-0">
          {COMPARISON_RANGES.map(opt => (
            <button
              key={opt.label}
              onClick={() => setRange(opt.days)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                range === opt.days
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="h-32 flex items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-blue-400" />
        </div>
      ) : data?.comparisons?.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {data.comparisons.map(c => (
            <ComparisonCard
              key={c.ticker}
              ticker={c.ticker}
              label={c.label}
              fundReturn={c.fund_return}
              benchReturn={c.benchmark_return}
              outperformance={c.outperformance}
            />
          ))}
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-100 p-8 text-center text-gray-400">
          <p className="text-sm">Not enough data for comparison</p>
        </div>
      )}
    </div>
  );
};

// ============================================================
// MONTHLY RETURNS HEATMAP
// ============================================================

const getMonthColor = (returnPct) => {
  if (returnPct === null || returnPct === undefined) return 'bg-gray-50 text-gray-400';
  if (returnPct >= 5) return 'bg-emerald-500 text-white';
  if (returnPct >= 3) return 'bg-emerald-400 text-white';
  if (returnPct >= 1) return 'bg-emerald-300 text-emerald-900';
  if (returnPct >= 0) return 'bg-emerald-100 text-emerald-800';
  if (returnPct >= -1) return 'bg-red-100 text-red-800';
  if (returnPct >= -3) return 'bg-red-300 text-red-900';
  if (returnPct >= -5) return 'bg-red-400 text-white';
  return 'bg-red-500 text-white';
};

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

const MonthlyHeatmap = () => {
  const { data, loading, error } = useApi('/analysis/monthly-performance');

  // Group months by year
  const yearGrid = useMemo(() => {
    if (!data?.months) return {};

    const grid = {};
    for (const m of data.months) {
      const [year, month] = m.month.split('-');
      if (!grid[year]) grid[year] = {};
      grid[year][parseInt(month, 10)] = m;
    }
    return grid;
  }, [data]);

  const years = Object.keys(yearGrid).sort();

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-6">
      <SectionHeader
        icon={Calendar}
        title="Monthly Returns"
        subtitle="Performance by month at a glance"
        iconColor="text-purple-600"
        iconBg="bg-purple-50"
      />

      {loading ? (
        <div className="h-24 flex items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-purple-400" />
        </div>
      ) : !data?.months?.length ? (
        <div className="text-center py-8 text-gray-400 text-sm">No monthly data available</div>
      ) : (
        <>
          {/* Heatmap grid */}
          <div className="overflow-x-auto">
            <table className="w-full min-w-[600px]">
              <thead>
                <tr>
                  <th className="text-xs text-gray-400 font-medium text-left py-2 w-16" />
                  {MONTH_NAMES.map(m => (
                    <th key={m} className="text-xs text-gray-400 font-medium text-center py-2 px-1">{m}</th>
                  ))}
                  <th className="text-xs text-gray-400 font-medium text-center py-2 px-2">Year</th>
                </tr>
              </thead>
              <tbody>
                {years.map(year => {
                  // Compute year total
                  const monthsInYear = Object.values(yearGrid[year]);
                  let yearReturn = 0;
                  if (monthsInYear.length > 0) {
                    // Compound monthly returns
                    let cumulative = 1;
                    monthsInYear.sort((a, b) => a.month.localeCompare(b.month));
                    for (const m of monthsInYear) {
                      cumulative *= (1 + m.return_pct / 100);
                    }
                    yearReturn = (cumulative - 1) * 100;
                  }

                  return (
                    <tr key={year}>
                      <td className="text-xs font-semibold text-gray-600 py-1">{year}</td>
                      {Array.from({ length: 12 }, (_, i) => {
                        const monthData = yearGrid[year]?.[i + 1];
                        const ret = monthData?.return_pct;

                        return (
                          <td key={i} className="p-0.5 text-center">
                            {monthData ? (
                              <div className={`rounded-lg py-2.5 px-1 text-xs font-bold ${getMonthColor(ret)} transition-all hover:scale-105 cursor-default`}
                                title={`${MONTH_NAMES[i]} ${year}: ${formatPct(ret)}\nNAV: $${monthData.start_nav.toFixed(4)} -> $${monthData.end_nav.toFixed(4)}\nTrading Days: ${monthData.trading_days}`}
                              >
                                {formatPctShort(ret)}
                              </div>
                            ) : (
                              <div className="rounded-lg py-2.5 px-1 text-xs text-gray-300 bg-gray-50">
                                --
                              </div>
                            )}
                          </td>
                        );
                      })}
                      <td className="p-0.5 text-center">
                        <div className={`rounded-lg py-2.5 px-2 text-xs font-bold ${getMonthColor(yearReturn)}`}>
                          {formatPctShort(yearReturn)}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Color legend */}
          <div className="flex items-center justify-center gap-1 mt-4 text-[10px] text-gray-400">
            <span>Loss</span>
            <div className="flex gap-0.5">
              <div className="w-5 h-3 rounded bg-red-500" />
              <div className="w-5 h-3 rounded bg-red-400" />
              <div className="w-5 h-3 rounded bg-red-300" />
              <div className="w-5 h-3 rounded bg-red-100" />
              <div className="w-5 h-3 rounded bg-emerald-100" />
              <div className="w-5 h-3 rounded bg-emerald-300" />
              <div className="w-5 h-3 rounded bg-emerald-400" />
              <div className="w-5 h-3 rounded bg-emerald-500" />
            </div>
            <span>Gain</span>
          </div>

          {/* Best/Worst summary */}
          {data.best_month && (
            <div className="flex flex-wrap gap-4 justify-center mt-3">
              <span className="inline-flex items-center gap-1 text-xs">
                <Award className="w-3.5 h-3.5 text-emerald-500" />
                <span className="text-gray-500">Best month:</span>
                <span className="font-bold text-emerald-600">{data.best_month} ({formatPct(data.best_month_return)})</span>
              </span>
              <span className="inline-flex items-center gap-1 text-xs">
                <span className="text-gray-500">Toughest month:</span>
                <span className="font-bold text-red-600">{data.worst_month} ({formatPct(data.worst_month_return)})</span>
              </span>
            </div>
          )}
        </>
      )}
    </div>
  );
};

// ============================================================
// ROLLING RETURNS CHART (Recharts)
// ============================================================

const RollingReturnsTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  if (!d) return null;

  return (
    <div className="bg-white/95 backdrop-blur border border-gray-200 rounded-lg shadow-lg px-3 py-2 text-xs">
      <p className="font-semibold text-gray-700 mb-1">{d.date}</p>
      {d.rolling_30d != null && (
        <div className="flex justify-between gap-4">
          <span className="text-blue-500 font-medium">30-Day</span>
          <span className={`font-bold ${d.rolling_30d >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
            {formatPct(d.rolling_30d)}
          </span>
        </div>
      )}
      {d.rolling_90d != null && (
        <div className="flex justify-between gap-4">
          <span className="text-purple-500 font-medium">90-Day</span>
          <span className={`font-bold ${d.rolling_90d >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
            {formatPct(d.rolling_90d)}
          </span>
        </div>
      )}
    </div>
  );
};

const RollingReturnsChart = () => {
  const { data, loading, error } = useApi('/analysis/rolling-returns?days=365');

  // Downsample for performance (show every Nth point if >200 points)
  const chartData = useMemo(() => {
    if (!data?.data) return [];
    const raw = data.data;
    if (raw.length <= 200) return raw;
    const step = Math.ceil(raw.length / 200);
    const sampled = raw.filter((_, i) => i % step === 0);
    // Always include last point
    if (sampled[sampled.length - 1] !== raw[raw.length - 1]) {
      sampled.push(raw[raw.length - 1]);
    }
    return sampled;
  }, [data]);

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-6">
      <SectionHeader
        icon={Activity}
        title="Rolling Returns"
        subtitle="How returns look over sliding 30-day and 90-day windows"
        iconColor="text-indigo-600"
        iconBg="bg-indigo-50"
      />

      {loading ? (
        <div className="h-[260px] flex items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-indigo-400" />
        </div>
      ) : chartData.length < 2 ? (
        <div className="h-[260px] flex items-center justify-center text-gray-400 text-sm">
          Not enough data for rolling returns
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={chartData} margin={{ top: 5, right: 10, bottom: 5, left: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10, fill: '#9ca3af' }}
              tickLine={false}
              axisLine={{ stroke: '#e5e7eb' }}
              tickFormatter={(v) => {
                const d = new Date(v + 'T00:00:00');
                return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
              }}
              minTickGap={50}
            />
            <YAxis
              tick={{ fontSize: 10, fill: '#9ca3af' }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => `${v >= 0 ? '+' : ''}${v.toFixed(0)}%`}
              width={45}
            />
            <ReTooltip content={<RollingReturnsTooltip />} />
            {/* Zero reference line */}
            <CartesianGrid horizontal={false} vertical={false} />
            <Line
              type="monotone"
              dataKey="rolling_30d"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={false}
              name="30-Day Return"
              connectNulls={false}
            />
            <Line
              type="monotone"
              dataKey="rolling_90d"
              stroke="#a855f7"
              strokeWidth={2}
              dot={false}
              name="90-Day Return"
              connectNulls={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}

      <div className="flex items-center justify-center gap-6 mt-2 text-xs">
        <div className="flex items-center gap-1.5">
          <div className="w-4 h-0.5 rounded bg-blue-500" />
          <span className="text-gray-500">30-Day Rolling</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-4 h-0.5 rounded bg-purple-500" />
          <span className="text-gray-500">90-Day Rolling</span>
        </div>
      </div>
    </div>
  );
};

// ============================================================
// RISK & REWARD SNAPSHOT (Plain-English Labels with Tooltips)
// ============================================================

const InfoTooltip = ({ text }) => {
  const [show, setShow] = useState(false);

  return (
    <span className="relative inline-block">
      <Info
        className="w-3.5 h-3.5 text-gray-300 hover:text-gray-500 cursor-help transition"
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
        onClick={() => setShow(!show)}
      />
      {show && (
        <span className="absolute z-10 bottom-full left-1/2 -translate-x-1/2 mb-1.5 w-48 bg-gray-800 text-white text-[10px] leading-snug p-2 rounded-lg shadow-lg pointer-events-none">
          {text}
          <span className="absolute top-full left-1/2 -translate-x-1/2 -mt-px border-4 border-transparent border-t-gray-800" />
        </span>
      )}
    </span>
  );
};

const RISK_METRIC_CONFIGS = [
  {
    key: 'total_return_pct',
    label: 'Total Return',
    description: 'How much the fund has grown overall since inception.',
    icon: TrendingUp,
    format: (v) => formatPct(v),
    color: (v) => v >= 0 ? 'text-emerald-600' : 'text-red-600',
    iconColor: (v) => v >= 0 ? 'bg-emerald-50 text-emerald-600' : 'bg-red-50 text-red-600',
  },
  {
    key: 'sharpe_ratio',
    label: 'Risk-Adjusted Score',
    description: 'Higher is better. Measures how much return we get for each unit of risk taken. Above 1.0 is good, above 2.0 is excellent.',
    icon: Award,
    format: (v) => v != null ? v.toFixed(2) : 'N/A',
    color: (v) => v >= 2 ? 'text-emerald-600' : v >= 1 ? 'text-blue-600' : v >= 0 ? 'text-amber-600' : 'text-red-600',
    iconColor: (v) => v >= 1 ? 'bg-emerald-50 text-emerald-600' : 'bg-amber-50 text-amber-600',
  },
  {
    key: 'max_drawdown_pct',
    label: 'Largest Dip',
    description: 'The biggest peak-to-trough drop in fund value. Smaller is better. Shows the worst-case scenario so far.',
    icon: Shield,
    format: (v) => v != null ? `${v.toFixed(2)}%` : '--',
    color: (v) => Math.abs(v) <= 3 ? 'text-emerald-600' : Math.abs(v) <= 10 ? 'text-amber-600' : 'text-red-600',
    iconColor: () => 'bg-blue-50 text-blue-600',
  },
  {
    key: 'annualized_volatility_pct',
    label: 'Price Swing Level',
    description: 'How much the fund value bounces around day to day. Lower means smoother returns.',
    icon: Activity,
    format: (v) => v != null ? `${v.toFixed(1)}%` : '--',
    color: (v) => v <= 10 ? 'text-emerald-600' : v <= 20 ? 'text-amber-600' : 'text-red-600',
    iconColor: () => 'bg-purple-50 text-purple-600',
  },
  {
    key: 'win_rate_pct',
    label: 'Winning Days',
    description: 'Percentage of trading days where the fund went up. Above 50% means more good days than bad.',
    icon: Zap,
    format: (v) => v != null ? `${v.toFixed(0)}%` : '--',
    color: (v) => v >= 55 ? 'text-emerald-600' : v >= 45 ? 'text-blue-600' : 'text-red-600',
    iconColor: (v) => v >= 50 ? 'bg-emerald-50 text-emerald-600' : 'bg-amber-50 text-amber-600',
  },
  {
    key: 'best_day_pct',
    label: 'Best Day',
    description: 'The single best trading day in the period. Shows peak upside potential.',
    icon: ArrowUpRight,
    format: (v) => formatPct(v),
    color: () => 'text-emerald-600',
    iconColor: () => 'bg-emerald-50 text-emerald-600',
    subKey: 'best_day_date',
  },
  {
    key: 'worst_day_pct',
    label: 'Toughest Day',
    description: 'The single worst trading day. Shows the largest single-day decline.',
    icon: ArrowDownRight,
    format: (v) => formatPct(v),
    color: () => 'text-red-600',
    iconColor: () => 'bg-red-50 text-red-600',
    subKey: 'worst_day_date',
  },
  {
    key: 'annualized_return_pct',
    label: 'Yearly Pace',
    description: 'If the current performance continued for a full year, this is the return you would see. Annualized from actual trading days.',
    icon: BarChart3,
    format: (v) => formatPct(v),
    color: (v) => v >= 0 ? 'text-emerald-600' : 'text-red-600',
    iconColor: (v) => v >= 0 ? 'bg-emerald-50 text-emerald-600' : 'bg-red-50 text-red-600',
  },
];

const RiskMetricCard = ({ config, data }) => {
  const value = data?.[config.key];
  const Icon = config.icon;
  const subDate = config.subKey ? data?.[config.subKey] : null;

  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-2">
        <div className={`p-2 rounded-lg ${config.iconColor(value)}`}>
          <Icon className="w-4 h-4" />
        </div>
        <InfoTooltip text={config.description} />
      </div>
      <p className={`text-2xl font-bold ${config.color(value)} mt-1`}>
        {config.format(value)}
      </p>
      <p className="text-xs text-gray-500 mt-1 font-medium">{config.label}</p>
      {subDate && (
        <p className="text-[10px] text-gray-400 mt-0.5">{subDate}</p>
      )}
    </div>
  );
};

const RiskRewardSnapshot = () => {
  const { data, loading, error } = useApi('/analysis/risk-metrics?days=730');

  return (
    <div className="mb-6">
      <SectionHeader
        icon={Shield}
        title="Risk & Reward Snapshot"
        subtitle="Key numbers explained in plain English"
        iconColor="text-amber-600"
        iconBg="bg-amber-50"
      />

      {loading ? (
        <div className="h-32 flex items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-amber-400" />
        </div>
      ) : !data ? (
        <div className="bg-white rounded-xl border border-gray-100 p-8 text-center text-gray-400 text-sm">
          Risk metrics unavailable
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {RISK_METRIC_CONFIGS.map(config => (
              <RiskMetricCard key={config.key} config={config} data={data} />
            ))}
          </div>

          {/* Period footer */}
          <p className="text-[10px] text-gray-400 mt-3 text-center">
            Based on {data.trading_days} trading days ({data.period_start} to {data.period_end})
          </p>
        </>
      )}
    </div>
  );
};

// ============================================================
// PERFORMANCE PAGE
// ============================================================

const PerformancePage = () => {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 pb-20 lg:pb-8">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900">Performance</h2>
        <p className="text-gray-500 text-sm">How your money is growing and how we stack up</p>
      </div>

      {/* 1. Interactive Benchmark Chart */}
      <BenchmarkChart />

      {/* 2. How We Compare Cards */}
      <BenchmarkComparison />

      {/* 3. Monthly Returns Heatmap */}
      <MonthlyHeatmap />

      {/* 4. Rolling Returns Chart */}
      <RollingReturnsChart />

      {/* 5. Risk & Reward Snapshot */}
      <RiskRewardSnapshot />
    </div>
  );
};

export default PerformancePage;
