import { useState, useEffect, useMemo, useCallback } from 'react';
import {
  ArrowDownRight, ArrowUpRight, Clock, CheckCircle2, AlertCircle,
  Loader2, ChevronDown, ChevronUp, ChevronLeft, ChevronRight,
  DollarSign, TrendingUp, TrendingDown, Filter, XCircle,
  ArrowLeftRight, Calendar, FileText, RefreshCw, CircleDot,
  Plus, Send, Info, AlertTriangle, Banknote, Building2
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip as ReTooltip,
  ResponsiveContainer, Cell, ReferenceLine
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
  return '$' + Math.abs(val).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

const formatDate = (dateStr) => {
  if (!dateStr) return '--';
  try {
    const d = new Date(dateStr + (dateStr.includes('T') ? '' : 'T00:00:00'));
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return dateStr;
  }
};

const formatDateShort = (dateStr) => {
  if (!dateStr) return '--';
  try {
    const d = new Date(dateStr + (dateStr.includes('T') ? '' : 'T00:00:00'));
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch {
    return dateStr;
  }
};

// ============================================================
// SECTION HEADER
// ============================================================

const SectionHeader = ({ icon: Icon, title, subtitle, iconColor = 'text-emerald-600', iconBg = 'bg-emerald-50', children }) => (
  <div className="flex items-center justify-between mb-5">
    <div className="flex items-center gap-3">
      <div className={`p-2 rounded-lg ${iconBg}`}>
        <Icon className={`w-5 h-5 ${iconColor}`} />
      </div>
      <div>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-slate-100">{title}</h3>
        {subtitle && <p className="text-sm text-gray-500 dark:text-slate-400">{subtitle}</p>}
      </div>
    </div>
    {children}
  </div>
);

// ============================================================
// NEW REQUEST FORM (Contribution / Withdrawal)
// ============================================================

const NewRequestForm = () => {
  const { getAuthHeaders } = useAuth();
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState('contribution');
  const [amount, setAmount] = useState('');
  const [notes, setNotes] = useState('');
  const [estimate, setEstimate] = useState(null);
  const [estimateLoading, setEstimateLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);

  // Fetch estimate when amount changes (debounced)
  useEffect(() => {
    const numAmount = parseFloat(amount);
    if (!numAmount || numAmount <= 0) {
      setEstimate(null);
      return;
    }

    const timer = setTimeout(async () => {
      setEstimateLoading(true);
      try {
        const res = await fetch(
          `${API_BASE_URL}/fund-flow/estimate?flow_type=${tab}&amount=${numAmount}`,
          { headers: getAuthHeaders() }
        );
        if (res.ok) {
          setEstimate(await res.json());
        } else {
          setEstimate(null);
        }
      } catch {
        setEstimate(null);
      }
      setEstimateLoading(false);
    }, 500);

    return () => clearTimeout(timer);
  }, [amount, tab, getAuthHeaders]);

  const handleSubmit = async () => {
    const numAmount = parseFloat(amount);
    if (!numAmount || numAmount <= 0) return;

    setSubmitting(true);
    setResult(null);
    try {
      const res = await fetch(`${API_BASE_URL}/fund-flow/request`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          flow_type: tab,
          amount: numAmount,
          notes: notes.trim() || null,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setResult({ success: true, message: data.message, requestId: data.request_id });
        setAmount('');
        setNotes('');
        setEstimate(null);
      } else {
        const err = await res.json().catch(() => ({}));
        setResult({ success: false, message: err.detail || 'Request failed. Please try again.' });
      }
    } catch {
      setResult({ success: false, message: 'Network error. Please try again.' });
    }
    setSubmitting(false);
  };

  const handleTabSwitch = (newTab) => {
    setTab(newTab);
    setAmount('');
    setNotes('');
    setEstimate(null);
    setResult(null);
  };

  return (
    <div className="bg-white dark:bg-slate-800/50 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700/50 mb-6 overflow-hidden">
      {/* Toggle header */}
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center justify-between w-full p-5 text-left hover:bg-gray-50 dark:hover:bg-slate-700/50 transition"
      >
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-emerald-50 dark:bg-emerald-900/30">
            <Plus className={`w-5 h-5 text-emerald-600 dark:text-emerald-400 transition-transform ${open ? 'rotate-45' : ''}`} />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-slate-100">Move Money</h3>
            <p className="text-sm text-gray-500 dark:text-slate-400">Contribute or withdraw funds</p>
          </div>
        </div>
        {open ? <ChevronUp className="w-5 h-5 text-gray-400 dark:text-slate-500" /> : <ChevronDown className="w-5 h-5 text-gray-400 dark:text-slate-500" />}
      </button>

      {open && (
        <div className="px-5 pb-5 border-t border-gray-100 dark:border-slate-700/50">
          {/* Tabs */}
          <div className="flex gap-1 mt-4 mb-5 p-1 bg-gray-100 dark:bg-slate-700 rounded-lg w-fit">
            <button
              onClick={() => handleTabSwitch('contribution')}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium transition ${
                tab === 'contribution'
                  ? 'bg-white dark:bg-slate-600 text-emerald-700 dark:text-emerald-400 shadow-sm'
                  : 'text-gray-500 dark:text-slate-400 hover:text-gray-700 dark:hover:text-slate-200'
              }`}
            >
              <ArrowDownRight className="w-4 h-4" />
              Contribute
            </button>
            <button
              onClick={() => handleTabSwitch('withdrawal')}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium transition ${
                tab === 'withdrawal'
                  ? 'bg-white dark:bg-slate-600 text-red-700 dark:text-red-300 shadow-sm'
                  : 'text-gray-500 dark:text-slate-400 hover:text-gray-700 dark:hover:text-slate-200'
              }`}
            >
              <ArrowUpRight className="w-4 h-4" />
              Withdraw
            </button>
          </div>

          {/* Success/Error result */}
          {result && (
            <div className={`mb-4 p-4 rounded-xl border ${
              result.success
                ? 'bg-emerald-50 dark:bg-emerald-900/30 border-emerald-200 dark:border-emerald-700 text-emerald-800 dark:text-emerald-200'
                : 'bg-red-50 dark:bg-red-900/30 border-red-200 dark:border-red-700 text-red-800 dark:text-red-200'
            }`}>
              <div className="flex items-start gap-2">
                {result.success
                  ? <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
                  : <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                }
                <div>
                  <p className="text-sm font-medium">{result.message}</p>
                  {result.requestId && (
                    <p className="text-xs mt-1 opacity-75">Request ID: #{result.requestId}</p>
                  )}
                  {result.success && tab === 'contribution' && (
                    <p className="text-xs mt-1 opacity-75">
                      Follow the wire/ACH instructions below to complete your contribution.
                    </p>
                  )}
                  {result.success && tab === 'withdrawal' && (
                    <p className="text-xs mt-1 opacity-75">
                      Your withdrawal is being processed. Estimated completion: 3-5 business days.
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Left: Form */}
            <div>
              {/* Amount */}
              <div className="mb-4">
                <label className="text-xs text-gray-500 dark:text-slate-400 font-semibold uppercase tracking-wider">
                  Amount (USD)
                </label>
                <div className="relative mt-1">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-slate-500 font-medium">$</span>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={amount}
                    onChange={e => setAmount(e.target.value)}
                    placeholder="0.00"
                    className="w-full pl-7 pr-3 py-3 text-lg font-semibold border border-gray-200 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                  />
                </div>
              </div>

              {/* Notes */}
              <div className="mb-4">
                <label className="text-xs text-gray-500 dark:text-slate-400 font-semibold uppercase tracking-wider">
                  Notes (optional)
                </label>
                <textarea
                  value={notes}
                  onChange={e => setNotes(e.target.value)}
                  maxLength={500}
                  rows={2}
                  placeholder="Any notes for the fund manager..."
                  className="w-full mt-1 px-3 py-2 text-sm border border-gray-200 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent resize-none"
                />
              </div>

              {/* Estimate */}
              {estimateLoading && (
                <div className="flex items-center gap-2 text-xs text-gray-400 dark:text-slate-500 mb-4">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" /> Calculating estimate...
                </div>
              )}

              {estimate && !estimateLoading && (
                <div className={`p-4 rounded-xl border mb-4 ${
                  tab === 'contribution' ? 'bg-emerald-50/50 dark:bg-emerald-900/20 border-emerald-200 dark:border-emerald-700' : 'bg-blue-50/50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-700'
                }`}>
                  <p className="text-xs font-bold text-gray-500 dark:text-slate-400 uppercase tracking-wider mb-2">Estimate</p>
                  <div className="space-y-1.5 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-500 dark:text-slate-400">Current NAV/Share</span>
                      <span className="font-semibold text-gray-900 dark:text-slate-100">${estimate.current_nav?.toFixed(4)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500 dark:text-slate-400">Estimated Shares</span>
                      <span className="font-semibold text-gray-900 dark:text-slate-100">
                        {estimate.estimated_shares?.toLocaleString('en-US', { maximumFractionDigits: 4 })}
                      </span>
                    </div>
                    {tab === 'withdrawal' && (
                      <>
                        {estimate.realized_gain != null && (
                          <div className="flex justify-between">
                            <span className="text-gray-500 dark:text-slate-400">Est. Realized Gain</span>
                            <span className={`font-semibold ${estimate.realized_gain >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                              {formatCurrency(estimate.realized_gain)}
                            </span>
                          </div>
                        )}
                        {estimate.estimated_tax != null && (
                          <div className="flex justify-between">
                            <span className="text-gray-500 dark:text-slate-400">Est. Tax (quarterly)</span>
                            <span className="font-semibold text-gray-700 dark:text-slate-300">{formatCurrency(estimate.estimated_tax)}</span>
                          </div>
                        )}
                        {estimate.net_proceeds != null && (
                          <div className="flex justify-between pt-1.5 border-t border-gray-200 dark:border-slate-700">
                            <span className="text-gray-700 dark:text-slate-300 font-medium">Net Proceeds</span>
                            <span className="font-bold text-gray-900 dark:text-slate-100">{formatCurrency(estimate.net_proceeds)}</span>
                          </div>
                        )}
                      </>
                    )}
                    {tab === 'contribution' && estimate.new_total_shares != null && (
                      <div className="flex justify-between pt-1.5 border-t border-gray-200 dark:border-slate-700">
                        <span className="text-gray-700 dark:text-slate-300 font-medium">New Total Shares</span>
                        <span className="font-bold text-gray-900 dark:text-slate-100">
                          {estimate.new_total_shares?.toLocaleString('en-US', { maximumFractionDigits: 4 })}
                        </span>
                      </div>
                    )}
                  </div>
                  <p className="text-[10px] text-gray-400 dark:text-slate-500 mt-2">
                    Estimate only — actual values calculated at processing time.
                  </p>
                </div>
              )}

              {/* Submit */}
              <button
                onClick={handleSubmit}
                disabled={submitting || !parseFloat(amount) || parseFloat(amount) <= 0}
                className={`flex items-center justify-center gap-2 w-full py-3 rounded-xl text-sm font-semibold transition disabled:opacity-40 disabled:cursor-not-allowed ${
                  tab === 'contribution'
                    ? 'bg-emerald-600 text-white hover:bg-emerald-700'
                    : 'bg-red-600 text-white hover:bg-red-700'
                }`}
              >
                {submitting ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
                {submitting
                  ? 'Submitting...'
                  : tab === 'contribution'
                    ? 'Submit Contribution Request'
                    : 'Submit Withdrawal Request'
                }
              </button>
            </div>

            {/* Right: Info panel */}
            <div>
              {tab === 'contribution' ? (
                <>
                  {/* Wire/ACH Instructions */}
                  <div className="p-4 rounded-xl border border-blue-200 dark:border-blue-700 bg-blue-50/50 dark:bg-blue-900/20 mb-4">
                    <div className="flex items-center gap-2 mb-3">
                      <Building2 className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                      <p className="text-sm font-bold text-blue-800 dark:text-blue-200">Wire/ACH Instructions</p>
                    </div>
                    <div className="space-y-2 text-sm">
                      <p className="text-blue-700 dark:text-blue-300">
                        Please contact <span className="font-semibold">support@tovitotrader.com</span> for
                        wire transfer or ACH instructions to send your contribution.
                      </p>
                      <div className="text-xs text-blue-600 dark:text-blue-400 bg-blue-100 dark:bg-blue-900/50 rounded-lg px-3 py-2">
                        <p className="font-semibold mb-1">Important:</p>
                        <p>Include your investor ID in the memo/reference field so we can match your deposit.</p>
                      </div>
                    </div>
                  </div>

                  {/* How it works */}
                  <div className="p-4 rounded-xl border border-gray-200 dark:border-slate-700 bg-gray-50/50 dark:bg-slate-800/50">
                    <div className="flex items-center gap-2 mb-3">
                      <Info className="w-4 h-4 text-gray-500 dark:text-slate-400" />
                      <p className="text-sm font-bold text-gray-700 dark:text-slate-300">How Contributions Work</p>
                    </div>
                    <div className="space-y-2.5 text-xs text-gray-600 dark:text-slate-400">
                      <div className="flex gap-2">
                        <span className="w-5 h-5 rounded-full bg-emerald-100 dark:bg-emerald-900/50 text-emerald-700 dark:text-emerald-400 flex items-center justify-center text-[10px] font-bold flex-shrink-0">1</span>
                        <p>Submit your request here and wire/ACH the funds to the fund account.</p>
                      </div>
                      <div className="flex gap-2">
                        <span className="w-5 h-5 rounded-full bg-emerald-100 dark:bg-emerald-900/50 text-emerald-700 dark:text-emerald-400 flex items-center justify-center text-[10px] font-bold flex-shrink-0">2</span>
                        <p>Funds typically arrive in <strong>1-3 business days</strong> via ACH.</p>
                      </div>
                      <div className="flex gap-2">
                        <span className="w-5 h-5 rounded-full bg-emerald-100 dark:bg-emerald-900/50 text-emerald-700 dark:text-emerald-400 flex items-center justify-center text-[10px] font-bold flex-shrink-0">3</span>
                        <p>Shares are purchased at the <strong>closing NAV on the day your funds arrive</strong>.</p>
                      </div>
                      <div className="flex gap-2">
                        <span className="w-5 h-5 rounded-full bg-emerald-100 dark:bg-emerald-900/50 text-emerald-700 dark:text-emerald-400 flex items-center justify-center text-[10px] font-bold flex-shrink-0">4</span>
                        <p>You'll see your new shares reflected on the next business day.</p>
                      </div>
                    </div>
                  </div>
                </>
              ) : (
                <>
                  {/* Withdrawal disclosure */}
                  <div className="p-4 rounded-xl border border-amber-200 dark:border-amber-700 bg-amber-50/50 dark:bg-amber-900/20 mb-4">
                    <div className="flex items-center gap-2 mb-3">
                      <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400" />
                      <p className="text-sm font-bold text-amber-800 dark:text-amber-200">Important: Withdrawal Timeline</p>
                    </div>
                    <div className="space-y-2 text-xs text-amber-700 dark:text-amber-300">
                      <p>
                        <strong>Share pricing:</strong> Withdrawal shares are priced at the
                        <strong> end-of-day NAV on the date your request is submitted</strong>.
                      </p>
                      <p>
                        <strong>Liquidation:</strong> Open positions may need to be closed to
                        free up capital. This process typically takes <strong>1-2 business days</strong>.
                      </p>
                      <p>
                        <strong>Transfer:</strong> Once funds are available, an ACH transfer
                        to your bank takes an additional <strong>2-3 business days</strong>.
                      </p>
                      <div className="flex items-center gap-2 mt-2 p-2 bg-amber-100 dark:bg-amber-900/50 rounded-lg">
                        <Clock className="w-4 h-4 text-amber-700 dark:text-amber-300 flex-shrink-0" />
                        <p className="font-bold text-amber-800 dark:text-amber-200">
                          Total estimated time: 3-5 business days from request submission.
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Tax info */}
                  <div className="p-4 rounded-xl border border-gray-200 dark:border-slate-700 bg-gray-50/50 dark:bg-slate-800/50">
                    <div className="flex items-center gap-2 mb-3">
                      <Info className="w-4 h-4 text-gray-500 dark:text-slate-400" />
                      <p className="text-sm font-bold text-gray-700 dark:text-slate-300">Tax Information</p>
                    </div>
                    <div className="space-y-2 text-xs text-gray-600 dark:text-slate-400">
                      <p>
                        <strong>No tax is withheld</strong> from your withdrawal.
                        You receive the full amount of your net proceeds.
                      </p>
                      <p>
                        Tax on any realized gains is <strong>settled quarterly</strong> at the
                        fund level (37% federal rate). Your estimated tax liability is
                        shown in the estimate for your records.
                      </p>
                      <p>
                        Your <strong>eligible withdrawal</strong> amount accounts for any
                        unrealized gains that may generate future tax obligations.
                      </p>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// ============================================================
// SUMMARY CARDS
// ============================================================

const SummaryCards = ({ transactions, position, nav }) => {
  const totalIn = transactions?.total_contributions || 0;
  const totalOut = transactions?.total_withdrawals || 0;
  const net = transactions?.net_investment || 0;

  // Current Value = shares * current NAV
  const currentShares = position?.current_shares || 0;
  const currentNav = nav?.nav_per_share || 0;
  const currentValue = currentShares * currentNav;

  // P/L Total = Current Value - Net Invested
  const plTotal = net > 0 ? currentValue - net : null;
  const plPct = net > 0 && plTotal !== null ? (plTotal / net) * 100 : null;

  return (
    <div className="grid grid-cols-2 lg:grid-cols-3 gap-3 mb-6">
      <div className="bg-white dark:bg-slate-800/50 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700/50 p-4">
        <div className="flex items-center gap-2 mb-1">
          <ArrowDownRight className="w-4 h-4 text-emerald-500" />
          <span className="text-[10px] text-gray-500 dark:text-slate-400 font-semibold uppercase tracking-wider">Total In</span>
        </div>
        <p className="text-xl font-bold text-emerald-600">{formatCurrency(totalIn)}</p>
      </div>
      <div className="bg-white dark:bg-slate-800/50 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700/50 p-4">
        <div className="flex items-center gap-2 mb-1">
          <ArrowUpRight className="w-4 h-4 text-red-500" />
          <span className="text-[10px] text-gray-500 dark:text-slate-400 font-semibold uppercase tracking-wider">Total Out</span>
        </div>
        <p className="text-xl font-bold text-red-600">{formatCurrency(totalOut)}</p>
      </div>
      <div className="bg-white dark:bg-slate-800/50 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700/50 p-4">
        <div className="flex items-center gap-2 mb-1">
          <DollarSign className="w-4 h-4 text-blue-500" />
          <span className="text-[10px] text-gray-500 dark:text-slate-400 font-semibold uppercase tracking-wider">Net Invested</span>
        </div>
        <p className="text-xl font-bold text-gray-900 dark:text-slate-100">{formatCurrency(net)}</p>
      </div>
      <div className="bg-white dark:bg-slate-800/50 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700/50 p-4">
        <div className="flex items-center gap-2 mb-1">
          <Banknote className="w-4 h-4 text-indigo-500" />
          <span className="text-[10px] text-gray-500 dark:text-slate-400 font-semibold uppercase tracking-wider">Current Value</span>
        </div>
        <p className="text-xl font-bold text-gray-900 dark:text-slate-100">
          {currentValue > 0 ? formatCurrency(currentValue) : '$--'}
        </p>
        {currentShares > 0 && currentNav > 0 && (
          <p className="text-[10px] text-gray-400 dark:text-slate-500 mt-0.5">
            {currentShares.toLocaleString('en-US', { maximumFractionDigits: 4 })} shares @ ${currentNav.toFixed(4)}
          </p>
        )}
      </div>
      <div className="bg-white dark:bg-slate-800/50 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700/50 p-4">
        <div className="flex items-center gap-2 mb-1">
          {plTotal !== null && plTotal >= 0
            ? <TrendingUp className="w-4 h-4 text-emerald-500" />
            : <TrendingDown className="w-4 h-4 text-red-500" />
          }
          <span className="text-[10px] text-gray-500 dark:text-slate-400 font-semibold uppercase tracking-wider">P/L Total</span>
        </div>
        {plTotal !== null ? (
          <>
            <p className={`text-xl font-bold ${plTotal >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
              {plTotal >= 0 ? '+' : '-'}{formatCurrency(Math.abs(plTotal))}
            </p>
            {plPct !== null && (
              <p className={`text-[10px] mt-0.5 font-medium ${plPct >= 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                {plPct >= 0 ? '+' : ''}{plPct.toFixed(2)}%
              </p>
            )}
          </>
        ) : (
          <p className="text-xl font-bold text-gray-400 dark:text-slate-500">$--</p>
        )}
      </div>
      <div className="bg-white dark:bg-slate-800/50 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700/50 p-4">
        <div className="flex items-center gap-2 mb-1">
          <FileText className="w-4 h-4 text-purple-500" />
          <span className="text-[10px] text-gray-500 dark:text-slate-400 font-semibold uppercase tracking-wider">Transactions</span>
        </div>
        <p className="text-xl font-bold text-gray-900 dark:text-slate-100">{transactions?.transactions?.length || 0}</p>
      </div>
    </div>
  );
};

// ============================================================
// CASH FLOW CHART
// ============================================================

const CashFlowTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  if (!d) return null;

  return (
    <div className="bg-white/95 dark:bg-slate-800/95 backdrop-blur border border-gray-200 dark:border-slate-600 rounded-lg shadow-lg px-3 py-2 text-xs">
      <p className="font-semibold text-gray-700 dark:text-slate-300 mb-1">{d.label}</p>
      {d.contributions > 0 && (
        <div className="flex justify-between gap-4">
          <span className="text-emerald-500">Contributions</span>
          <span className="font-bold text-emerald-600">{formatCurrency(d.contributions)}</span>
        </div>
      )}
      {d.withdrawals > 0 && (
        <div className="flex justify-between gap-4">
          <span className="text-red-500">Withdrawals</span>
          <span className="font-bold text-red-600">{formatCurrency(d.withdrawals)}</span>
        </div>
      )}
      <div className="flex justify-between gap-4 mt-1 pt-1 border-t border-gray-100 dark:border-slate-700/50">
        <span className="text-gray-500 dark:text-slate-400">Net Flow</span>
        <span className={`font-bold ${d.net >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
          {d.net >= 0 ? '+' : '-'}{formatCurrency(Math.abs(d.net))}
        </span>
      </div>
    </div>
  );
};

const CashFlowChart = ({ transactions }) => {
  const { darkMode } = useTheme();
  const chartData = useMemo(() => {
    if (!transactions?.transactions?.length) return [];

    // Group by month
    const byMonth = {};
    for (const tx of transactions.transactions) {
      const monthKey = tx.date.substring(0, 7); // 'YYYY-MM'
      if (!byMonth[monthKey]) {
        byMonth[monthKey] = { contributions: 0, withdrawals: 0 };
      }
      if (tx.type === 'Contribution' || tx.type === 'Initial') {
        byMonth[monthKey].contributions += tx.amount;
      } else if (tx.type === 'Withdrawal') {
        byMonth[monthKey].withdrawals += tx.amount;
      }
    }

    // Sort by month and format
    return Object.keys(byMonth)
      .sort()
      .map(month => {
        const d = byMonth[month];
        let label;
        try {
          const dt = new Date(month + '-01T00:00:00');
          label = dt.toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
        } catch {
          label = month;
        }
        return {
          month,
          label,
          contributions: Math.round(d.contributions * 100) / 100,
          withdrawals: Math.round(d.withdrawals * 100) / 100,
          net: Math.round((d.contributions - d.withdrawals) * 100) / 100,
        };
      });
  }, [transactions]);

  if (chartData.length === 0) {
    return null;
  }

  return (
    <div className="bg-white dark:bg-slate-800/50 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700/50 p-6 mb-6">
      <SectionHeader
        icon={BarChart}
        title="Cash Flow"
        subtitle="Monthly contributions and withdrawals"
        iconColor="text-blue-600 dark:text-blue-400"
        iconBg="bg-blue-50 dark:bg-blue-900/30"
      />

      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={chartData} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
          <XAxis
            dataKey="label"
            tick={{ fontSize: 11, fill: darkMode ? '#94a3b8' : '#9ca3af' }}
            tickLine={false}
            axisLine={{ stroke: darkMode ? '#334155' : '#e5e7eb' }}
          />
          <YAxis
            tick={{ fontSize: 11, fill: darkMode ? '#94a3b8' : '#9ca3af' }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
            width={50}
          />
          <ReTooltip content={<CashFlowTooltip />} cursor={{ fill: darkMode ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.03)' }} />
          <ReferenceLine y={0} stroke={darkMode ? '#334155' : '#e5e7eb'} />
          <Bar dataKey="contributions" fill="#10b981" radius={[4, 4, 0, 0]} maxBarSize={40} name="In" />
          <Bar dataKey="withdrawals" fill="#ef4444" radius={[4, 4, 0, 0]} maxBarSize={40} name="Out" />
        </BarChart>
      </ResponsiveContainer>

      <div className="flex items-center justify-center gap-6 mt-2 text-xs">
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-sm bg-emerald-500" />
          <span className="text-gray-500 dark:text-slate-400">Contributions</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-sm bg-red-500" />
          <span className="text-gray-500 dark:text-slate-400">Withdrawals</span>
        </div>
      </div>
    </div>
  );
};

// ============================================================
// FUND FLOW STATUS TRACKER
// ============================================================

const STATUS_CONFIG = {
  pending:        { label: 'Pending',        color: 'text-amber-600 dark:text-amber-400',     bg: 'bg-amber-50 dark:bg-amber-900/30',     border: 'border-amber-200 dark:border-amber-700',     icon: Clock,         dot: 'bg-amber-400' },
  approved:       { label: 'Approved',       color: 'text-blue-600 dark:text-blue-400',       bg: 'bg-blue-50 dark:bg-blue-900/30',       border: 'border-blue-200 dark:border-blue-700',       icon: CheckCircle2,  dot: 'bg-blue-400' },
  awaiting_funds: { label: 'Awaiting Funds', color: 'text-purple-600 dark:text-purple-400',   bg: 'bg-purple-50 dark:bg-purple-900/30',   border: 'border-purple-200 dark:border-purple-700',   icon: RefreshCw,     dot: 'bg-purple-400' },
  matched:        { label: 'Matched',        color: 'text-indigo-600 dark:text-indigo-400',   bg: 'bg-indigo-50 dark:bg-indigo-900/30',   border: 'border-indigo-200 dark:border-indigo-700',   icon: CircleDot,     dot: 'bg-indigo-400' },
  processed:      { label: 'Completed',      color: 'text-emerald-600 dark:text-emerald-400', bg: 'bg-emerald-50 dark:bg-emerald-900/30', border: 'border-emerald-200 dark:border-emerald-700', icon: CheckCircle2,  dot: 'bg-emerald-400' },
  rejected:       { label: 'Rejected',       color: 'text-red-600 dark:text-red-400',         bg: 'bg-red-50 dark:bg-red-900/30',         border: 'border-red-200 dark:border-red-700',         icon: XCircle,       dot: 'bg-red-400' },
  cancelled:      { label: 'Cancelled',      color: 'text-gray-500 dark:text-slate-400',      bg: 'bg-gray-50 dark:bg-slate-800',         border: 'border-gray-200 dark:border-slate-700',      icon: XCircle,       dot: 'bg-gray-400' },
};

const FLOW_STEPS = ['pending', 'approved', 'awaiting_funds', 'matched', 'processed'];

const StatusBadge = ({ status }) => {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.pending;
  const Icon = config.icon;

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${config.bg} ${config.color} border ${config.border}`}>
      <Icon className="w-3 h-3" />
      {config.label}
    </span>
  );
};

const FlowProgressBar = ({ currentStatus }) => {
  const currentIdx = FLOW_STEPS.indexOf(currentStatus);
  const isTerminal = currentStatus === 'rejected' || currentStatus === 'cancelled';

  return (
    <div className="flex items-center gap-1 mt-2">
      {FLOW_STEPS.map((step, i) => {
        const config = STATUS_CONFIG[step];
        const isActive = i <= currentIdx && !isTerminal;
        const isCurrent = step === currentStatus;

        return (
          <div key={step} className="flex items-center flex-1">
            <div className={`h-1.5 w-full rounded-full transition-all duration-500 ${
              isActive ? config.dot : isTerminal ? 'bg-gray-200 dark:bg-slate-600' : 'bg-gray-200 dark:bg-slate-600'
            } ${isCurrent ? 'ring-2 ring-offset-1 ring-' + config.dot.replace('bg-', '') : ''}`} />
          </div>
        );
      })}
    </div>
  );
};

const FundFlowCard = ({ request }) => {
  const isContribution = request.flow_type === 'contribution';
  const statusConfig = STATUS_CONFIG[request.status] || STATUS_CONFIG.pending;

  return (
    <div className={`bg-white dark:bg-slate-800/50 rounded-xl border shadow-sm p-4 hover:shadow-md transition-shadow ${
      request.status === 'processed' ? 'border-emerald-100 dark:border-emerald-800' :
      request.status === 'rejected' || request.status === 'cancelled' ? 'border-gray-200 opacity-75' :
      'border-gray-100 dark:border-slate-700/50'
    }`}>
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className={`p-1.5 rounded-lg ${isContribution ? 'bg-emerald-50 dark:bg-emerald-900/30' : 'bg-red-50 dark:bg-red-900/30'}`}>
            {isContribution
              ? <ArrowDownRight className="w-4 h-4 text-emerald-600" />
              : <ArrowUpRight className="w-4 h-4 text-red-600" />
            }
          </div>
          <div>
            <span className={`text-sm font-bold ${isContribution ? 'text-emerald-700 dark:text-emerald-300' : 'text-red-700 dark:text-red-300'}`}>
              {isContribution ? 'Contribution' : 'Withdrawal'}
            </span>
            <p className="text-[10px] text-gray-400 dark:text-slate-500">Requested {formatDate(request.request_date)}</p>
          </div>
        </div>
        <StatusBadge status={request.status} />
      </div>

      {/* Amount */}
      <div className="flex items-baseline gap-2 mb-2">
        <span className="text-2xl font-bold text-gray-900 dark:text-slate-100">{formatCurrency(request.requested_amount)}</span>
        {request.actual_amount && request.actual_amount !== request.requested_amount && (
          <span className="text-xs text-gray-400 dark:text-slate-500">(Actual: {formatCurrency(request.actual_amount)})</span>
        )}
      </div>

      {/* Progress bar */}
      <FlowProgressBar currentStatus={request.status} />

      {/* Step labels */}
      <div className="flex justify-between mt-1 text-[9px] text-gray-400 dark:text-slate-500">
        <span>Requested</span>
        <span>Approved</span>
        <span>Funds</span>
        <span>Matched</span>
        <span>Done</span>
      </div>

      {/* Details (if processed) */}
      {request.status === 'processed' && (
        <div className="mt-3 pt-3 border-t border-gray-100 dark:border-slate-700/50 grid grid-cols-2 gap-2 text-xs">
          {request.shares_transacted != null && (
            <div>
              <span className="text-gray-400 dark:text-slate-500">Shares</span>
              <p className="font-semibold text-gray-700 dark:text-slate-300">
                {request.shares_transacted.toLocaleString('en-US', { maximumFractionDigits: 4 })}
              </p>
            </div>
          )}
          {request.nav_per_share != null && (
            <div>
              <span className="text-gray-400 dark:text-slate-500">NAV/Share</span>
              <p className="font-semibold text-gray-700 dark:text-slate-300">${request.nav_per_share.toFixed(4)}</p>
            </div>
          )}
          {request.processed_date && (
            <div>
              <span className="text-gray-400 dark:text-slate-500">Completed</span>
              <p className="font-semibold text-gray-700 dark:text-slate-300">{formatDate(request.processed_date)}</p>
            </div>
          )}
          {!isContribution && request.realized_gain != null && (
            <div>
              <span className="text-gray-400 dark:text-slate-500">Realized Gain</span>
              <p className={`font-semibold ${request.realized_gain >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                {formatCurrency(request.realized_gain)}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Rejection reason */}
      {request.status === 'rejected' && request.rejection_reason && (
        <div className="mt-3 pt-3 border-t border-gray-100 dark:border-slate-700/50">
          <p className="text-xs text-red-600">
            <span className="font-semibold">Reason:</span> {request.rejection_reason}
          </p>
        </div>
      )}
    </div>
  );
};

const FundFlowTracker = () => {
  const { getAuthHeaders } = useAuth();
  const [statusFilter, setStatusFilter] = useState('all');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    (async () => {
      try {
        let url = `${API_BASE_URL}/fund-flow/requests?limit=200`;
        if (statusFilter !== 'all') url += `&status=${statusFilter}`;
        const res = await fetch(url, { headers: getAuthHeaders() });
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
  }, [statusFilter, getAuthHeaders]);

  const activeRequests = useMemo(() => {
    if (!data?.requests) return [];
    return data.requests.filter(r => !['processed', 'rejected', 'cancelled'].includes(r.status));
  }, [data]);

  const completedRequests = useMemo(() => {
    if (!data?.requests) return [];
    return data.requests.filter(r => ['processed', 'rejected', 'cancelled'].includes(r.status));
  }, [data]);

  const STATUS_FILTERS = [
    { key: 'all', label: 'All' },
    { key: 'pending', label: 'Pending' },
    { key: 'approved', label: 'Approved' },
    { key: 'processed', label: 'Completed' },
  ];

  return (
    <div className="bg-white dark:bg-slate-800/50 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700/50 p-6 mb-6">
      <SectionHeader
        icon={RefreshCw}
        title="Fund Flow Requests"
        subtitle="Track your contribution and withdrawal requests"
        iconColor="text-purple-600 dark:text-purple-400"
        iconBg="bg-purple-50 dark:bg-purple-900/30"
      >
        <div className="flex gap-1">
          {STATUS_FILTERS.map(f => (
            <button
              key={f.key}
              onClick={() => setStatusFilter(f.key)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                statusFilter === f.key
                  ? 'bg-purple-600 text-white shadow-sm'
                  : 'bg-gray-100 dark:bg-slate-700 text-gray-600 dark:text-slate-300 hover:bg-gray-200 dark:hover:bg-slate-600'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </SectionHeader>

      {loading ? (
        <div className="h-24 flex items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-purple-400" />
        </div>
      ) : !data?.requests?.length ? (
        <div className="text-center py-8 text-gray-400 dark:text-slate-500">
          <Clock className="w-8 h-8 mx-auto mb-2 text-gray-300 dark:text-slate-600" />
          <p className="text-sm">No fund flow requests found</p>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Active requests first (visually prominent) */}
          {activeRequests.length > 0 && (
            <div>
              <p className="text-xs font-bold text-amber-600 dark:text-amber-400 uppercase tracking-wider mb-2">
                In Progress ({activeRequests.length})
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {activeRequests.map(req => (
                  <FundFlowCard key={req.request_id} request={req} />
                ))}
              </div>
            </div>
          )}

          {/* Completed requests */}
          {completedRequests.length > 0 && (
            <div>
              {activeRequests.length > 0 && (
                <p className="text-xs font-bold text-gray-400 dark:text-slate-500 uppercase tracking-wider mb-2 mt-4">
                  Completed ({completedRequests.length})
                </p>
              )}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {completedRequests.map(req => (
                  <FundFlowCard key={req.request_id} request={req} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// ============================================================
// TRANSACTION HISTORY TABLE
// ============================================================

const TYPE_ICONS = {
  Initial: { icon: DollarSign, color: 'text-blue-600 dark:text-blue-400', bg: 'bg-blue-50 dark:bg-blue-900/30' },
  Contribution: { icon: ArrowDownRight, color: 'text-emerald-600 dark:text-emerald-400', bg: 'bg-emerald-50 dark:bg-emerald-900/30' },
  Withdrawal: { icon: ArrowUpRight, color: 'text-red-600 dark:text-red-400', bg: 'bg-red-50 dark:bg-red-900/30' },
  Tax_Payment: { icon: FileText, color: 'text-amber-600 dark:text-amber-400', bg: 'bg-amber-50 dark:bg-amber-900/30' },
  Fee: { icon: FileText, color: 'text-gray-600 dark:text-slate-400', bg: 'bg-gray-50 dark:bg-slate-800' },
  Adjustment: { icon: RefreshCw, color: 'text-purple-600 dark:text-purple-400', bg: 'bg-purple-50 dark:bg-purple-900/30' },
};

const TYPE_FILTER_OPTIONS = [
  { key: '', label: 'All Types' },
  { key: 'Initial', label: 'Initial' },
  { key: 'Contribution', label: 'Contributions' },
  { key: 'Withdrawal', label: 'Withdrawals' },
];

const TransactionHistory = () => {
  const { getAuthHeaders } = useAuth();
  const [transactions, setTransactions] = useState(null);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState('');
  const [page, setPage] = useState(0);
  const pageSize = 15;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    (async () => {
      try {
        let url = `${API_BASE_URL}/investor/transactions?limit=${pageSize}&offset=${page * pageSize}`;
        if (typeFilter) url += `&transaction_type=${typeFilter}`;
        const res = await fetch(url, { headers: getAuthHeaders() });
        if (!res.ok) throw new Error('Failed');
        const json = await res.json();
        if (!cancelled) {
          setTransactions(json);
          setLoading(false);
        }
      } catch {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => { cancelled = true; };
  }, [page, typeFilter, getAuthHeaders]);

  // Reset page when filter changes
  useEffect(() => {
    setPage(0);
  }, [typeFilter]);

  const txList = transactions?.transactions || [];
  const hasMore = txList.length === pageSize;

  return (
    <div className="bg-white dark:bg-slate-800/50 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700/50 p-6 mb-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-4 gap-3">
        <SectionHeader
          icon={ArrowLeftRight}
          title="Transaction History"
          subtitle="All your account transactions"
          iconColor="text-indigo-600 dark:text-indigo-400"
          iconBg="bg-indigo-50 dark:bg-indigo-900/30"
        />
        <div className="flex items-center gap-2 flex-shrink-0">
          <Filter className="w-4 h-4 text-gray-400" />
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="text-sm border border-gray-200 dark:border-slate-600 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent bg-white dark:bg-slate-700 dark:text-slate-200"
          >
            {TYPE_FILTER_OPTIONS.map(opt => (
              <option key={opt.key} value={opt.key}>{opt.label}</option>
            ))}
          </select>
        </div>
      </div>

      {loading ? (
        <div className="h-32 flex items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-indigo-400" />
        </div>
      ) : txList.length === 0 ? (
        <div className="text-center py-8 text-gray-400 dark:text-slate-500">
          <FileText className="w-8 h-8 mx-auto mb-2 text-gray-300 dark:text-slate-600" />
          <p className="text-sm">{typeFilter ? 'No matching transactions' : 'No transactions yet'}</p>
        </div>
      ) : (
        <>
          {/* Transaction rows */}
          <div className="space-y-1">
            {txList.map((tx, i) => {
              const typeConfig = TYPE_ICONS[tx.type] || TYPE_ICONS.Adjustment;
              const Icon = typeConfig.icon;
              const isPositive = tx.type === 'Contribution' || tx.type === 'Initial';

              return (
                <div
                  key={`${tx.date}-${i}`}
                  className="flex items-center gap-3 p-3 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-700/50 transition group"
                >
                  {/* Icon */}
                  <div className={`p-2 rounded-lg ${typeConfig.bg} flex-shrink-0`}>
                    <Icon className={`w-4 h-4 ${typeConfig.color}`} />
                  </div>

                  {/* Details */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-gray-900 dark:text-slate-100 text-sm">
                        {tx.type === 'Initial' ? 'Initial Deposit' : tx.type}
                      </span>
                      {tx.notes && (
                        <span className="text-[10px] text-gray-400 dark:text-slate-500 truncate max-w-[200px]" title={tx.notes}>
                          {tx.notes}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-3 text-xs text-gray-500 dark:text-slate-400">
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3 h-3" />
                        {formatDate(tx.date)}
                      </span>
                      <span>
                        {tx.shares.toLocaleString('en-US', { maximumFractionDigits: 4 })} shares {isPositive ? 'received' : 'redeemed'}
                      </span>
                      <span className="text-gray-400 dark:text-slate-500">@ ${tx.nav_at_transaction?.toFixed(4) || '--'}</span>
                    </div>
                  </div>

                  {/* Amount */}
                  <div className="text-right flex-shrink-0">
                    <p className={`text-base font-bold ${isPositive ? 'text-emerald-600' : 'text-red-600'}`}>
                      {isPositive ? '+' : '-'}{formatCurrency(tx.amount)}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between mt-4 pt-3 border-t border-gray-100 dark:border-slate-700/50">
            <button
              onClick={() => setPage(p => Math.max(0, p - 1))}
              disabled={page === 0}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium transition disabled:opacity-30 disabled:cursor-not-allowed bg-gray-100 dark:bg-slate-700 text-gray-600 dark:text-slate-300 hover:bg-gray-200 dark:hover:bg-slate-600"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
              Previous
            </button>
            <span className="text-xs text-gray-400 dark:text-slate-500">Page {page + 1}</span>
            <button
              onClick={() => setPage(p => p + 1)}
              disabled={!hasMore}
              className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium transition disabled:opacity-30 disabled:cursor-not-allowed bg-gray-100 dark:bg-slate-700 text-gray-600 dark:text-slate-300 hover:bg-gray-200 dark:hover:bg-slate-600"
            >
              Next
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </>
      )}
    </div>
  );
};

// ============================================================
// NAV TIMELINE (Daily NAV milestones)
// ============================================================

const NavTimeline = () => {
  const { data: perf } = useApi('/nav/performance');
  const { data: nav } = useApi('/nav/current');
  const { data: risk } = useApi('/analysis/risk-metrics?days=730');

  if (!perf || !nav) return null;

  const milestones = [];

  // Current NAV
  if (nav?.nav_per_share) {
    milestones.push({
      label: 'Current NAV',
      value: `$${nav.nav_per_share.toFixed(4)}`,
      sub: `${nav.daily_change_percent >= 0 ? '+' : ''}${nav.daily_change_percent?.toFixed(2) || '0.00'}% today`,
      color: nav.daily_change_percent >= 0 ? 'bg-emerald-400' : 'bg-red-400',
    });
  }

  // Since inception
  if (perf?.since_inception_return != null) {
    milestones.push({
      label: 'Since Launch',
      value: `${perf.since_inception_return >= 0 ? '+' : ''}${perf.since_inception_return.toFixed(2)}%`,
      sub: `Started ${perf.inception_date || 'Jan 2026'}`,
      color: perf.since_inception_return >= 0 ? 'bg-emerald-400' : 'bg-red-400',
    });
  }

  // Best day
  if (risk?.best_day_pct) {
    milestones.push({
      label: 'Best Day',
      value: `+${risk.best_day_pct.toFixed(2)}%`,
      sub: formatDate(risk.best_day_date),
      color: 'bg-emerald-400',
    });
  }

  // Worst day
  if (risk?.worst_day_pct != null) {
    milestones.push({
      label: 'Toughest Day',
      value: `${risk.worst_day_pct.toFixed(2)}%`,
      sub: formatDate(risk.worst_day_date),
      color: 'bg-red-400',
    });
  }

  if (milestones.length === 0) return null;

  return (
    <div className="bg-white dark:bg-slate-800/50 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700/50 p-6 mb-6">
      <SectionHeader
        icon={TrendingUp}
        title="Key Milestones"
        subtitle="Notable moments in your fund journey"
        iconColor="text-emerald-600 dark:text-emerald-400"
        iconBg="bg-emerald-50 dark:bg-emerald-900/30"
      />

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {milestones.map((m, i) => (
          <div key={i} className="relative pl-4">
            <div className={`absolute left-0 top-0 bottom-0 w-1 rounded-full ${m.color}`} />
            <p className="text-[10px] text-gray-400 dark:text-slate-500 font-semibold uppercase tracking-wider">{m.label}</p>
            <p className="text-lg font-bold text-gray-900 dark:text-slate-100 mt-0.5">{m.value}</p>
            <p className="text-xs text-gray-500 dark:text-slate-400">{m.sub}</p>
          </div>
        ))}
      </div>
    </div>
  );
};

// ============================================================
// ACTIVITY PAGE
// ============================================================

const ActivityPage = () => {
  // Fetch all transactions (high limit) for summary + chart
  const { data: allTransactions } = useApi('/investor/transactions?limit=200');
  const { data: position } = useApi('/investor/position');
  const { data: navData } = useApi('/nav/current');

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 pb-20 lg:pb-8">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-slate-100">My Money</h2>
        <p className="text-gray-500 dark:text-slate-400 text-sm">Your contributions, withdrawals, and fund flow history</p>
      </div>

      {/* 0. New Request Form */}
      <NewRequestForm />

      {/* 1. Summary Cards */}
      <SummaryCards transactions={allTransactions} position={position} nav={navData} />

      {/* 2. Key Milestones */}
      <NavTimeline />

      {/* 3. Cash Flow Chart */}
      <CashFlowChart transactions={allTransactions} />

      {/* 4. Fund Flow Tracker */}
      <FundFlowTracker />

      {/* 5. Transaction History */}
      <TransactionHistory />
    </div>
  );
};

export default ActivityPage;
