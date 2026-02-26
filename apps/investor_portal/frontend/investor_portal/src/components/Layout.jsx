import { useState } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, TrendingUp, PieChart, ArrowLeftRight,
  FileText, LogOut, HelpCircle, ChevronLeft, ChevronRight, Menu, X, Settings
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const NAV_ITEMS = [
  { path: '/dashboard', label: 'My Dashboard', icon: LayoutDashboard },
  { path: '/performance', label: 'My Performance', icon: TrendingUp },
  { path: '/activity', label: 'My Money', icon: ArrowLeftRight },
  { path: '/portfolio', label: 'Fund Portfolio', icon: PieChart },
  { path: '/reports', label: 'Reports', icon: FileText },
];

const Layout = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const firstName = user?.name?.split(' ')[0] || 'Investor';
  const initial = (user?.name || 'I')[0].toUpperCase();

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-slate-950 flex">
      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed lg:sticky top-0 left-0 h-screen z-50 flex flex-col
          bg-gradient-to-b from-slate-900 via-emerald-900 to-slate-900 text-white transition-all duration-300
          ${mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
          ${collapsed ? 'w-16' : 'w-60'}
        `}
      >
        {/* Logo area */}
        <div className={`flex items-center h-16 border-b border-emerald-800/50 px-4 ${collapsed ? 'justify-center' : 'gap-3'}`}>
          <div className="w-8 h-8 bg-emerald-500 rounded-lg flex items-center justify-center flex-shrink-0 shadow-lg shadow-emerald-500/30">
            <TrendingUp className="w-5 h-5 text-white" />
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <h1 className="font-bold text-sm text-white truncate">TOVITO TRADER</h1>
              <p className="text-[10px] text-slate-400">Investor Portal</p>
            </div>
          )}
          {/* Mobile close */}
          <button
            onClick={() => setMobileOpen(false)}
            className="lg:hidden ml-auto p-1 text-slate-400 hover:text-white"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-4 px-2 space-y-1 overflow-y-auto">
          {NAV_ITEMS.map(({ path, label, icon: Icon }) => (
            <NavLink
              key={path}
              to={path}
              end={path === '/dashboard'}
              onClick={() => setMobileOpen(false)}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors
                ${isActive
                  ? 'bg-emerald-500/15 text-emerald-400 border-l-2 border-emerald-400'
                  : 'text-slate-300 hover:bg-emerald-500/10 hover:text-white border-l-2 border-transparent'
                }
                ${collapsed ? 'justify-center px-2' : ''}`
              }
            >
              <Icon className="w-5 h-5 flex-shrink-0" />
              {!collapsed && <span>{label}</span>}
            </NavLink>
          ))}

          {/* Help link */}
          <button
            onClick={() => { navigate('/help'); setMobileOpen(false); }}
            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors
              text-slate-300 hover:bg-emerald-500/10 hover:text-white border-l-2 border-transparent w-full
              ${collapsed ? 'justify-center px-2' : ''}`}
          >
            <HelpCircle className="w-5 h-5 flex-shrink-0" />
            {!collapsed && <span>Help</span>}
          </button>
        </nav>

        {/* Collapse toggle (desktop only) */}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="hidden lg:flex items-center justify-center p-2 mx-2 mb-2 text-slate-400 hover:text-white hover:bg-emerald-500/10 rounded-lg transition"
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>

        {/* User section */}
        <div className={`border-t border-emerald-800/50 p-3 ${collapsed ? 'flex flex-col items-center' : ''}`}>
          <div className={`flex items-center ${collapsed ? 'justify-center' : 'gap-3'}`}>
            <div className="w-8 h-8 bg-emerald-600 rounded-full flex items-center justify-center flex-shrink-0 text-sm font-bold">
              {initial}
            </div>
            {!collapsed && (
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-white truncate">{firstName}</p>
                <p className="text-[10px] text-slate-400 truncate">{user?.email}</p>
              </div>
            )}
          </div>
          <div className={`flex gap-2 mt-3 ${collapsed ? 'flex-col items-center' : ''}`}>
            <button
              onClick={() => { navigate('/settings'); setMobileOpen(false); }}
              className={`flex items-center gap-2 text-sm text-slate-400 hover:text-white transition flex-1
                ${collapsed ? 'justify-center' : 'px-1'}`}
            >
              <Settings className="w-4 h-4" />
              {!collapsed && <span>Settings</span>}
            </button>
            <button
              onClick={handleLogout}
              className={`flex items-center gap-2 text-sm text-slate-400 hover:text-red-400 transition
                ${collapsed ? 'justify-center' : 'px-1'}`}
            >
              <LogOut className="w-4 h-4" />
              {!collapsed && <span>Sign Out</span>}
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Mobile header */}
        <header className="lg:hidden bg-white dark:bg-slate-900 border-b border-gray-200 dark:border-slate-700 h-14 flex items-center px-4 gap-3">
          <button
            onClick={() => setMobileOpen(true)}
            className="p-2 text-gray-600 dark:text-slate-400 hover:bg-gray-100 dark:hover:bg-slate-700 rounded-lg"
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 bg-emerald-500 rounded-lg flex items-center justify-center">
              <TrendingUp className="w-4 h-4 text-white" />
            </div>
            <span className="font-bold text-gray-900 dark:text-slate-100 text-sm">Tovito Trader</span>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>

        {/* Footer */}
        <footer className="border-t border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900">
          <div className="px-6 py-4">
            <p className="text-center text-xs text-gray-400 dark:text-slate-500">
              &copy; 2026 Tovito Trader. All data as of market close.
            </p>
          </div>
        </footer>
      </div>

      {/* Mobile bottom tab bar */}
      <nav className="lg:hidden fixed bottom-0 left-0 right-0 bg-white dark:bg-slate-900 border-t border-gray-200 dark:border-slate-700 z-30">
        <div className="flex justify-around py-2">
          {NAV_ITEMS.map(({ path, label, icon: Icon }) => (
            <NavLink
              key={path}
              to={path}
              end={path === '/dashboard'}
              className={({ isActive }) =>
                `flex flex-col items-center gap-0.5 px-2 py-1 text-[10px] font-medium transition-colors
                ${isActive ? 'text-emerald-600 dark:text-emerald-400' : 'text-gray-400 dark:text-slate-500'}`
              }
            >
              <Icon className="w-5 h-5" />
              <span>{label}</span>
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  );
};

export default Layout;
