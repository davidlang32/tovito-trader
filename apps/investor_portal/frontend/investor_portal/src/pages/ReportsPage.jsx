import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileText, ArrowLeft, Calendar, Activity, Download,
  Loader2, CheckCircle2, AlertCircle, Table2
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { API_BASE_URL } from '../config';

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

const ReportsPage = ({ onBack }) => {
  const navigate = useNavigate();
  const { getAuthHeaders } = useAuth();
  const [reportType, setReportType] = useState('monthly');
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [year, setYear] = useState(2026);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [generating, setGenerating] = useState(false);
  const [jobId, setJobId] = useState(null);
  const [jobStatus, setJobStatus] = useState(null);
  const [error, setError] = useState(null);

  const handleBack = onBack || (() => navigate('/dashboard'));

  useEffect(() => {
    if (!jobId) return;
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/reports/status/${jobId}`, {
          headers: getAuthHeaders(),
        });
        if (!res.ok) throw new Error('Status check failed');
        const data = await res.json();
        setJobStatus(data);
        if (data.status === 'completed' || data.status === 'failed') {
          clearInterval(interval);
          setGenerating(false);
        }
      } catch {
        clearInterval(interval);
        setGenerating(false);
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [jobId, getAuthHeaders]);

  const handleGenerate = async () => {
    setGenerating(true);
    setJobStatus(null);
    setError(null);

    let endpoint, body;
    if (reportType === 'monthly') {
      endpoint = '/reports/monthly';
      body = { month, year };
    } else if (reportType === 'custom') {
      if (!startDate || !endDate) { setError('Please select both dates'); setGenerating(false); return; }
      endpoint = '/reports/custom';
      body = { start_date: startDate, end_date: endDate };
    } else {
      endpoint = `/reports/ytd?year=${year}`;
      body = null;
    }

    try {
      const res = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: 'POST',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Request failed');
      }
      const data = await res.json();
      setJobId(data.job_id);
      setJobStatus(data);
    } catch (e) {
      setError(e.message);
      setGenerating(false);
    }
  };

  const handleDownload = async () => {
    if (!jobStatus?.download_url) return;
    const res = await fetch(`${API_BASE_URL}${jobStatus.download_url}`, {
      headers: getAuthHeaders(),
    });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'report.pdf';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center h-16 gap-4">
            <button onClick={handleBack} className="p-2 hover:bg-gray-100 rounded-lg">
              <ArrowLeft className="w-5 h-5 text-gray-600" />
            </button>
            <div className="flex items-center gap-2">
              <FileText className="w-5 h-5 text-blue-600" />
              <h1 className="font-bold text-gray-900">Generate Reports</h1>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex gap-2 mb-6">
          {[
            { key: 'monthly', label: 'Monthly Statement', icon: Calendar },
            { key: 'custom', label: 'Custom Range', icon: Table2 },
            { key: 'ytd', label: 'Year-to-Date', icon: Activity },
          ].map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => { setReportType(key); setJobStatus(null); setError(null); }}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition ${
                reportType === key
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'
              }`}
            >
              <Icon className="w-4 h-4" />
              {label}
            </button>
          ))}
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-6">
          {reportType === 'monthly' && (
            <div className="flex gap-4 items-end">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Month</label>
                <select
                  value={month}
                  onChange={e => setMonth(Number(e.target.value))}
                  className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
                >
                  {MONTHS.map((m, i) => (
                    <option key={i} value={i + 1}>{m}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Year</label>
                <select
                  value={year}
                  onChange={e => setYear(Number(e.target.value))}
                  className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
                >
                  <option value={2026}>2026</option>
                  <option value={2027}>2027</option>
                </select>
              </div>
              <button
                onClick={handleGenerate}
                disabled={generating}
                className="px-6 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
              >
                {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                Generate
              </button>
            </div>
          )}

          {reportType === 'custom' && (
            <div className="flex gap-4 items-end">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Start Date</label>
                <input
                  type="date"
                  value={startDate}
                  onChange={e => setStartDate(e.target.value)}
                  className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">End Date</label>
                <input
                  type="date"
                  value={endDate}
                  onChange={e => setEndDate(e.target.value)}
                  className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
                />
              </div>
              <button
                onClick={handleGenerate}
                disabled={generating}
                className="px-6 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
              >
                {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                Generate
              </button>
            </div>
          )}

          {reportType === 'ytd' && (
            <div className="flex gap-4 items-end">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Year</label>
                <select
                  value={year}
                  onChange={e => setYear(Number(e.target.value))}
                  className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
                >
                  <option value={2026}>2026</option>
                  <option value={2027}>2027</option>
                </select>
              </div>
              <button
                onClick={handleGenerate}
                disabled={generating}
                className="px-6 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
              >
                {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                Generate
              </button>
            </div>
          )}
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4 text-red-700 text-sm">
            {error}
          </div>
        )}

        {jobStatus && (
          <div className={`rounded-lg p-4 mb-4 text-sm ${
            jobStatus.status === 'completed' ? 'bg-green-50 border border-green-200 text-green-700'
            : jobStatus.status === 'failed' ? 'bg-red-50 border border-red-200 text-red-700'
            : 'bg-blue-50 border border-blue-200 text-blue-700'
          }`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {jobStatus.status === 'completed' ? (
                  <CheckCircle2 className="w-5 h-5" />
                ) : jobStatus.status === 'failed' ? (
                  <AlertCircle className="w-5 h-5" />
                ) : (
                  <Loader2 className="w-5 h-5 animate-spin" />
                )}
                <span>{jobStatus.message}</span>
              </div>
              {jobStatus.status === 'completed' && (
                <button
                  onClick={handleDownload}
                  className="px-4 py-1.5 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 flex items-center gap-1.5"
                >
                  <Download className="w-4 h-4" />
                  Download PDF
                </button>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

export default ReportsPage;
