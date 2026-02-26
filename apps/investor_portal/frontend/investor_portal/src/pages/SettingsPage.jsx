import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Settings, User, Lock, Mail, Briefcase, Shield, CheckCircle2,
  AlertCircle, Loader2, Edit3, Save, X, ExternalLink, ArrowDownRight,
  ArrowUpRight, ChevronDown, ChevronUp, Phone, MapPin, Globe, Moon, Sun, Monitor
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import { API_BASE_URL } from '../config';

// ============================================================
// HELPERS
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

const FieldRow = ({ label, value, icon: Icon }) => (
  <div className="flex items-start gap-3 py-2.5 border-b border-gray-50 dark:border-slate-800/30 last:border-0">
    {Icon && <Icon className="w-4 h-4 text-gray-400 dark:text-slate-500 mt-0.5 flex-shrink-0" />}
    <div className="flex-1 min-w-0">
      <p className="text-[10px] text-gray-400 dark:text-slate-500 font-semibold uppercase tracking-wider">{label}</p>
      <p className="text-sm text-gray-900 dark:text-slate-100 mt-0.5">{value || <span className="text-gray-300 dark:text-slate-600 italic">Not provided</span>}</p>
    </div>
  </div>
);

const StatusBadge = ({ onFile, label }) => (
  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
    onFile
      ? 'bg-emerald-50 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800'
      : 'bg-gray-50 dark:bg-slate-700 text-gray-400 dark:text-slate-500 border border-gray-200 dark:border-slate-700'
  }`}>
    {onFile ? <CheckCircle2 className="w-3 h-3" /> : <AlertCircle className="w-3 h-3" />}
    {onFile ? `${label} on file` : `No ${label} on file`}
  </span>
);

// ============================================================
// PROFILE SECTION
// ============================================================

const ProfileSection = () => {
  const { user, getAuthHeaders } = useAuth();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState(null);
  const [form, setForm] = useState({});

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/profile`, { headers: getAuthHeaders() });
        if (res.ok) {
          const data = await res.json();
          setProfile(data);
          setForm({
            full_legal_name: data.full_legal_name || '',
            home_address_line1: data.home_address_line1 || '',
            home_address_line2: data.home_address_line2 || '',
            home_city: data.home_city || '',
            home_state: data.home_state || '',
            home_zip: data.home_zip || '',
            home_country: data.home_country || '',
            email_primary: data.email_primary || '',
            phone_mobile: data.phone_mobile || '',
          });
        }
      } catch { /* ignore */ }
      setLoading(false);
    })();
  }, [getAuthHeaders]);

  const handleSave = async () => {
    setSaving(true);
    setSaveMsg(null);
    try {
      const res = await fetch(`${API_BASE_URL}/profile/contact`, {
        method: 'PUT',
        headers: getAuthHeaders(),
        body: JSON.stringify(form),
      });
      if (res.ok) {
        setSaveMsg({ type: 'success', text: 'Contact info updated' });
        setProfile(prev => ({ ...prev, ...form }));
        setEditing(false);
      } else {
        setSaveMsg({ type: 'error', text: 'Failed to save' });
      }
    } catch {
      setSaveMsg({ type: 'error', text: 'Network error' });
    }
    setSaving(false);
    setTimeout(() => setSaveMsg(null), 3000);
  };

  if (loading) {
    return (
      <div className="bg-white dark:bg-slate-800/50 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700/50 p-6 mb-6">
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-6 h-6 animate-spin text-gray-400 dark:text-slate-500" />
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-slate-800/50 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700/50 p-6 mb-6">
      <SectionHeader icon={User} title="Profile Information" subtitle="Your account and contact details" iconColor="text-blue-600 dark:text-blue-400" iconBg="bg-blue-50 dark:bg-blue-900/30">
        {!editing ? (
          <button
            onClick={() => setEditing(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30 rounded-lg hover:bg-blue-100 dark:hover:bg-blue-900/30 transition"
          >
            <Edit3 className="w-3.5 h-3.5" />
            Edit
          </button>
        ) : (
          <div className="flex gap-2">
            <button
              onClick={() => setEditing(false)}
              className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-gray-500 dark:text-slate-400 bg-gray-100 dark:bg-slate-700 rounded-lg hover:bg-gray-200 dark:hover:bg-slate-600 transition"
            >
              <X className="w-3.5 h-3.5" />
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition disabled:opacity-50"
            >
              {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
              Save
            </button>
          </div>
        )}
      </SectionHeader>

      {saveMsg && (
        <div className={`mb-4 px-3 py-2 rounded-lg text-xs font-medium ${
          saveMsg.type === 'success' ? 'bg-emerald-50 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300' : 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300'
        }`}>
          {saveMsg.text}
        </div>
      )}

      {editing ? (
        /* Edit Form */
        <div className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] text-gray-500 dark:text-slate-400 font-semibold uppercase tracking-wider">Full Legal Name</label>
              <input
                type="text"
                value={form.full_legal_name}
                onChange={e => setForm(f => ({ ...f, full_legal_name: e.target.value }))}
                className="w-full mt-1 px-3 py-2 text-sm border border-gray-200 dark:border-slate-600 dark:bg-slate-700/50 dark:text-slate-100 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="text-[10px] text-gray-500 dark:text-slate-400 font-semibold uppercase tracking-wider">Email</label>
              <input
                type="email"
                value={form.email_primary}
                onChange={e => setForm(f => ({ ...f, email_primary: e.target.value }))}
                className="w-full mt-1 px-3 py-2 text-sm border border-gray-200 dark:border-slate-600 dark:bg-slate-700/50 dark:text-slate-100 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="text-[10px] text-gray-500 dark:text-slate-400 font-semibold uppercase tracking-wider">Mobile Phone</label>
              <input
                type="tel"
                value={form.phone_mobile}
                onChange={e => setForm(f => ({ ...f, phone_mobile: e.target.value }))}
                className="w-full mt-1 px-3 py-2 text-sm border border-gray-200 dark:border-slate-600 dark:bg-slate-700/50 dark:text-slate-100 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="text-[10px] text-gray-500 dark:text-slate-400 font-semibold uppercase tracking-wider">Country</label>
              <input
                type="text"
                value={form.home_country}
                onChange={e => setForm(f => ({ ...f, home_country: e.target.value }))}
                className="w-full mt-1 px-3 py-2 text-sm border border-gray-200 dark:border-slate-600 dark:bg-slate-700/50 dark:text-slate-100 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
          <div>
            <label className="text-[10px] text-gray-500 dark:text-slate-400 font-semibold uppercase tracking-wider">Address Line 1</label>
            <input
              type="text"
              value={form.home_address_line1}
              onChange={e => setForm(f => ({ ...f, home_address_line1: e.target.value }))}
              className="w-full mt-1 px-3 py-2 text-sm border border-gray-200 dark:border-slate-600 dark:bg-slate-700/50 dark:text-slate-100 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="text-[10px] text-gray-500 dark:text-slate-400 font-semibold uppercase tracking-wider">Address Line 2</label>
            <input
              type="text"
              value={form.home_address_line2}
              onChange={e => setForm(f => ({ ...f, home_address_line2: e.target.value }))}
              className="w-full mt-1 px-3 py-2 text-sm border border-gray-200 dark:border-slate-600 dark:bg-slate-700/50 dark:text-slate-100 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-[10px] text-gray-500 dark:text-slate-400 font-semibold uppercase tracking-wider">City</label>
              <input
                type="text"
                value={form.home_city}
                onChange={e => setForm(f => ({ ...f, home_city: e.target.value }))}
                className="w-full mt-1 px-3 py-2 text-sm border border-gray-200 dark:border-slate-600 dark:bg-slate-700/50 dark:text-slate-100 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="text-[10px] text-gray-500 dark:text-slate-400 font-semibold uppercase tracking-wider">State</label>
              <input
                type="text"
                value={form.home_state}
                onChange={e => setForm(f => ({ ...f, home_state: e.target.value }))}
                className="w-full mt-1 px-3 py-2 text-sm border border-gray-200 dark:border-slate-600 dark:bg-slate-700/50 dark:text-slate-100 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="text-[10px] text-gray-500 dark:text-slate-400 font-semibold uppercase tracking-wider">ZIP</label>
              <input
                type="text"
                value={form.home_zip}
                onChange={e => setForm(f => ({ ...f, home_zip: e.target.value }))}
                className="w-full mt-1 px-3 py-2 text-sm border border-gray-200 dark:border-slate-600 dark:bg-slate-700/50 dark:text-slate-100 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
        </div>
      ) : (
        /* View Mode */
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-x-8">
          <div>
            <FieldRow icon={User} label="Full Legal Name" value={profile?.full_legal_name} />
            <FieldRow icon={Mail} label="Email" value={profile?.email_primary || user?.email} />
            <FieldRow icon={Phone} label="Mobile Phone" value={profile?.phone_mobile} />
            <FieldRow icon={MapPin} label="Address" value={
              profile?.home_address_line1
                ? `${profile.home_address_line1}${profile.home_address_line2 ? ', ' + profile.home_address_line2 : ''}, ${profile.home_city || ''}, ${profile.home_state || ''} ${profile.home_zip || ''}`
                : null
            } />
          </div>
          <div>
            <FieldRow icon={Globe} label="Citizenship" value={profile?.citizenship} />
            <FieldRow icon={Briefcase} label="Employment" value={
              profile?.employment_status
                ? `${profile.employment_status}${profile.employer_name ? ' at ' + profile.employer_name : ''}`
                : null
            } />
            <div className="flex gap-2 mt-3">
              <StatusBadge onFile={profile?.ssn_on_file} label="SSN" />
              <StatusBadge onFile={profile?.bank_on_file} label="Bank info" />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// ============================================================
// CHANGE PASSWORD SECTION
// ============================================================

const PasswordSection = () => {
  const { user, getAuthHeaders } = useAuth();
  const [sending, setSending] = useState(false);
  const [message, setMessage] = useState(null);

  const handleResetRequest = async () => {
    setSending(true);
    setMessage(null);
    try {
      const res = await fetch(`${API_BASE_URL}/auth/forgot-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: user?.email }),
      });
      if (res.ok) {
        setMessage({ type: 'success', text: 'Password reset link sent to your email. Check your inbox.' });
      } else {
        setMessage({ type: 'error', text: 'Unable to send reset link. Please try again.' });
      }
    } catch {
      setMessage({ type: 'error', text: 'Network error. Please try again.' });
    }
    setSending(false);
  };

  return (
    <div className="bg-white dark:bg-slate-800/50 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700/50 p-6 mb-6">
      <SectionHeader icon={Lock} title="Change Password" subtitle="Update your account password" iconColor="text-amber-600 dark:text-amber-400" iconBg="bg-amber-50 dark:bg-amber-900/30" />

      <p className="text-sm text-gray-600 dark:text-slate-400 mb-4">
        To change your password, we'll send a secure reset link to your email address
        (<span className="font-medium">{user?.email}</span>). Click the link to set a new password.
      </p>

      {message && (
        <div className={`mb-4 px-3 py-2 rounded-lg text-sm ${
          message.type === 'success' ? 'bg-emerald-50 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300' : 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300'
        }`}>
          {message.type === 'success' && <CheckCircle2 className="w-4 h-4 inline mr-1.5" />}
          {message.text}
        </div>
      )}

      <button
        onClick={handleResetRequest}
        disabled={sending}
        className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-900/30 border border-amber-200 dark:border-amber-800 rounded-lg hover:bg-amber-100 dark:hover:bg-amber-900/30 transition disabled:opacity-50"
      >
        {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Lock className="w-4 h-4" />}
        {sending ? 'Sending...' : 'Send Password Reset Link'}
      </button>
    </div>
  );
};

// ============================================================
// COMMUNICATION PREFERENCES
// ============================================================

const PreferencesSection = () => {
  const { getAuthHeaders } = useAuth();
  const [prefs, setPrefs] = useState({ communication_preference: 'email', statement_delivery: 'electronic' });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/profile`, { headers: getAuthHeaders() });
        if (res.ok) {
          const data = await res.json();
          setPrefs({
            communication_preference: data.communication_preference || 'email',
            statement_delivery: data.statement_delivery || 'electronic',
          });
        }
      } catch { /* ignore */ }
      setLoading(false);
    })();
  }, [getAuthHeaders]);

  const handleSave = async (key, value) => {
    setSaving(true);
    setSaveMsg(null);
    const updated = { ...prefs, [key]: value };
    setPrefs(updated);

    try {
      const res = await fetch(`${API_BASE_URL}/profile/contact`, {
        method: 'PUT',
        headers: getAuthHeaders(),
        body: JSON.stringify(updated),
      });
      if (res.ok) {
        setSaveMsg({ type: 'success', text: 'Preference saved' });
      }
    } catch { /* ignore */ }
    setSaving(false);
    setTimeout(() => setSaveMsg(null), 2000);
  };

  if (loading) return null;

  const ToggleOption = ({ label, description, groupKey, value, currentValue }) => (
    <button
      onClick={() => handleSave(groupKey, value)}
      className={`flex-1 p-3 rounded-lg border-2 text-left transition ${
        currentValue === value
          ? 'border-emerald-500 dark:border-emerald-400 bg-emerald-50/50 dark:bg-emerald-900/20'
          : 'border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 hover:border-gray-300 dark:hover:border-slate-500'
      }`}
    >
      <div className="flex items-center gap-2">
        <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
          currentValue === value ? 'border-emerald-500 dark:border-emerald-400' : 'border-gray-300 dark:border-slate-600'
        }`}>
          {currentValue === value && <div className="w-2 h-2 rounded-full bg-emerald-500" />}
        </div>
        <span className="text-sm font-medium text-gray-900 dark:text-slate-100">{label}</span>
      </div>
      <p className="text-[11px] text-gray-500 dark:text-slate-400 mt-1 ml-6">{description}</p>
    </button>
  );

  return (
    <div className="bg-white dark:bg-slate-800/50 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700/50 p-6 mb-6">
      <SectionHeader icon={Mail} title="Communication Preferences" subtitle="How you'd like to hear from us" iconColor="text-purple-600 dark:text-purple-400" iconBg="bg-purple-50 dark:bg-purple-900/30" />

      {saveMsg && (
        <div className="mb-4 px-3 py-2 rounded-lg text-xs font-medium bg-emerald-50 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300">
          {saveMsg.text}
        </div>
      )}

      <div className="space-y-4">
        <div>
          <p className="text-xs text-gray-500 dark:text-slate-400 font-semibold uppercase tracking-wider mb-2">Communication Method</p>
          <div className="flex gap-3">
            <ToggleOption
              label="Email"
              description="Receive updates and notifications via email"
              groupKey="communication_preference"
              value="email"
              currentValue={prefs.communication_preference}
            />
            <ToggleOption
              label="Portal Only"
              description="Check the portal for all updates — no emails"
              groupKey="communication_preference"
              value="portal"
              currentValue={prefs.communication_preference}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

// ============================================================
// APPEARANCE SECTION
// ============================================================

const AppearanceSection = () => {
  const { darkMode, setDarkMode } = useTheme();

  const ThemeButton = ({ label, icon: Icon, value, description }) => (
    <button
      onClick={() => setDarkMode(value)}
      className={`flex-1 p-3 rounded-lg border-2 text-left transition ${
        darkMode === value
          ? 'border-emerald-500 dark:border-emerald-400 bg-emerald-50/50 dark:bg-emerald-900/20'
          : 'border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800/50 hover:border-gray-300 dark:hover:border-slate-500'
      }`}
    >
      <div className="flex items-center gap-2">
        <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
          darkMode === value ? 'border-emerald-500 dark:border-emerald-400' : 'border-gray-300 dark:border-slate-600'
        }`}>
          {darkMode === value && <div className="w-2 h-2 rounded-full bg-emerald-500" />}
        </div>
        <Icon className="w-4 h-4 text-gray-600 dark:text-slate-400" />
        <span className="text-sm font-medium text-gray-900 dark:text-slate-100">{label}</span>
      </div>
      <p className="text-[11px] text-gray-500 dark:text-slate-400 mt-1 ml-6">{description}</p>
    </button>
  );

  return (
    <div className="bg-white dark:bg-slate-800/50 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700/50 p-6 mb-6">
      <SectionHeader icon={Moon} title="Appearance" subtitle="Customize the look and feel" iconColor="text-indigo-600 dark:text-indigo-400" iconBg="bg-indigo-50 dark:bg-indigo-900/30" />

      <div>
        <p className="text-xs text-gray-500 dark:text-slate-400 font-semibold uppercase tracking-wider mb-2">Theme</p>
        <div className="flex gap-3">
          <ThemeButton
            label="Light"
            icon={Sun}
            value={false}
            description="Light background with dark text"
          />
          <ThemeButton
            label="Dark"
            icon={Moon}
            value={true}
            description="Dark background with light text"
          />
        </div>
      </div>
    </div>
  );
};

// ============================================================
// QUICK LINKS
// ============================================================

const QuickLinks = () => {
  const navigate = useNavigate();

  return (
    <div className="bg-white dark:bg-slate-800/50 rounded-xl shadow-sm border border-gray-100 dark:border-slate-700/50 p-6">
      <SectionHeader icon={ExternalLink} title="Quick Actions" subtitle="Common account actions" iconColor="text-gray-600 dark:text-slate-400" iconBg="bg-gray-50 dark:bg-slate-700" />

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <button
          onClick={() => navigate('/activity')}
          className="flex items-center gap-3 p-4 rounded-xl border border-emerald-200 dark:border-emerald-800 bg-emerald-50/50 dark:bg-emerald-900/20 hover:bg-emerald-50 dark:hover:bg-emerald-900/20 transition text-left"
        >
          <div className="p-2 rounded-lg bg-emerald-100 dark:bg-emerald-900/40">
            <ArrowDownRight className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
          </div>
          <div>
            <p className="text-sm font-semibold text-emerald-700 dark:text-emerald-300">Make a Contribution</p>
            <p className="text-[11px] text-emerald-600 dark:text-emerald-400">Add funds to your account</p>
          </div>
        </button>

        <button
          onClick={() => navigate('/activity')}
          className="flex items-center gap-3 p-4 rounded-xl border border-red-200 dark:border-red-800 bg-red-50/50 dark:bg-red-900/20 hover:bg-red-50 dark:hover:bg-red-900/20 transition text-left"
        >
          <div className="p-2 rounded-lg bg-red-100 dark:bg-red-900/40">
            <ArrowUpRight className="w-5 h-5 text-red-600 dark:text-red-400" />
          </div>
          <div>
            <p className="text-sm font-semibold text-red-700 dark:text-red-300">Request a Withdrawal</p>
            <p className="text-[11px] text-red-600 dark:text-red-400">Withdraw from your account</p>
          </div>
        </button>
      </div>
    </div>
  );
};

// ============================================================
// SETTINGS PAGE
// ============================================================

const SettingsPage = () => {
  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 pb-20 lg:pb-8">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-slate-100">Settings</h2>
        <p className="text-gray-500 dark:text-slate-400 text-sm">Manage your account, profile, and preferences</p>
      </div>

      <ProfileSection />
      <PasswordSection />
      <PreferencesSection />
      <AppearanceSection />
      <QuickLinks />
    </div>
  );
};

export default SettingsPage;
