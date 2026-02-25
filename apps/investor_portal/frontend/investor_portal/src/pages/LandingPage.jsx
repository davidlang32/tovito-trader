import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  TrendingUp, ArrowRight, BarChart3, PieChart, Zap, Lock,
  Shield, Clock, Users, CalendarDays, Target, LineChart,
  CheckCircle2, Loader2, Send, Phone, Mail, MessageSquare,
  ChevronDown
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { API_BASE_URL } from '../config';

// ============================================================
// NAVBAR
// ============================================================

const Navbar = ({ scrolled }) => {
  const { user } = useAuth();

  return (
    <nav className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
      scrolled
        ? 'bg-slate-900/95 backdrop-blur-md shadow-lg shadow-black/10 py-3'
        : 'bg-transparent py-5'
    }`}>
      <div className="max-w-7xl mx-auto px-6 flex items-center justify-between">
        {/* Logo */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-emerald-500 rounded-xl flex items-center justify-center shadow-lg shadow-emerald-500/30">
            <TrendingUp className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-white font-bold text-lg tracking-tight">TOVITO TRADER</h1>
            <p className="text-emerald-400/80 text-xs font-medium hidden sm:block">Investment Fund</p>
          </div>
        </div>

        {/* CTAs */}
        <div className="flex items-center gap-3 sm:gap-4">
          {user ? (
            <Link
              to="/dashboard"
              className="bg-emerald-500 hover:bg-emerald-600 text-white px-5 py-2.5 rounded-xl text-sm font-semibold transition shadow-lg shadow-emerald-500/25"
            >
              Go to Dashboard
            </Link>
          ) : (
            <>
              <Link
                to="/login"
                className="text-white/80 hover:text-white text-sm font-medium transition hidden sm:inline-block"
              >
                Sign In
              </Link>
              <a
                href="#inquiry"
                className="bg-emerald-500 hover:bg-emerald-600 text-white px-5 py-2.5 rounded-xl text-sm font-semibold transition shadow-lg shadow-emerald-500/25"
              >
                Get Started
              </a>
            </>
          )}
        </div>
      </div>
    </nav>
  );
};

// ============================================================
// HERO SECTION
// ============================================================

const HeroSection = () => (
  <section className="relative min-h-screen flex items-center justify-center overflow-hidden bg-gradient-to-br from-slate-900 via-emerald-900 to-slate-900">
    {/* Animated background elements */}
    <div className="absolute inset-0">
      <div className="absolute top-20 left-10 w-72 h-72 bg-emerald-500/10 rounded-full blur-3xl animate-pulse" />
      <div className="absolute bottom-20 right-10 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />
      <div className="absolute top-1/2 left-1/3 w-48 h-48 bg-emerald-400/5 rounded-full blur-2xl animate-pulse" style={{ animationDelay: '2s' }} />
      <div className="absolute top-1/4 right-1/4 w-64 h-64 bg-blue-400/5 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '3s' }} />
    </div>

    {/* Grid pattern overlay */}
    <div className="absolute inset-0 opacity-[0.03]" style={{
      backgroundImage: 'linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)',
      backgroundSize: '40px 40px'
    }} />

    <div className="relative z-10 max-w-5xl mx-auto px-6 text-center pt-24 pb-16">
      <div className="inline-flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/20 rounded-full px-4 py-1.5 mb-8">
        <div className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
        <span className="text-emerald-300 text-xs font-medium tracking-wider uppercase">Actively Trading</span>
      </div>

      <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-white leading-tight mb-6">
        Professional Fund Management,{' '}
        <span className="text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-blue-400">
          Personalized for You
        </span>
      </h1>

      <p className="text-slate-400 text-base sm:text-lg max-w-2xl mx-auto mb-10 leading-relaxed">
        Join a select group of investors benefiting from active day trading strategies.
        Track your portfolio in real-time with daily NAV pricing,
        professional-grade analytics, and full transparency.
      </p>

      <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
        <a
          href="#inquiry"
          className="flex items-center gap-2 bg-emerald-500 hover:bg-emerald-600 text-white px-8 py-3.5 rounded-xl text-base font-semibold transition shadow-xl shadow-emerald-500/25 hover:shadow-emerald-500/40"
        >
          Learn More
          <ArrowRight className="w-5 h-5" />
        </a>
        <a
          href="#how-it-works"
          className="flex items-center gap-2 text-slate-300 hover:text-white px-6 py-3.5 rounded-xl text-base font-medium transition border border-slate-700 hover:border-slate-500"
        >
          How It Works
          <ChevronDown className="w-4 h-4" />
        </a>
      </div>
    </div>

    {/* Bottom fade to next section */}
    <div className="absolute bottom-0 left-0 right-0 h-24 bg-gradient-to-t from-slate-950 to-transparent" />
  </section>
);

// ============================================================
// TEASER STATS BAR
// ============================================================

const TeaserStatsBar = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/public/teaser-stats`);
        if (res.ok) {
          const data = await res.json();
          if (!cancelled) setStats(data);
        }
      } catch {
        // Silently fail — stats bar just won't show
      }
      if (!cancelled) setLoading(false);
    })();

    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <section className="bg-slate-950 py-8">
        <div className="max-w-5xl mx-auto px-6">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
            {[1, 2, 3, 4].map(i => (
              <div key={i} className="text-center">
                <div className="h-8 w-20 bg-slate-800 rounded-lg mx-auto mb-2 animate-pulse" />
                <div className="h-4 w-24 bg-slate-800 rounded mx-auto animate-pulse" />
              </div>
            ))}
          </div>
        </div>
      </section>
    );
  }

  if (!stats) return null;

  const items = [
    {
      value: `${stats.since_inception_pct >= 0 ? '+' : ''}${stats.since_inception_pct}%`,
      label: 'Since Inception',
      color: stats.since_inception_pct >= 0 ? 'text-emerald-400' : 'text-red-400',
    },
    {
      value: stats.total_investors,
      label: 'Active Investors',
      color: 'text-blue-400',
    },
    {
      value: stats.trading_days,
      label: 'Trading Days',
      color: 'text-purple-400',
    },
    {
      value: `Since ${new Date(stats.inception_date + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', year: 'numeric' })}`,
      label: 'Actively Trading',
      color: 'text-amber-400',
    },
  ];

  return (
    <section className="bg-slate-950 py-8 border-t border-slate-800/50">
      <div className="max-w-5xl mx-auto px-6">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
          {items.map((item, i) => (
            <div key={i} className="text-center">
              <p className={`text-2xl sm:text-3xl font-bold ${item.color}`}>{item.value}</p>
              <p className="text-slate-500 text-xs font-medium uppercase tracking-wider mt-1">{item.label}</p>
            </div>
          ))}
        </div>
        <p className="text-center text-slate-600 text-[10px] mt-4">
          As of {stats.as_of_date}. Past performance does not guarantee future results.
        </p>
      </div>
    </section>
  );
};

// ============================================================
// HOW IT WORKS SECTION
// ============================================================

const HowItWorksSection = () => {
  const steps = [
    {
      step: '01',
      icon: Target,
      title: 'Invest',
      description: 'Start with a contribution to the fund. You receive shares priced at the daily NAV, just like a mutual fund. Your money is pooled with other investors for maximum trading power.',
      color: 'text-emerald-400',
      bg: 'bg-emerald-500/10',
      border: 'border-emerald-500/20',
    },
    {
      step: '02',
      icon: LineChart,
      title: 'We Trade',
      description: 'We trade momentum-based leveraged options to maximize capital efficiency in a long portfolio. When the market trends sideways or down, we rotate into interest-bearing treasuries and wait for the next opportunity.',
      color: 'text-blue-400',
      bg: 'bg-blue-500/10',
      border: 'border-blue-500/20',
    },
    {
      step: '03',
      icon: TrendingUp,
      title: 'You Earn',
      description: 'Track your returns through our investor portal with interactive charts, benchmark comparisons, and detailed analytics. Your shares appreciate as the fund grows.',
      color: 'text-purple-400',
      bg: 'bg-purple-500/10',
      border: 'border-purple-500/20',
    },
  ];

  return (
    <section id="how-it-works" className="bg-slate-950 py-20">
      <div className="max-w-6xl mx-auto px-6">
        <div className="text-center mb-14">
          <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">How It Works</h2>
          <p className="text-slate-400 text-base max-w-xl mx-auto">
            A simple, transparent process from investment to returns.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {steps.map((s, i) => (
            <div key={i} className={`relative rounded-2xl border ${s.border} ${s.bg} p-8 transition hover:scale-[1.02] hover:shadow-xl`}>
              <div className="flex items-center gap-3 mb-5">
                <span className={`text-xs font-bold ${s.color} opacity-60`}>{s.step}</span>
                <div className={`w-10 h-10 rounded-xl ${s.bg} flex items-center justify-center`}>
                  <s.icon className={`w-5 h-5 ${s.color}`} />
                </div>
              </div>
              <h3 className="text-xl font-bold text-white mb-3">{s.title}</h3>
              <p className="text-slate-400 text-sm leading-relaxed">{s.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

// ============================================================
// FEATURES SECTION
// ============================================================

const FeaturesSection = () => {
  const features = [
    {
      icon: BarChart3,
      title: 'Daily NAV Pricing',
      description: 'Your portfolio is valued every trading day at market close. No guessing, no delays.',
      color: 'text-emerald-400',
      bg: 'bg-emerald-500/10',
    },
    {
      icon: LineChart,
      title: 'Interactive Charts',
      description: 'Professional TradingView-powered charts with crosshair tooltips, time ranges, and zoom.',
      color: 'text-blue-400',
      bg: 'bg-blue-500/10',
    },
    {
      icon: PieChart,
      title: 'Benchmark Comparisons',
      description: 'See how the fund performs against the S&P 500, Nasdaq, and Bitcoin in real-time.',
      color: 'text-purple-400',
      bg: 'bg-purple-500/10',
    },
    {
      icon: Clock,
      title: 'Real-Time Visibility',
      description: 'Full transparency into fund holdings, positions, and risk metrics. Nothing hidden.',
      color: 'text-amber-400',
      bg: 'bg-amber-500/10',
    },
    {
      icon: Shield,
      title: 'Tax-Efficient Structure',
      description: 'Pass-through tax entity with quarterly settlement. No surprise withholdings on withdrawals.',
      color: 'text-cyan-400',
      bg: 'bg-cyan-500/10',
    },
    {
      icon: Lock,
      title: 'Bank-Grade Security',
      description: 'Fernet encryption at rest, bcrypt authentication, JWT tokens, and automatic session management.',
      color: 'text-rose-400',
      bg: 'bg-rose-500/10',
    },
  ];

  return (
    <section className="bg-gradient-to-b from-slate-950 to-slate-900 py-20">
      <div className="max-w-6xl mx-auto px-6">
        <div className="text-center mb-14">
          <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">Why Tovito Trader</h2>
          <p className="text-slate-400 text-base max-w-xl mx-auto">
            Built for serious investors who want transparency, technology, and trust.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((f, i) => (
            <div key={i} className="rounded-2xl border border-slate-800 bg-slate-900/50 p-6 hover:border-slate-700 transition group">
              <div className={`w-12 h-12 rounded-xl ${f.bg} flex items-center justify-center mb-4 group-hover:scale-110 transition`}>
                <f.icon className={`w-6 h-6 ${f.color}`} />
              </div>
              <h3 className="text-lg font-semibold text-white mb-2">{f.title}</h3>
              <p className="text-slate-400 text-sm leading-relaxed">{f.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

// ============================================================
// INQUIRY FORM SECTION
// ============================================================

const InquiryFormSection = () => {
  const [form, setForm] = useState({ name: '', email: '', phone: '', message: '' });
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');

  const handleChange = (e) => {
    setForm(prev => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE_URL}/public/inquiry`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: form.name.trim(),
          email: form.email.trim(),
          phone: form.phone.trim() || null,
          message: form.message.trim() || null,
        }),
      });

      if (res.ok) {
        setSubmitted(true);
      } else if (res.status === 429) {
        setError('Too many requests. Please try again later.');
      } else {
        const data = await res.json().catch(() => ({}));
        setError(data.detail || 'Something went wrong. Please try again.');
      }
    } catch {
      setError('Network error. Please check your connection and try again.');
    }

    setLoading(false);
  };

  return (
    <section id="inquiry" className="relative bg-gradient-to-b from-slate-900 to-slate-950 py-20">
      {/* Subtle background glow */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[600px] bg-emerald-500/5 rounded-full blur-3xl" />
      </div>

      <div className="relative z-10 max-w-2xl mx-auto px-6">
        <div className="text-center mb-10">
          <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">Ready to Learn More?</h2>
          <p className="text-slate-400 text-base max-w-lg mx-auto">
            Submit your information and a member of our team will reach out to discuss
            how Tovito Trader can help you meet your investment goals.
          </p>
        </div>

        {submitted ? (
          <div className="bg-slate-800/50 border border-emerald-500/30 rounded-2xl p-10 text-center">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-emerald-500/10 rounded-full mb-5">
              <CheckCircle2 className="w-8 h-8 text-emerald-400" />
            </div>
            <h3 className="text-2xl font-bold text-white mb-3">Thank You!</h3>
            <p className="text-slate-400 text-base max-w-md mx-auto">
              We've received your inquiry. A member of our team will be in touch shortly
              to share more about the fund and answer any questions you may have.
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-8 sm:p-10 shadow-2xl">
            {error && (
              <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                {error}
              </div>
            )}

            <div className="space-y-5">
              {/* Name */}
              <div>
                <label className="text-xs text-slate-400 font-semibold uppercase tracking-wider mb-1.5 block">
                  Full Name *
                </label>
                <div className="relative">
                  <Users className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                  <input
                    type="text"
                    name="name"
                    value={form.name}
                    onChange={handleChange}
                    required
                    maxLength={100}
                    placeholder="John Smith"
                    className="w-full pl-10 pr-4 py-3 bg-slate-900/80 border border-slate-700 rounded-xl text-white placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition"
                  />
                </div>
              </div>

              {/* Email */}
              <div>
                <label className="text-xs text-slate-400 font-semibold uppercase tracking-wider mb-1.5 block">
                  Email Address *
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                  <input
                    type="email"
                    name="email"
                    value={form.email}
                    onChange={handleChange}
                    required
                    placeholder="john@example.com"
                    className="w-full pl-10 pr-4 py-3 bg-slate-900/80 border border-slate-700 rounded-xl text-white placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition"
                  />
                </div>
              </div>

              {/* Phone */}
              <div>
                <label className="text-xs text-slate-400 font-semibold uppercase tracking-wider mb-1.5 block">
                  Phone <span className="text-slate-600">(optional)</span>
                </label>
                <div className="relative">
                  <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                  <input
                    type="tel"
                    name="phone"
                    value={form.phone}
                    onChange={handleChange}
                    maxLength={20}
                    placeholder="(555) 123-4567"
                    className="w-full pl-10 pr-4 py-3 bg-slate-900/80 border border-slate-700 rounded-xl text-white placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition"
                  />
                </div>
              </div>

              {/* Message */}
              <div>
                <label className="text-xs text-slate-400 font-semibold uppercase tracking-wider mb-1.5 block">
                  Message <span className="text-slate-600">(optional)</span>
                </label>
                <div className="relative">
                  <MessageSquare className="absolute left-3 top-3.5 w-4 h-4 text-slate-500" />
                  <textarea
                    name="message"
                    value={form.message}
                    onChange={handleChange}
                    maxLength={1000}
                    rows={4}
                    placeholder="Tell us about your investment goals..."
                    className="w-full pl-10 pr-4 py-3 bg-slate-900/80 border border-slate-700 rounded-xl text-white placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent resize-none transition"
                  />
                </div>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || !form.name.trim() || !form.email.trim()}
              className="w-full mt-6 flex items-center justify-center gap-2 bg-emerald-500 hover:bg-emerald-600 text-white py-3.5 rounded-xl text-sm font-semibold transition shadow-lg shadow-emerald-500/25 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
              {loading ? 'Submitting...' : 'Submit Inquiry'}
            </button>

            <p className="text-center text-slate-600 text-[10px] mt-4">
              By submitting, you agree to be contacted by our team. We will never share your information.
            </p>
          </form>
        )}
      </div>
    </section>
  );
};

// ============================================================
// FOOTER
// ============================================================

const Footer = () => (
  <footer className="bg-slate-950 border-t border-slate-800/50 py-10">
    <div className="max-w-6xl mx-auto px-6">
      <div className="flex flex-col sm:flex-row items-center justify-between gap-6">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-emerald-500 rounded-lg flex items-center justify-center">
            <TrendingUp className="w-4 h-4 text-white" />
          </div>
          <span className="text-white font-bold text-sm">TOVITO TRADER</span>
        </div>

        <div className="flex items-center gap-6 text-xs text-slate-500">
          <a href="mailto:support@tovitotrader.com" className="hover:text-slate-300 transition">
            Contact
          </a>
          <Link to="/login" className="hover:text-slate-300 transition">
            Investor Login
          </Link>
        </div>
      </div>

      <div className="mt-6 pt-6 border-t border-slate-800/50 text-center">
        <p className="text-slate-600 text-[10px] max-w-2xl mx-auto leading-relaxed">
          Past performance does not guarantee future results. Investing in the fund involves risk,
          including the possible loss of principal. This website is for informational purposes only
          and does not constitute an offer to sell or a solicitation of an offer to buy any securities.
        </p>
        <p className="text-slate-600 text-[10px] mt-3">
          &copy; 2026 Tovito Trader. All rights reserved.
        </p>
      </div>
    </div>
  </footer>
);

// ============================================================
// LANDING PAGE
// ============================================================

const LandingPage = () => {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 50);
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <div className="min-h-screen bg-slate-950">
      <Navbar scrolled={scrolled} />
      <HeroSection />
      <TeaserStatsBar />
      <HowItWorksSection />
      <FeaturesSection />
      <InquiryFormSection />
      <Footer />
    </div>
  );
};

export default LandingPage;
