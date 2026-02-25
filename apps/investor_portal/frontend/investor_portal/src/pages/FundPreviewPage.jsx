import { useState, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import {
  TrendingUp, Shield, BarChart3, Users, Calendar, Clock,
  AlertTriangle, ArrowRight, LogIn, PieChart, Target,
  CheckCircle2, XCircle
} from 'lucide-react';
import { API_BASE_URL } from '../config';
import { useAuth } from '../context/AuthContext';


// ============================================================
// FUND PREVIEW PAGE
// ============================================================

const FundPreviewPage = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const { user } = useAuth();

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      setError('invalid');
      return;
    }

    const fetchData = async () => {
      try {
        const res = await fetch(
          `${API_BASE_URL}/public/prospect-performance?token=${encodeURIComponent(token)}&days=90`
        );
        if (!res.ok) throw new Error('Network error');
        const json = await res.json();
        if (!json.valid) {
          setError('expired');
        } else {
          setData(json);
        }
      } catch (e) {
        setError('network');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [token]);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState type={error} />;
  if (!data) return <ErrorState type="expired" />;

  return (
    <div className="min-h-screen bg-slate-950">
      <Navbar user={user} />
      <HeroSection data={data} />
      <StatsBar data={data} />
      <MonthlyReturnsSection returns={data.monthly_returns} />
      {data.plan_allocation.length > 0 && (
        <PlanAllocationSection plans={data.plan_allocation} />
      )}
      {data.benchmark_comparison.length > 0 && (
        <BenchmarkSection benchmarks={data.benchmark_comparison} />
      )}
      <CTASection user={user} />
      <Footer />
    </div>
  );
};


// ============================================================
// SUB-COMPONENTS
// ============================================================

const Navbar = ({ user }) => (
  <nav className="sticky top-0 z-50 bg-slate-950/90 backdrop-blur-md border-b border-slate-800/50">
    <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
      <Link to="/" className="flex items-center gap-2">
        <div className="w-8 h-8 bg-emerald-500/20 rounded-lg flex items-center justify-center">
          <TrendingUp className="w-5 h-5 text-emerald-400" />
        </div>
        <span className="text-lg font-bold text-white tracking-tight">TOVITO TRADER</span>
      </Link>
      <div className="flex items-center gap-4">
        {user ? (
          <Link
            to="/dashboard"
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm font-medium transition"
          >
            Go to Dashboard
          </Link>
        ) : (
          <Link
            to="/login"
            className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-sm font-medium transition"
          >
            <LogIn className="w-4 h-4" />
            Investor Login
          </Link>
        )}
      </div>
    </div>
  </nav>
);

const HeroSection = ({ data }) => (
  <section className="relative py-16 overflow-hidden">
    <div className="absolute inset-0 bg-gradient-to-b from-emerald-500/5 to-transparent" />
    <div className="relative max-w-4xl mx-auto px-6 text-center">
      <div className="inline-flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/20 rounded-full px-4 py-1.5 mb-6">
        <Shield className="w-4 h-4 text-emerald-400" />
        <span className="text-sm text-emerald-300">Exclusive Fund Preview</span>
      </div>
      <h1 className="text-4xl md:text-5xl font-bold text-white mb-4">
        Fund Performance Overview
      </h1>
      <p className="text-lg text-slate-400 max-w-2xl mx-auto">
        A transparent look at how our fund is performing.
        All returns shown are net of fees.
      </p>
      {data.since_inception_pct !== 0 && (
        <div className="mt-8 inline-flex items-center gap-3 bg-slate-900/80 border border-slate-700/50 rounded-2xl px-8 py-4">
          <span className="text-slate-400 text-sm">Since Inception Return</span>
          <span className={`text-3xl font-bold ${data.since_inception_pct >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
            {data.since_inception_pct >= 0 ? '+' : ''}{data.since_inception_pct}%
          </span>
        </div>
      )}
    </div>
  </section>
);

const StatsBar = ({ data }) => {
  const stats = [
    { label: 'Trading Days', value: data.trading_days, icon: Calendar },
    { label: 'Active Investors', value: data.investor_count, icon: Users },
    { label: 'Since', value: data.inception_date?.slice(0, 7)?.replace('-', '/'), icon: Clock },
    { label: 'As of', value: data.as_of_date, icon: BarChart3 },
  ];

  return (
    <section className="py-6 border-y border-slate-800/50">
      <div className="max-w-5xl mx-auto px-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {stats.map((stat, i) => (
            <div key={i} className="text-center">
              <stat.icon className="w-5 h-5 text-slate-500 mx-auto mb-1" />
              <div className="text-lg font-semibold text-white">{stat.value}</div>
              <div className="text-xs text-slate-500">{stat.label}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

const MonthlyReturnsSection = ({ returns }) => {
  if (!returns || returns.length === 0) return null;

  return (
    <section className="py-12">
      <div className="max-w-5xl mx-auto px-6">
        <h2 className="text-2xl font-bold text-white mb-6">Monthly Returns</h2>
        <div className="bg-slate-900/50 rounded-xl border border-slate-800/50 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-800/50">
                  <th className="text-left text-slate-400 font-medium px-4 py-3">Month</th>
                  <th className="text-right text-slate-400 font-medium px-4 py-3">Return</th>
                  <th className="text-right text-slate-400 font-medium px-4 py-3">Trading Days</th>
                </tr>
              </thead>
              <tbody>
                {returns.map((mr, i) => (
                  <tr key={i} className="border-b border-slate-800/30 last:border-0">
                    <td className="px-4 py-3 text-white font-medium">{mr.month_label}</td>
                    <td className="px-4 py-3 text-right">
                      <span className={`font-semibold ${mr.return_pct >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                        {mr.return_pct >= 0 ? '+' : ''}{mr.return_pct}%
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right text-slate-400">{mr.trading_days}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
  );
};

const PlanAllocationSection = ({ plans }) => {
  const PLAN_META = {
    plan_cash: { name: 'Plan CASH', desc: 'Treasury & money market', color: 'blue', risk: 'Conservative' },
    plan_etf: { name: 'Plan ETF', desc: 'Index ETF strategy', color: 'emerald', risk: 'Moderate' },
    plan_a: { name: 'Plan A', desc: 'Leveraged options', color: 'amber', risk: 'Aggressive' },
  };

  const colorMap = {
    blue: { bg: 'bg-blue-500/10', border: 'border-blue-500/20', text: 'text-blue-400', bar: 'bg-blue-500' },
    emerald: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/20', text: 'text-emerald-400', bar: 'bg-emerald-500' },
    amber: { bg: 'bg-amber-500/10', border: 'border-amber-500/20', text: 'text-amber-400', bar: 'bg-amber-500' },
  };

  return (
    <section className="py-12 border-t border-slate-800/50">
      <div className="max-w-5xl mx-auto px-6">
        <h2 className="text-2xl font-bold text-white mb-2">Investment Plans</h2>
        <p className="text-slate-400 mb-6">
          Our portfolio is divided into three distinct strategies based on risk profile.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {plans.map((plan, i) => {
            const meta = PLAN_META[plan.plan_id] || { name: plan.plan_id, desc: '', color: 'blue', risk: '' };
            const colors = colorMap[meta.color] || colorMap.blue;
            return (
              <div key={i} className={`${colors.bg} border ${colors.border} rounded-xl p-5`}>
                <div className="flex items-center gap-2 mb-3">
                  <PieChart className={`w-5 h-5 ${colors.text}`} />
                  <h3 className="text-white font-bold">{meta.name}</h3>
                </div>
                <p className="text-slate-400 text-sm mb-4">{meta.desc}</p>
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-400">Allocation</span>
                    <span className={`font-semibold ${colors.text}`}>{plan.allocation_pct}%</span>
                  </div>
                  <div className="w-full bg-slate-800 rounded-full h-2">
                    <div
                      className={`${colors.bar} h-2 rounded-full transition-all duration-500`}
                      style={{ width: `${Math.min(plan.allocation_pct, 100)}%` }}
                    />
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-400">Positions</span>
                    <span className="text-white">{plan.position_count}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-400">Risk Level</span>
                    <span className="text-slate-300">{meta.risk}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
};

const BenchmarkSection = ({ benchmarks }) => (
  <section className="py-12 border-t border-slate-800/50">
    <div className="max-w-5xl mx-auto px-6">
      <h2 className="text-2xl font-bold text-white mb-6">Benchmark Comparison (90 Days)</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {benchmarks.map((b, i) => {
          const outperforms = b.outperformance_pct > 0;
          return (
            <div key={i} className="bg-slate-900/50 border border-slate-800/50 rounded-xl p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-white font-bold">{b.label}</h3>
                  <span className="text-sm text-slate-500">{b.ticker}</span>
                </div>
                <div className={`flex items-center gap-1 px-3 py-1 rounded-full text-sm font-medium ${outperforms ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}>
                  {outperforms ? <CheckCircle2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                  {outperforms ? '+' : ''}{b.outperformance_pct}%
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-xs text-slate-500 mb-1">Fund Return</div>
                  <div className={`text-lg font-bold ${b.fund_return_pct >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {b.fund_return_pct >= 0 ? '+' : ''}{b.fund_return_pct}%
                  </div>
                </div>
                <div>
                  <div className="text-xs text-slate-500 mb-1">{b.label}</div>
                  <div className={`text-lg font-bold ${b.benchmark_return_pct >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {b.benchmark_return_pct >= 0 ? '+' : ''}{b.benchmark_return_pct}%
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  </section>
);

const CTASection = ({ user }) => (
  <section className="py-16 border-t border-slate-800/50">
    <div className="max-w-3xl mx-auto px-6 text-center">
      <Target className="w-12 h-12 text-emerald-400 mx-auto mb-4" />
      <h2 className="text-3xl font-bold text-white mb-4">Interested in Joining?</h2>
      <p className="text-slate-400 mb-8">
        We're selective about who we bring on as investors. If our approach resonates with you,
        we'd love to have a conversation.
      </p>
      <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
        <a
          href="mailto:david.lang@tovitotrader.com"
          className="px-6 py-3 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl font-medium transition flex items-center gap-2"
        >
          Contact Us <ArrowRight className="w-4 h-4" />
        </a>
        {user ? (
          <Link
            to="/dashboard"
            className="px-6 py-3 bg-slate-800 hover:bg-slate-700 text-white rounded-xl font-medium transition"
          >
            Go to Dashboard
          </Link>
        ) : (
          <Link
            to="/login"
            className="px-6 py-3 bg-slate-800 hover:bg-slate-700 text-white rounded-xl font-medium transition"
          >
            Already an Investor? Sign In
          </Link>
        )}
      </div>
    </div>
  </section>
);

const Footer = () => (
  <footer className="py-8 border-t border-slate-800/50">
    <div className="max-w-5xl mx-auto px-6 text-center">
      <p className="text-xs text-slate-600 max-w-2xl mx-auto">
        Past performance is not indicative of future results. All investments involve risk,
        including the possible loss of principal. Returns shown are net of fees and do not
        account for taxes. This is not an offer to sell or a solicitation of an offer to buy
        any securities.
      </p>
      <p className="text-xs text-slate-700 mt-3">
        &copy; {new Date().getFullYear()} Tovito Trader. All rights reserved.
      </p>
    </div>
  </footer>
);


// ============================================================
// LOADING & ERROR STATES
// ============================================================

const LoadingState = () => (
  <div className="min-h-screen bg-slate-950 flex items-center justify-center">
    <div className="text-center">
      <div className="w-10 h-10 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
      <p className="text-slate-400">Loading fund preview...</p>
    </div>
  </div>
);

const ErrorState = ({ type }) => {
  const messages = {
    invalid: {
      icon: AlertTriangle,
      title: 'Invalid Link',
      desc: 'This link is not valid. Please check the URL or contact us for a new link.',
    },
    expired: {
      icon: Clock,
      title: 'Link Expired',
      desc: 'This preview link has expired or been revoked. Contact us to request a new one.',
    },
    network: {
      icon: AlertTriangle,
      title: 'Connection Error',
      desc: 'Unable to load fund data. Please check your connection and try again.',
    },
  };

  const msg = messages[type] || messages.expired;
  const IconComponent = msg.icon;

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
      <div className="max-w-md text-center">
        <div className="w-16 h-16 bg-slate-800 rounded-full flex items-center justify-center mx-auto mb-6">
          <IconComponent className="w-8 h-8 text-amber-400" />
        </div>
        <h1 className="text-2xl font-bold text-white mb-3">{msg.title}</h1>
        <p className="text-slate-400 mb-8">{msg.desc}</p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <Link
            to="/"
            className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm font-medium transition"
          >
            Visit Our Website
          </Link>
          <a
            href="mailto:david.lang@tovitotrader.com"
            className="px-5 py-2.5 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-sm font-medium transition"
          >
            Contact Us
          </a>
        </div>
      </div>
    </div>
  );
};


export default FundPreviewPage;
