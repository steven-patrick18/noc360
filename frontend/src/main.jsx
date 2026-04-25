import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Activity,
  AlertTriangle,
  Copy,
  Download,
  Edit3,
  ExternalLink,
  Eye,
  EyeOff,
  Globe2,
  LayoutDashboard,
  LogOut,
  MonitorCog,
  Play,
  Plus,
  ReceiptText,
  RadioTower,
  RefreshCcw,
  Router,
  Search,
  Server,
  Star,
  Trash2,
  Users,
  X,
} from 'lucide-react';
import './styles.css';

const API_BASE_URL = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '');
const statuses = ['Active', 'Pending', 'Inactive'];
const chargeTypes = ['Usage Charges', 'DID Charges', 'Data Charges', 'Server Charges', 'Port Charges', 'Setup Charges', 'Other Charges'];
const ledgerCategories = [...chargeTypes, 'Payment', 'Adjustment'];
const pageKeys = ['dashboard', 'my_dashboard', 'business_ai', 'reports', 'my_reports', 'management_portal', 'billing', 'my_ledger', 'clients', 'cdr', 'my_cdr', 'vos_portals', 'vos_desktop_launcher', 'dialer_clusters', 'rdp_media', 'routing_gateways', 'user_access'];
const modulePageKeys = {
  dashboard: 'dashboard',
  myDashboard: 'my_dashboard',
  businessAi: 'business_ai',
  reports: 'reports',
  myReports: 'my_reports',
  management: 'management_portal',
  billing: 'billing',
  myBilling: 'my_ledger',
  clients: 'clients',
  myCdr: 'my_cdr',
  vos: 'vos_portals',
  vosDesktop: 'vos_desktop_launcher',
  clusters: 'dialer_clusters',
  rdps: 'rdp_media',
  gateways: 'routing_gateways',
  userAccess: 'user_access',
};

const modules = {
  dashboard: { label: 'Command Center', icon: Activity },
  businessAi: { label: 'Intelligence Core', icon: Activity },
  reports: { label: 'Data Intelligence', icon: Download },
  management: { label: 'Management Portal', icon: LayoutDashboard },
  billing: { label: 'Money Engine', icon: ReceiptText },
  clients: { label: 'Clients', icon: Users },
  userAccess: { label: 'User Access', icon: Users },
  vos: {
    label: 'VOS Portals',
    icon: Globe2,
    endpoint: '/vos-portals',
    titleField: 'portal_type',
    fields: [
      ['vos_version', 'VOS Version', 'text'],
      ['portal_type', 'Portal Type', 'text'],
      ['server_ip', 'Server IP', 'text'],
      ['status', 'Status', 'status'],
      ['username', 'Username', 'text'],
      ['password', 'Password', 'text'],
      ['anti_hack_url', 'Anti Hack URL', 'text'],
      ['anti_hack_password', 'Anti Hack Password', 'text'],
      ['uuid', 'UUID', 'text'],
      ['cdr_panel_url', 'CDR Panel URL', 'text'],
      ['web_panel_url', 'Web Panel URL', 'text'],
      ['vos_port', 'VOS Port', 'number'],
      ['vos_desktop_enabled', 'Desktop Enabled', 'boolean'],
      ['vos_notes', 'VOS Notes', 'textarea'],
    ],
  },
  vosDesktop: { label: 'VOS Desktop', icon: Play },
  clusters: {
    label: 'Dialer Clusters',
    icon: RadioTower,
    endpoint: '/dialer-clusters',
    titleField: 'account_name',
    fields: [
      ['cluster_no', 'Cluster No', 'number'],
      ['account_name', 'Cluster Name', 'text'],
      ['db_ip', 'DB IP', 'text'],
      ['web_ips', 'Web IPs', 'textarea'],
      ['asterisk_ips', 'Asterisk IPs', 'textarea'],
      ['inbound_ip', 'Inbound IP', 'text'],
      ['client_id', 'Client', 'client'],
      ['dids_patch', 'DIDs Patch', 'text'],
      ['in_id', 'IN ID', 'text'],
      ['assigned_rdp', 'Assigned RDP', 'rdp'],
      ['assigned_rdp_ip', 'Assigned RDP IP', 'readonly'],
      ['status', 'Status', 'status'],
    ],
  },
  rdps: {
    label: 'Media Nodes',
    icon: MonitorCog,
    endpoint: '/rdps',
    titleField: 'name',
    readOnlyInventory: true,
    fields: [
      ['name', 'RDP', 'readonly'],
      ['ip', 'IP', 'readonly'],
      ['status', 'Status', 'readonlyStatus'],
      ['assigned_to', 'Assigned To', 'readonly'],
      ['assigned_cluster', 'Assigned Cluster', 'readonly'],
      ['used_in_routing', 'Used In Routing', 'readonly'],
      ['usage_status', 'Usage Status', 'readonlyStatus'],
    ],
  },
  gateways: {
    label: 'Traffic Control',
    icon: Router,
    endpoint: '/routing-gateways',
    titleField: 'gateway_name',
    fields: [
      ['gateway_name', 'Gateway Name', 'rtng'],
      ['gateway_ip', 'Gateway IP', 'readonly'],
      ['media1_name', 'Media 1 Name', 'rdp'],
      ['media1_ip', 'Media 1 IP', 'readonly'],
      ['media2_name', 'Media 2 Name', 'rdp'],
      ['media2_ip', 'Media 2 IP', 'readonly'],
      ['carrier_ip', 'Carrier IP', 'text'],
      ['ports', 'Ports', 'text'],
      ['vendor_name', 'Vendor Name', 'text'],
      ['status', 'Status', 'status'],
    ],
  },
};

const customerModules = {
  myDashboard: { label: 'My Dashboard', icon: Activity },
  myBilling: { label: 'My Ledger', icon: ReceiptText },
  myCdr: { label: 'My CDR', icon: RadioTower },
  myReports: { label: 'My Reports', icon: Download },
};

function emptyRecord(fields) {
  return Object.fromEntries(fields.map(([key, , type]) => [key, type === 'number' ? 0 : type === 'boolean' ? false : key === 'status' ? 'Active' : '']));
}

async function request(path, options = {}) {
  const token = localStorage.getItem('noc360_token');
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers,
    ...options,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || 'Request failed');
  }
  return response.json();
}

function StatusPill({ value }) {
  const raw = String(value || 'Unknown');
  const normalized = raw.toLowerCase().trim();
  const statusText = {
    active: '🟢 ONLINE',
    pending: '🟡 WARMING',
    inactive: '🔴 OFFLINE',
    'high usage': '⚡ HIGH LOAD',
    'high load': '⚡ HIGH LOAD',
  }[normalized] || raw;
  const className = normalized === 'high usage' ? 'high-load' : normalized.replace(/[^a-z0-9]+/g, '-');
  return <span className={`status ${className}`}>{statusText}</span>;
}

function canDo(user, pageKey, action = 'can_view') {
  if (user?.role === 'admin') return true;
  return Boolean(user?.permissions?.[pageKey]?.[action]);
}

function cyberAlertMessage(alert) {
  const message = String(alert?.message || alert || '');
  if (/rdp|media/i.test(message)) return `🚨 Media node overloaded — ${message}`;
  if (/payment|outstanding|billing/i.test(message)) return `💸 Payment pending – follow up before it disappears`;
  return message;
}

function cyberInsightText(item, fallbackClient = 'ROLEX') {
  const text = String(item || '');
  if (/outstanding|cashflow|payment/i.test(text)) return `🧠 Suggestion: improve cashflow from ${fallbackClient}`;
  if (/revenue|billing|growth/i.test(text)) return `⚡ Growth Signal: ${text}`;
  if (/rdp|gateway|risk|drop/i.test(text)) return `🚨 Risk Signal: ${text}`;
  return `🧠 ${text}`;
}

function ledgerQuery(filters = {}, defaultLimit = true) {
  const params = new URLSearchParams();
  if (filters.client_id) params.set('client_id', filters.client_id);
  if (filters.date) {
    params.set('from_date', filters.date);
    params.set('to_date', filters.date);
  }
  if (filters.from_date) params.set('from_date', filters.from_date);
  if (filters.to_date) params.set('to_date', filters.to_date);
  if (filters.date_from) params.set('from_date', filters.date_from);
  if (filters.date_to) params.set('to_date', filters.date_to);
  if (filters.category) params.set('category', filters.category);
  if (filters.charge_type) params.set('category', filters.charge_type);
  if (filters.entry_type) params.set('entry_type', filters.entry_type);
  if (filters.search) params.set('search', filters.search);
  if (filters.created_by) params.set('created_by', filters.created_by);
  params.set('page', String(filters.page || 1));
  params.set('page_size', String(filters.page_size || (defaultLimit ? 50 : 'all')));
  const query = params.toString();
  return query ? `?${query}` : '';
}

function App() {
  const [auth, setAuth] = useState(() => {
    const token = localStorage.getItem('noc360_token');
    const user = localStorage.getItem('noc360_user');
    return token && user ? { token, user: JSON.parse(user) } : null;
  });
  const [active, setActive] = useState(auth?.user?.role === 'customer' ? 'myDashboard' : 'dashboard');
  const [dashboard, setDashboard] = useState(null);
  const [management, setManagement] = useState({ summary: null, cluster: [], rdpCluster: [], routing: [] });
  const [data, setData] = useState({ vos: [], vosDesktop: [], clusters: [], rdps: [], gateways: [], clients: [], users: [] });
  const [billing, setBilling] = useState({ rows: [], summary: null, ledger: [], ledgerPage: { total: 0, page: 1, page_size: 50, total_pages: 1 }, ledgerSummary: null });
  const [settings, setSettings] = useState({ usd_to_inr_rate: 83 });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [profileOpen, setProfileOpen] = useState(false);
  const [toast, setToast] = useState('');

  const refreshBillingData = async (ledgerFilters = {}) => {
    if (!auth) return;
    const canBilling = canDo(auth.user, 'billing') || canDo(auth.user, 'my_ledger');
    if (!canBilling) {
      setBilling({ rows: [], summary: null, ledger: [], ledgerPage: { total: 0, page: 1, page_size: 50, total_pages: 1 }, ledgerSummary: null });
      return null;
    }
    const query = ledgerQuery(ledgerFilters);
    console.log('[NOC360] refreshLedger filters', ledgerFilters, query);
    const [billingRows, billingSummary, ledgerPage, ledgerSummary, billingRate] = await Promise.all([
      request('/billing'),
      request('/billing/summary'),
      request(`/billing/ledger${query}`),
      request('/billing/client-outstanding'),
      request('/settings/billing-rate'),
    ]);
    const items = Array.isArray(ledgerPage) ? ledgerPage : (ledgerPage.items || []);
    const pageMeta = Array.isArray(ledgerPage)
      ? { total: items.length, page: 1, page_size: items.length, total_pages: 1 }
      : { total: ledgerPage.total || 0, page: ledgerPage.page || 1, page_size: ledgerPage.page_size || items.length || 0, total_pages: ledgerPage.total_pages || 1 };
    setBilling({ rows: billingRows, summary: billingSummary, ledger: items, ledgerPage: pageMeta, ledgerSummary });
    setSettings(billingRate);
    return pageMeta;
  };

  const loadAll = async () => {
    if (!auth) return;
    setLoading(true);
    setError('');
    try {
      await refreshBillingData();

      if (auth.user.role !== 'customer') {
        const can = (pageKey) => canDo(auth.user, pageKey);
        const [dash, summary, clusterAssignments, rdpClusterAssignments, routingAssignments, vos, vosDesktop, clusters, rdps, gateways, clients, users] = await Promise.all([
          can('dashboard') ? request('/dashboard') : Promise.resolve(null),
          can('management_portal') ? request('/management/summary') : Promise.resolve(null),
          can('management_portal') ? request('/management/cluster-assignments') : Promise.resolve([]),
          can('management_portal') ? request('/management/rdp-cluster-assignments') : Promise.resolve([]),
          can('management_portal') ? request('/management/routing-media-assignments') : Promise.resolve([]),
          can('vos_portals') || can('management_portal') ? request('/vos-portals') : Promise.resolve([]),
          can('vos_desktop_launcher') ? request('/vos-desktop') : Promise.resolve([]),
          can('dialer_clusters') || can('management_portal') ? request('/dialer-clusters') : Promise.resolve([]),
          can('rdp_media') || can('management_portal') ? request('/rdps') : Promise.resolve([]),
          can('routing_gateways') || can('management_portal') ? request('/routing-gateways') : Promise.resolve([]),
          request('/clients'),
          can('user_access') ? request('/users') : Promise.resolve([]),
        ]);
        setDashboard(dash);
        setManagement({ summary, cluster: clusterAssignments, rdpCluster: rdpClusterAssignments, routing: routingAssignments });
        setData({ vos, vosDesktop, clusters, rdps, gateways, clients, users });
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, [auth]);

  useEffect(() => {
    if (!auth?.token) return undefined;
    let mounted = true;
    request('/auth/me')
      .then((user) => {
        if (!mounted) return;
        localStorage.setItem('noc360_user', JSON.stringify(user));
        setAuth((current) => (current?.token === auth.token ? { ...current, user } : current));
      })
      .catch(() => {});
    return () => {
      mounted = false;
    };
  }, [auth?.token]);

  const showToast = (message) => {
    setToast(message);
    window.setTimeout(() => setToast(''), 2600);
  };

  const updateStoredUser = (user) => {
    localStorage.setItem('noc360_user', JSON.stringify(user));
    setAuth((current) => (current ? { ...current, user } : current));
    setProfileOpen(false);
    showToast('Profile updated');
  };

  const login = async (username, password) => {
    const result = await request('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) });
    localStorage.setItem('noc360_token', result.access_token);
    localStorage.setItem('noc360_user', JSON.stringify(result.user));
    setAuth({ token: result.access_token, user: result.user });
    setActive(result.user.role === 'customer' ? 'myDashboard' : 'dashboard');
    if (window.location.pathname === '/login') window.history.replaceState({}, '', '/');
  };

  const logout = () => {
    localStorage.removeItem('noc360_token');
    localStorage.removeItem('noc360_user');
    setAuth(null);
    setProfileOpen(false);
    setActive('dashboard');
    if (window.location.pathname !== '/login') window.history.pushState({}, '', '/login');
  };

  if (!auth) return <LoginScreen onLogin={login} />;

  const hasPermission = (moduleKey) => {
    if (auth.user.role === 'admin') return true;
    const pageKey = modulePageKeys[moduleKey];
    return !pageKey || auth.user.permissions?.[pageKey]?.can_view;
  };
  const activeModules = auth.user.role === 'customer'
    ? Object.fromEntries(Object.entries(customerModules).filter(([key]) => hasPermission(key)))
    : Object.fromEntries(Object.entries(modules).filter(([key]) => hasPermission(key)));
  const activeKey = activeModules[active] ? active : Object.keys(activeModules)[0];
  const ActiveIcon = activeModules[activeKey]?.icon || Activity;
  const shellStats = [
    ['Sync', loading ? 'Live' : 'Ready'],
    ['Alerts', dashboard?.summary?.alerts ?? management.summary?.duplicate_alerts ?? 0],
    ['RDP', data.rdps?.length ?? 0],
    ['Outstanding', billing.ledgerSummary?.total_outstanding ? usd(billing.ledgerSummary.total_outstanding) : '$0.00'],
  ];

  return (
    <div className={`app ${loading ? 'isSyncing' : ''}`}>
      <div className="sceneGlow" aria-hidden="true">
        <span className="earthCore" />
        <span className="orbitRing orbitOne" />
        <span className="orbitRing orbitTwo" />
        <span className="orbitRing orbitThree" />
        <span className="signalWave waveOne" />
        <span className="signalWave waveTwo" />
        <span className="packetNode nodeOne" />
        <span className="packetNode nodeTwo" />
        <span className="packetNode nodeThree" />
        <span className="callRoute routeOne" />
        <span className="callRoute routeTwo" />
      </div>
      <aside className="sidebar">
        <div className="brand">
          <Server size={30} />
          <div>
            <strong>NOC360</strong>
            <span>Global VoIP Grid</span>
          </div>
        </div>
        <nav>
          {Object.entries(activeModules).map(([key, item], index) => {
            const Icon = item.icon;
            return (
              <button key={key} className={activeKey === key ? 'active' : ''} onClick={() => setActive(key)} style={{ '--nav-index': index }}>
                <Icon size={18} />
                <span>{item.label}</span>
                <i className="navPulse" />
              </button>
            );
          })}
        </nav>
      </aside>

      <main>
        <header className="topbar">
          <div>
            <span className="eyebrow">NOC360 – Global VoIP Command Grid</span>
            <h1><ActiveIcon size={28} /> {activeModules[activeKey]?.label || 'No Access'}</h1>
          </div>
          <div className="hudGrid">
            {shellStats.map(([label, value]) => <div className="hudCell" key={label}><span>{label}</span><strong>{value}</strong></div>)}
          </div>
          <div className="topActions">
            <button className="rolePill accountTrigger" onClick={() => setProfileOpen(true)} title="Account Settings">{auth.user.username || auth.user.role}</button>
            <button className="refreshButton" onClick={loadAll} title="Refresh live master data"><RefreshCcw size={18} /> Refresh Data</button>
            <button className="iconButton" onClick={logout} title="Logout"><LogOut size={18} /></button>
          </div>
        </header>

        {toast && <div className="toastSuccess appToast">{toast}</div>}
        {error && <div className="error"><AlertTriangle size={18} /> {error}</div>}
        {loading && <div className="loading">Syncing NOC inventory...</div>}

        <section className="pageShell" key={activeKey || 'no-access'}>
          {auth.user.role === 'customer' && activeKey === 'myDashboard' ? (
            <CustomerDashboard billing={billing} user={auth.user} />
          ) : auth.user.role === 'customer' && activeKey === 'myBilling' ? (
            <BillingPage billing={billing} data={data} reload={loadAll} refreshBilling={refreshBillingData} user={auth.user} settings={settings} />
          ) : auth.user.role === 'customer' && activeKey === 'myCdr' ? (
            <CustomerCdrPage user={auth.user} />
          ) : auth.user.role === 'customer' && activeKey === 'myReports' ? (
            <ReportsPage data={data} user={auth.user} />
          ) : activeKey === 'dashboard' ? (
            <Dashboard dashboard={dashboard} data={data} setActive={setActive} />
          ) : activeKey === 'management' ? (
          <ManagementPortal management={management} data={data} reload={loadAll} user={auth.user} />
          ) : activeKey === 'businessAi' ? (
            <BusinessAIPage data={data} />
          ) : activeKey === 'reports' ? (
            <ReportsPage data={data} user={auth.user} />
          ) : activeKey === 'vosDesktop' ? (
            <VOSDesktopPage rows={data.vosDesktop} user={auth.user} reload={loadAll} />
          ) : activeKey === 'billing' ? (
            <BillingPage billing={billing} data={data} reload={loadAll} refreshBilling={refreshBillingData} user={auth.user} settings={settings} />
          ) : activeKey === 'clients' ? (
          <ClientsPage clients={data.clients} reload={loadAll} user={auth.user} />
          ) : activeKey === 'userAccess' ? (
          <UserAccessPage users={data.users} clients={data.clients} reload={loadAll} user={auth.user} />
          ) : activeKey ? (
            <CrudPage
              moduleKey={activeKey}
              config={modules[activeKey]}
              rows={data[activeKey]}
              rdps={data.rdps}
            clients={data.clients}
            rtngs={data.vos.filter((portal) => portal.portal_type?.toUpperCase().startsWith('RTNG'))}
            reload={loadAll}
            user={auth.user}
          />
          ) : (
            <div className="panel"><h2>No page access</h2><p className="muted">Ask an admin to assign page permissions.</p></div>
          )}
        </section>
      </main>
      {profileOpen && <AccountSettingsModal user={auth.user} onClose={() => setProfileOpen(false)} onUpdated={updateStoredUser} onLogout={logout} />}
    </div>
  );
}

function LoginScreen({ onLogin }) {
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('admin123');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError('');
    try {
      await onLogin(username, password);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <div className="loginPage">
      <form className="loginBox" onSubmit={submit}>
        <div className="brand loginBrand"><Server size={32} /><div><strong>NOC360</strong><span>Customer Billing Portal</span></div></div>
        {error && <div className="error">{error}</div>}
        <label><span>Username</span><input value={username} onChange={(event) => setUsername(event.target.value)} /></label>
        <label><span>Password</span><input type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>
        <button className="primary">{loading ? 'Signing in...' : 'Login'}</button>
        <p className="muted">Customer samples: im1 / 123, im2 / 123, rolex / 123</p>
      </form>
    </div>
  );
}

function AccountSettingsModal({ user, onClose, onUpdated, onLogout }) {
  const [email, setEmail] = useState(user?.email || '');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setEmail(user?.email || '');
  }, [user?.email]);

  const save = async (event) => {
    event.preventDefault();
    setError('');
    if (!currentPassword) {
      setError('Current password is required.');
      return;
    }
    if (newPassword || confirmPassword) {
      if (newPassword.length < 6) {
        setError('New password must be at least 6 characters.');
        return;
      }
      if (newPassword !== confirmPassword) {
        setError('New password and confirm password must match.');
        return;
      }
    }
    setSaving(true);
    try {
      const updatedUser = await request('/auth/update-profile', {
        method: 'PUT',
        body: JSON.stringify({
          email,
          current_password: currentPassword,
          new_password: newPassword || null,
        }),
      });
      onUpdated(updatedUser);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modalBackdrop modal-overlay">
      <form className="modal modal-box accountModal" onSubmit={save}>
        <div className="modalHeader accountHero">
          <div>
            <span className="eyebrow">Secure operator profile</span>
            <h2>Account Settings</h2>
          </div>
          <button type="button" className="iconButton" onClick={onClose} title="Close"><X size={18} /></button>
        </div>
        {error && <div className="error"><AlertTriangle size={18} /> {error}</div>}
        <div className="formGrid accountForm">
          <label>
            <span>Username</span>
            <input value={user?.username || ''} readOnly />
          </label>
          <label>
            <span>Email</span>
            <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="user@example.com" />
          </label>
          <label className="wide">
            <span>Current Password</span>
            <input type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} autoComplete="current-password" />
          </label>
          <label>
            <span>New Password</span>
            <input type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} autoComplete="new-password" />
          </label>
          <label>
            <span>Confirm Password</span>
            <input type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} autoComplete="new-password" />
          </label>
        </div>
        <div className="modalActions accountActions">
          <button type="button" onClick={onLogout}><LogOut size={16} /> Logout</button>
          <button className="primary" disabled={saving}>{saving ? 'Saving...' : 'Save Changes'}</button>
        </div>
      </form>
    </div>
  );
}

function loadLauncherSettings() {
  const defaults = {
    launcherPath: 'D:\\NOC360\\Launcher\\vos_launcher.bat',
    v1Name: 'VOS v1',
    v1Path: 'C:\\Users\\ASUS\\Desktop\\VOS Shortcuts\\VOS3000-v1.lnk',
    v2Name: 'VOS v2',
    v2Path: 'C:\\Users\\ASUS\\Desktop\\VOS Shortcuts\\VOS3000-v2.lnk',
    customPath: '',
  };
  try {
    const saved = JSON.parse(localStorage.getItem('vos_launcher_paths') || '{}');
    const savedKeys = Object.keys(saved).filter((key) => !['Custom', '__launcher_path'].includes(key));
    const v1Name = savedKeys[0] || defaults.v1Name;
    const v2Name = savedKeys[1] || defaults.v2Name;
    return {
      launcherPath: saved.__launcher_path || localStorage.getItem('vos_launcher_path') || defaults.launcherPath,
      v1Name,
      v1Path: saved[v1Name] ?? defaults.v1Path,
      v2Name,
      v2Path: saved[v2Name] ?? defaults.v2Path,
      customPath: saved.Custom ?? defaults.customPath,
    };
  } catch {
    return defaults;
  }
}

function VOSDesktopEditModal({ record, onClose, onSave }) {
  const [form, setForm] = useState({
    ...record,
    password: '',
    anti_hack_password: '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const setField = (key, value) => setForm((current) => ({ ...current, [key]: value }));
  const submit = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    try {
      await onSave(form);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };
  return (
    <div className="modalBackdrop modal-overlay">
      <form className="modal modal-box accountModal" onSubmit={submit}>
        <div className="modalHeader accountHero">
          <div><span className="eyebrow">VOS Desktop Master Link</span><h2>Edit {record.vos_name}</h2></div>
          <button type="button" className="iconButton" onClick={onClose}><X size={18} /></button>
        </div>
        {error && <div className="error"><AlertTriangle size={18} /> {error}</div>}
        <div className="formGrid">
          <label><span>Server IP</span><input value={form.server_ip || ''} onChange={(event) => setField('server_ip', event.target.value)} /></label>
          <label><span>Status</span><select value={form.status || 'Active'} onChange={(event) => setField('status', event.target.value)}>{statuses.map((status) => <option key={status}>{status}</option>)}</select></label>
          <label><span>Username</span><input value={form.username || ''} onChange={(event) => setField('username', event.target.value)} /></label>
          <label><span>Password</span><input type="password" value={form.password || ''} onChange={(event) => setField('password', event.target.value)} placeholder="Leave blank to keep current password" /></label>
          <label className="wide"><span>Anti-Hack URL</span><input value={form.anti_hack_url || ''} onChange={(event) => setField('anti_hack_url', event.target.value)} /></label>
          <label><span>Anti-Hack Password</span><input type="password" value={form.anti_hack_password || ''} onChange={(event) => setField('anti_hack_password', event.target.value)} placeholder="Leave blank to keep current password" /></label>
          <label><span>VOS Port</span><input type="number" value={form.vos_port || ''} onChange={(event) => setField('vos_port', event.target.value)} /></label>
          <label className="wide"><span>Web Panel URL</span><input value={form.web_panel_url || ''} onChange={(event) => setField('web_panel_url', event.target.value)} /></label>
          <label><span>Desktop Enabled</span><input type="checkbox" checked={Boolean(form.vos_desktop_enabled)} onChange={(event) => setField('vos_desktop_enabled', event.target.checked)} /></label>
          <label className="wide"><span>VOS Notes</span><textarea value={form.vos_notes || ''} onChange={(event) => setField('vos_notes', event.target.value)} /></label>
        </div>
        <div className="modalActions">
          <button type="button" onClick={onClose}>Cancel</button>
          <button className="primary" disabled={saving}>{saving ? 'Saving...' : 'Save'}</button>
        </div>
      </form>
    </div>
  );
}

function VOSDesktopPage({ rows, user, reload }) {
  const canUseLauncher = canDo(user, 'vos_desktop_launcher', 'can_export') || user?.role === 'admin';
  const canEdit = canDo(user, 'vos_desktop_launcher', 'can_edit') || user?.role === 'admin';
  const [query, setQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('All');
  const [launcherSettings, setLauncherSettings] = useState(() => loadLauncherSettings());
  const [selectedVersions, setSelectedVersions] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('vos_launcher_selected_versions') || '{}');
    } catch {
      return {};
    }
  });
  const [favorites, setFavorites] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('vos_desktop_favorites') || '[]');
    } catch {
      return [];
    }
  });
  const [lastUsed, setLastUsed] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('vos_desktop_last_used') || '{}');
    } catch {
      return {};
    }
  });
  const [revealed, setRevealed] = useState({});
  const [editing, setEditing] = useState(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const launcherNames = [launcherSettings.v1Name || 'VOS v1', launcherSettings.v2Name || 'VOS v2', 'Custom'];
  const launcherPaths = {
    __launcher_path: launcherSettings.launcherPath || 'D:\\NOC360\\Launcher\\vos_launcher.bat',
    [launcherNames[0]]: launcherSettings.v1Path || '',
    [launcherNames[1]]: launcherSettings.v2Path || '',
    Custom: launcherSettings.customPath || '',
  };
  const favoriteSet = useMemo(() => new Set(favorites), [favorites]);
  const filtered = useMemo(() => {
    const needle = query.toLowerCase();
    return [...rows]
      .sort((a, b) => Number(favoriteSet.has(b.id)) - Number(favoriteSet.has(a.id)) || a.vos_name.localeCompare(b.vos_name))
      .filter((row) => typeFilter === 'All' || row.vos_type === typeFilter)
      .filter((row) => [row.vos_name, row.server_ip, row.status, row.username, row.vos_type, row.vos_notes].join(' ').toLowerCase().includes(needle));
  }, [rows, query, typeFilter, favoriteSet]);
  const groupedRows = useMemo(() => ([
    ['RDP', 'Media Servers / RDP'],
    ['RTNG', 'Routing Servers / RTNG'],
    ['DID', 'DID Portals'],
    ['Other', 'Other VOS'],
  ]).map(([type, title]) => [type, title, filtered.filter((row) => row.vos_type === type)]).filter(([, , groupRows]) => groupRows.length), [filtered]);

  const saveLauncherPaths = () => {
    localStorage.setItem('vos_launcher_paths', JSON.stringify(launcherPaths));
    localStorage.setItem('vos_launcher_path', launcherPaths.__launcher_path);
    setMessage('Permanent launcher paths saved');
    setError('');
  };

  const selectedVersionFor = (row) => (launcherNames.includes(selectedVersions[row.id]) ? selectedVersions[row.id] : launcherNames[0]);
  const selectedPathFor = (row) => launcherPaths[selectedVersionFor(row)] || '';
  const permanentLauncherPath = () => launcherPaths.__launcher_path || '';

  const setSelectedVersion = (row, version) => {
    const next = { ...selectedVersions, [row.id]: version };
    setSelectedVersions(next);
    localStorage.setItem('vos_launcher_selected_versions', JSON.stringify(next));
  };

  const toggleFavorite = (row) => {
    const next = favoriteSet.has(row.id) ? favorites.filter((id) => id !== row.id) : [...favorites, row.id];
    setFavorites(next);
    localStorage.setItem('vos_desktop_favorites', JSON.stringify(next));
  };

  const markLastUsed = (row) => {
    const next = { ...lastUsed, [row.id]: new Date().toISOString() };
    setLastUsed(next);
    localStorage.setItem('vos_desktop_last_used', JSON.stringify(next));
    request(`/vos-desktop/${row.id}/last-used`, { method: 'POST', body: JSON.stringify({}) }).catch(() => {});
  };

  const fetchLogin = async (row) => request(`/vos-desktop/${row.id}/login`);

  const copyText = async (text) => {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return;
    }
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);
  };

  const fileUrlForWindowsPath = (path) => {
    if (!path) return '';
    return `file:///${path.replaceAll('\\', '/')}`;
  };

  const copyLogin = async (row) => {
    if (!canUseLauncher) return;
    try {
      const login = await fetchLogin(row);
      await copyText([
        `VOS: ${row.vos_name || ''}`,
        `Server: ${login.server || ''}`,
        `Username: ${login.username || ''}`,
        `Password: ${login.password || ''}`,
        `Anti-Hack URL: ${login.anti_hack_url || row.anti_hack_url || ''}`,
        `Anti-Hack Pass: ${login.anti_hack_password || ''}`,
      ].join('\n'));
      setMessage('Login details copied.');
      setError('');
    } catch (err) {
      setError(err.message);
    }
  };

  const toggleReveal = async (row) => {
    if (revealed[row.id]) {
      setRevealed((current) => ({ ...current, [row.id]: null }));
      return;
    }
    try {
      const login = await fetchLogin(row);
      setRevealed((current) => ({ ...current, [row.id]: login }));
      setError('');
    } catch (err) {
      setError(err.message);
    }
  };

  const launchDesktop = async (row) => {
    if (!canUseLauncher) return;
    const launcherPath = permanentLauncherPath();
    const shortcutPath = selectedPathFor(row);
    if (!launcherPath.trim()) {
      setError('Launcher not configured. Please create vos_launcher.bat in D:\\NOC360\\Launcher');
      return;
    }
    if (!shortcutPath.trim()) {
      setError('Please set local VOS shortcut/app path first.');
      return;
    }
    try {
      const token = localStorage.getItem('noc360_token');
      const response = await fetch(`${API_BASE_URL}/vos-desktop/${row.id}/launch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ launcher_path: launcherPath, shortcut_path: shortcutPath }),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail.detail || 'Launcher command failed');
      }
      const launchInfo = await response.json();
      await copyText(launchInfo.command);
      window.open(fileUrlForWindowsPath(launchInfo.launcher_path), '_blank', 'noopener,noreferrer');
      markLastUsed(row);
      setMessage(`Permanent launcher command copied for ${row.vos_name}. If the browser blocks local launch, run the copied command.`);
      setError('');
    } catch (err) {
      setError(err.message);
    }
  };

  const openWhitelist = (row) => {
    const url = row.anti_hack_url || (row.server_ip ? `http://${row.server_ip}:8989/anti-atck` : '');
    if (!url) {
      setError('Anti-hack URL is missing');
      return;
    }
    window.open(url, '_blank', 'noopener,noreferrer');
    fetchLogin(row)
      .then((login) => (login.anti_hack_password ? copyText(login.anti_hack_password) : null))
      .then(() => {
        setMessage('Anti-hack page opened. Password copied.');
        setError('');
      })
      .catch(() => setMessage('Anti-hack page opened.'));
  };

  const openWebPanel = (row) => {
    window.open(row.web_panel_url || `http://${row.server_ip}`, '_blank', 'noopener,noreferrer');
  };

  const lastUsedText = (row) => {
    if (!lastUsed[row.id]) return 'Never';
    return new Date(lastUsed[row.id]).toLocaleString();
  };

  const saveEdit = async (form) => {
    const payload = {
      server_ip: form.server_ip || null,
      status: form.status || 'Active',
      username: form.username || null,
      anti_hack_url: form.anti_hack_url || null,
      web_panel_url: form.web_panel_url || null,
      vos_port: form.vos_port ? Number(form.vos_port) : null,
      vos_desktop_enabled: Boolean(form.vos_desktop_enabled),
      vos_notes: form.vos_notes || null,
    };
    if (form.password) payload.password = form.password;
    if (form.anti_hack_password) payload.anti_hack_password = form.anti_hack_password;
    await request(`/vos-desktop/${form.id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
    setEditing(null);
    setMessage('VOS launcher record updated');
    await reload();
  };

  return (
    <section className="vosDesktopPage">
      <div className="panel vosDesktopHero">
        <div>
          <span className="eyebrow">VOS Desktop Launcher</span>
          <h2><Play size={20} /> Local shortcut launch from VOS Portal Master</h2>
          <p className="muted">RDP, RTNG, DID, and every other VOS portal use one trusted permanent launcher. No repeated downloads, no temp scripts.</p>
        </div>
        <div className="launcherStats">
          <span>{rows.length} VOS records</span>
          <span>{favorites.length} favorites</span>
          <span>{Object.keys(lastUsed).length} launched</span>
        </div>
      </div>

      <div className="panel launcherSettingsPanel">
        <div>
          <span className="eyebrow">Local VOS Launcher Paths</span>
          <h2>Shortcut/App Paths</h2>
        </div>
        <label className="wideLauncherField"><span>Launcher Path</span><input value={launcherSettings.launcherPath} onChange={(event) => setLauncherSettings({ ...launcherSettings, launcherPath: event.target.value })} placeholder="D:\NOC360\Launcher\vos_launcher.bat" /></label>
        <label><span>VOS Version 1 Name</span><input value={launcherSettings.v1Name} onChange={(event) => setLauncherSettings({ ...launcherSettings, v1Name: event.target.value })} placeholder="VOS v1" /></label>
        <label className="wideLauncherField"><span>VOS Version 1 Path</span><input value={launcherSettings.v1Path} onChange={(event) => setLauncherSettings({ ...launcherSettings, v1Path: event.target.value })} placeholder="C:\Users\ASUS\Desktop\VOS Shortcuts\VOS3000-v1.lnk" /></label>
        <label><span>VOS Version 2 Name</span><input value={launcherSettings.v2Name} onChange={(event) => setLauncherSettings({ ...launcherSettings, v2Name: event.target.value })} placeholder="VOS v2" /></label>
        <label className="wideLauncherField"><span>VOS Version 2 Path</span><input value={launcherSettings.v2Path} onChange={(event) => setLauncherSettings({ ...launcherSettings, v2Path: event.target.value })} placeholder="C:\Users\ASUS\Desktop\VOS Shortcuts\VOS3000-v2.lnk" /></label>
        <label className="wideLauncherField"><span>Custom Path</span><input value={launcherSettings.customPath} onChange={(event) => setLauncherSettings({ ...launcherSettings, customPath: event.target.value })} placeholder="C:\Program Files\VOS3000\VOS3000.exe" /></label>
        <button className="primary" onClick={saveLauncherPaths}>Save Launcher Paths</button>
      </div>

      {message && <div className="toastSuccess">{message}</div>}
      {error && <div className="error"><AlertTriangle size={18} /> {error}</div>}

      <div className="toolbar">
        <div className="search">
          <Search size={18} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search VOS desktop records..." />
        </div>
        <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}>
          <option>All</option>
          <option>RDP</option>
          <option>RTNG</option>
          <option>DID</option>
          <option>Other</option>
        </select>
      </div>

      {groupedRows.map(([type, title, groupRows]) => (
        <div className="managementSection vosGroup" key={type}>
          <h2>{title}</h2>
          <div className="tableWrap vosDesktopTable">
            <table>
              <thead>
                <tr><th>Favorite</th><th>VOS Name / Portal Type</th><th>Server IP</th><th>VOS Type</th><th>Status</th><th>Last Used</th><th>Launcher Version</th><th>Actions</th></tr>
              </thead>
              <tbody>
                {groupRows.map((row) => (
                  <React.Fragment key={row.id}>
                    <tr>
                      <td><button className={`iconButton favoriteButton ${favoriteSet.has(row.id) ? 'isFavorite' : ''}`} onClick={() => toggleFavorite(row)} title="Favorite"><Star size={16} /></button></td>
                      <td><strong>{row.vos_name}</strong>{row.vos_notes && <small>{row.vos_notes}</small>}</td>
                      <td>{row.server_ip || <span className="missing">Missing</span>}</td>
                      <td><span className="typeBadge">{row.vos_type}</span></td>
                      <td><StatusPill value={row.status} /></td>
                      <td>{lastUsedText(row)}</td>
                      <td>
                        <select value={selectedVersionFor(row)} onChange={(event) => setSelectedVersion(row, event.target.value)}>
                          {launcherNames.map((name) => <option key={name}>{name}</option>)}
                        </select>
                        <small className={selectedPathFor(row) ? 'muted' : 'missing'}>{selectedPathFor(row) || 'Path not set'}</small>
                      </td>
                      <td className="actions vosActions">
                        {canUseLauncher && <button className="primary" onClick={() => launchDesktop(row)}><Play size={15} /> Launch Desktop Client</button>}
                        <button onClick={() => openWhitelist(row)}>Whitelist IP</button>
                        {canUseLauncher && <button onClick={() => copyLogin(row)}><Copy size={15} /> Copy Login</button>}
                        <button onClick={() => openWebPanel(row)}><ExternalLink size={15} /> Open Web Panel</button>
                        {canUseLauncher && <button onClick={() => toggleReveal(row)}>{revealed[row.id] ? <EyeOff size={15} /> : <Eye size={15} />} {revealed[row.id] ? 'Hide Password' : 'Show Password'}</button>}
                        {canEdit && <button className="iconButton" onClick={() => setEditing(row)} title="Edit"><Edit3 size={16} /></button>}
                      </td>
                    </tr>
                    {revealed[row.id] && (
                      <tr className="credentialRow">
                        <td colSpan="8">
                          <span>Server: <b>{revealed[row.id].server || '-'}</b></span>
                          <span>Username: <b>{revealed[row.id].username || '-'}</b></span>
                          <span>Password: <b>{revealed[row.id].password || '-'}</b></span>
                          <span>Anti-Hack Pass: <b>{revealed[row.id].anti_hack_password || '-'}</b></span>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
      {!groupedRows.length && <div className="panel muted">No VOS desktop records found.</div>}
      {editing && <VOSDesktopEditModal record={editing} onClose={() => setEditing(null)} onSave={saveEdit} />}
    </section>
  );
}

function ManagementPortal({ management, data, reload, user }) {
  const rtngs = data.vos.filter((portal) => portal.portal_type?.toUpperCase().startsWith('RTNG'));
  const [saving, setSaving] = useState('');
  const canEdit = canDo(user, 'management_portal', 'can_edit');

  const saveManagement = async (key, path, body) => {
    setSaving(key);
    try {
      await request(path, { method: 'PUT', body: JSON.stringify(body) });
      await reload();
    } finally {
      setSaving('');
    }
  };

  const cards = [
    ['Total Clients', management.summary?.total_clients ?? 0],
    ['Active Clients', management.summary?.active_clients ?? 0],
    ['Total Clusters', management.summary?.total_clusters ?? 0],
    ['Assigned Clusters', management.summary?.assigned_clusters ?? 0],
    ['Free RDP', management.summary?.free_rdp ?? 0],
    ['Used RDP', management.summary?.used_rdp ?? 0],
    ['Routing Gateways Configured', management.summary?.routing_gateways_configured ?? 0],
    ['Duplicate Alerts', management.summary?.duplicate_alerts ?? 0],
  ];

  return (
    <section className="management">
      <div className="cards managementCards">
        {cards.map(([label, value]) => (
          <div className={`metric ${label.includes('Duplicate') && value ? 'metricAlert' : ''}`} key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>

      <div className="clientBreakdown">
        <Breakdown title="RDP Used Per Client" data={management.summary?.rdp_used_per_client || {}} />
        <Breakdown title="Clusters Per Client" data={management.summary?.clusters_per_client || {}} />
      </div>

      <ManagementSection title="Cluster Client Assignment">
        <table>
          <thead>
            <tr><th>Cluster</th><th>Client</th><th>Inbound IP</th><th>Status</th><th>Actions</th></tr>
          </thead>
          <tbody>
            {management.cluster.map((row) => (
              <ClusterAccountRow key={row.cluster_id} row={row} clients={data.clients} saving={saving} onSave={saveManagement} canEdit={canEdit} />
            ))}
          </tbody>
        </table>
      </ManagementSection>

      <ManagementSection title="RDP to Cluster Assignment">
        <table>
          <thead>
            <tr><th>Cluster</th><th>Client</th><th>Selected RDP</th><th>RDP IP</th><th>Status</th><th>Duplicate Alert</th><th>Actions</th></tr>
          </thead>
          <tbody>
            {management.rdpCluster.map((row) => (
              <RdpClusterRow key={row.cluster_id} row={row} rdps={data.rdps} saving={saving} onSave={saveManagement} canEdit={canEdit} />
            ))}
          </tbody>
        </table>
      </ManagementSection>

      <ManagementSection title="Routing Gateway Media Mapping">
        <table>
          <thead>
            <tr><th>Routing Gateway</th><th>Gateway IP</th><th>Client</th><th>Media 1</th><th>Media 1 IP</th><th>Media 2</th><th>Media 2 IP</th><th>Carrier IP</th><th>Ports</th><th>Vendor</th><th>Status</th><th>Actions</th></tr>
          </thead>
          <tbody>
            {management.routing.map((row) => (
              <RoutingMediaRow key={row.gateway_name} row={row} rdps={data.rdps} rtngs={rtngs} saving={saving} onSave={saveManagement} canEdit={canEdit} />
            ))}
          </tbody>
        </table>
      </ManagementSection>
    </section>
  );
}

function makeQuery(filters) {
  const params = new URLSearchParams();
  if (filters.date_from) params.set('date_from', filters.date_from);
  if (filters.date_to) params.set('date_to', filters.date_to);
  if (filters.client_ids?.length) params.set('client_ids', filters.client_ids.join(','));
  if (filters.charge_type) params.set('charge_type', filters.charge_type);
  return params.toString() ? `?${params}` : '';
}

function MultiSelect({ values, options, labelKey = 'name', onChange }) {
  return (
    <select multiple value={values} onChange={(event) => onChange(Array.from(event.target.selectedOptions).map((option) => option.value))}>
      {options.map((option) => <option key={option.id} value={option.id}>{option[labelKey]}</option>)}
    </select>
  );
}

function reportValue(header, value) {
  if (typeof value !== 'number') return String(value ?? '-');
  const key = header.toLowerCase();
  if (key.includes('inr') || key.includes('₹')) return inr(value);
  if (key.includes('usd') || key.includes('$')) return usd(value);
  return Number(value).toFixed(2);
}

function ReportsPage({ data, user }) {
  const isCustomer = user?.role === 'customer';
  const reportsPageKey = isCustomer ? 'my_reports' : 'reports';
  const canCreate = canDo(user, reportsPageKey, 'can_create');
  const canExport = canDo(user, reportsPageKey, 'can_export');
  const [filters, setFilters] = useState({ date_from: '', date_to: '', client_ids: [], cluster_ids: [], charge_type: '' });
  const [reportType, setReportType] = useState('ledger');
  const [rows, setRows] = useState([]);
  const [costForm, setCostForm] = useState({ client_id: '', entry_date: new Date().toISOString().slice(0, 10), quantity: '', rate: '', description: '' });
  const reports = [
    ['ledger', 'Client Ledger Report', '/reports/ledger'],
    ['daily-billing', 'Daily Billing Report', '/reports/daily-billing'],
    ['data-cost', 'Data Cost Report', '/reports/data-cost'],
    ['outstanding', 'Client-wise Outstanding Report', '/reports/outstanding'],
    ['cluster-usage', 'Cluster Usage Report', '/reports/cluster-usage'],
    ['rdp-utilization', 'RDP Utilization Report', '/reports/rdp-utilization'],
    ['routing-capacity', 'Routing Gateway Capacity Report', '/reports/routing-capacity'],
  ];
  const load = async (type = reportType) => {
    const item = reports.find(([key]) => key === type);
    setRows(await request(`${item[2]}${makeQuery(filters)}`));
  };
  useEffect(() => { load(); }, [reportType]);
  const addDataCost = async (event) => {
    event.preventDefault();
    await request('/reports/data-cost', { method: 'POST', body: JSON.stringify({ ...costForm, client_id: Number(costForm.client_id), quantity: Number(costForm.quantity), rate: Number(costForm.rate) }) });
    await load('data-cost');
  };
  const headers = rows[0] ? Object.keys(rows[0]) : [];
  return (
    <section>
      <div className="reportFilters">
        <input type="date" value={filters.date_from} onChange={(e) => setFilters({ ...filters, date_from: e.target.value })} />
        <input type="date" value={filters.date_to} onChange={(e) => setFilters({ ...filters, date_to: e.target.value })} />
        {!isCustomer && <MultiSelect values={filters.client_ids} options={data.clients} onChange={(value) => setFilters({ ...filters, client_ids: value })} />}
        {!isCustomer && <MultiSelect values={filters.cluster_ids} options={data.clusters} labelKey="cluster_name" onChange={(value) => setFilters({ ...filters, cluster_ids: value })} />}
        <select value={filters.charge_type} onChange={(e) => setFilters({ ...filters, charge_type: e.target.value })}><option value="">All charge types</option>{ledgerCategories.map((type) => <option key={type}>{type}</option>)}</select>
        <select value={reportType} onChange={(e) => setReportType(e.target.value)}>{reports.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select>
        <button onClick={() => load()}><RefreshCcw size={16} /> Run</button>
        {canExport && <button onClick={() => exportRows(`${reportType}.csv`, rows)}><Download size={16} /> Export CSV</button>}
      </div>
      {reportType === 'data-cost' && !isCustomer && canCreate && (
        <form className="inlineForm" onSubmit={addDataCost}>
          <ClientSelect value={costForm.client_id} clients={data.clients} onChange={(value) => setCostForm({ ...costForm, client_id: value })} />
          <input type="date" value={costForm.entry_date} onChange={(e) => setCostForm({ ...costForm, entry_date: e.target.value })} />
          <input type="number" step="0.01" placeholder="Quantity" value={costForm.quantity} onChange={(e) => setCostForm({ ...costForm, quantity: e.target.value })} />
          <input type="number" step="0.0001" placeholder="Rate" value={costForm.rate} onChange={(e) => setCostForm({ ...costForm, rate: e.target.value })} />
          <input placeholder="Description" value={costForm.description} onChange={(e) => setCostForm({ ...costForm, description: e.target.value })} />
          <button className="primary">Add Data Cost</button>
        </form>
      )}
      <div className="tableWrap"><table><thead><tr>{headers.map((header) => <th key={header}>{header.replaceAll('_', ' ')}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={index}>{headers.map((header) => <td key={header}>{reportValue(header, row[header])}</td>)}</tr>)}</tbody></table></div>
    </section>
  );
}

function BusinessAIPage({ data }) {
  const [filters, setFilters] = useState({ date_from: '', date_to: '', client_ids: [], charge_type: '' });
  const [summary, setSummary] = useState(null);
  const [insights, setInsights] = useState([]);
  const [selectedChart, setSelectedChart] = useState('billing_trend_by_day');
  const chartOptions = [
    ['billing_trend_by_day', 'Billing Trend by Day'],
    ['payment_trend_by_day', 'Payment Trend by Day'],
    ['outstanding_by_client', 'Outstanding by Client'],
    ['client_billing_ranking', 'Client Billing Ranking'],
    ['charge_type_breakdown', 'Charge Type Breakdown'],
    ['client_growth_trend', 'Client Growth Trend'],
  ];
  const load = async () => {
    const qs = makeQuery(filters);
    const [summaryData, insightData] = await Promise.all([request(`/business-ai/summary${qs}`), request(`/business-ai/insights${qs}`)]);
    setSummary(summaryData);
    setInsights(insightData.insights || []);
  };
  useEffect(() => { load(); }, []);
  const cards = summary?.cards || {};
  const chartRows = summary?.charts?.[selectedChart] || [];
  const highestOutstanding = cards.highest_outstanding_client || 'ROLEX';
  const insightGroups = [
    ['Growth Signal', insights.filter((item) => /billing|revenue|growth|top/i.test(item)).slice(0, 3)],
    ['Risk Signal', insights.filter((item) => /drop|risk|rdp|gateway|outstanding/i.test(item)).slice(0, 3)],
    ['Cashflow Signal', insights.filter((item) => /payment|cashflow|outstanding/i.test(item)).slice(0, 3)],
  ].map(([label, rows]) => [label, rows.length ? rows : [`Suggestion: improve cashflow from ${highestOutstanding}`]]);
  return (
    <section className="businessAi">
      <div className="reportFilters">
        <input type="date" value={filters.date_from} onChange={(e) => setFilters({ ...filters, date_from: e.target.value })} />
        <input type="date" value={filters.date_to} onChange={(e) => setFilters({ ...filters, date_to: e.target.value })} />
        <MultiSelect values={filters.client_ids} options={data.clients} onChange={(value) => setFilters({ ...filters, client_ids: value })} />
        <select value={filters.charge_type} onChange={(e) => setFilters({ ...filters, charge_type: e.target.value })}><option value="">All charge types</option>{chargeTypes.map((type) => <option key={type}>{type}</option>)}</select>
        <select value={selectedChart} onChange={(e) => setSelectedChart(e.target.value)}>{chartOptions.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select>
        <button onClick={load}><RefreshCcw size={16} /> Analyze</button>
      </div>
      <div className="aiHero">
        <div>
          <span className="eyebrow">Business AI Insights</span>
          <h2>Client Billing Intelligence</h2>
        </div>
        <div className="signalStrip"><span>Billing Signal</span><span>Payment Signal</span><span>Cashflow Signal</span></div>
      </div>
      <div className="cards aiCards">
        {[
          ['Total Billing', cards.total_billing, cards.total_billing_inr, 'revenue'],
          ['Total Payments', cards.total_payments, cards.total_payments_inr, 'payment'],
          ['Total Outstanding', cards.total_outstanding, cards.total_outstanding_inr, 'outstanding'],
          ['Today Billing', cards.today_billing, cards.today_billing_inr, 'revenue'],
          ['Monthly Billing', cards.monthly_billing, cards.monthly_billing_inr, 'revenue'],
          ['Active Clients', cards.active_clients],
          ['Top Billing Client', cards.top_billing_client],
          ['Highest Outstanding Client', cards.highest_outstanding_client],
        ].map(([label, value, inrValue, tone]) => <div className={`metric aiMetric ${tone || ''} ${label.includes('Outstanding') ? 'metricAlert' : ''}`} key={label}><span>{label}</span><strong>{typeof value === 'number' ? (inrValue !== undefined ? dualMoney(value, inrValue) : money(value)) : value || '-'}</strong></div>)}
      </div>
      <div className="aiGrid">
        <div className="panel">
          <h2>{chartOptions.find(([key]) => key === selectedChart)?.[1] || 'Billing Trend'}</h2>
          <BusinessAiChart selectedChart={selectedChart} rows={chartRows} filters={filters} setFilters={setFilters} />
        </div>
        <div className="panel insightPanel">
          <h2>Business AI Insights</h2>
          {insightGroups.map(([label, rows]) => (
            <div className="signalPanel" key={label}>
              <h3>{label}</h3>
              {rows.map((item, index) => <div className="insightBox" key={`${label}-${index}`}><AlertTriangle size={17} />{cyberInsightText(item, highestOutstanding)}</div>)}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function BusinessAiChart({ selectedChart, rows, filters, setFilters }) {
  if (selectedChart === 'outstanding_by_client') {
    return (
      <div className="tableWrap aiTable"><table><thead><tr><th>Client</th><th>Outstanding USD</th><th>Outstanding INR</th></tr></thead><tbody>{rows.map((row) => (
        <tr key={row.client}><td>{row.client}</td><td className={row.outstanding > 0 ? 'outstandingText' : ''}>{usd(row.outstanding)}</td><td className={row.outstanding_inr > 0 ? 'outstandingText' : ''}>{inr(row.outstanding_inr)}</td></tr>
      ))}</tbody></table></div>
    );
  }
  if (selectedChart === 'client_billing_ranking') {
    return (
      <div className="tableWrap aiTable"><table><thead><tr><th>Client</th><th>Total Billing</th><th>Total Payments</th><th>Outstanding</th></tr></thead><tbody>{rows.map((row) => (
        <tr key={row.client}><td>{row.client}</td><td>{dualMoney(row.billing, row.billing_inr)}</td><td className="creditText">{dualMoney(row.payments, row.payments_inr)}</td><td className={row.outstanding > 0 ? 'outstandingText' : ''}>{dualMoney(row.outstanding, row.outstanding_inr)}</td></tr>
      ))}</tbody></table></div>
    );
  }
  if (selectedChart === 'client_growth_trend') {
    return (
      <div className="chartBars">{rows.map((row) => (
        <div key={row.label} className={`chartBar growthBar ${row.value >= 0 ? 'positive' : 'negative'}`}><span>{row.label}</span><i style={{ width: `${Math.min(100, Math.abs(row.value))}%` }} /><strong>{row.value}%</strong></div>
      ))}</div>
    );
  }
  return (
    <div className="chartBars">{rows.map((row) => (
      <button key={row.label || row.client} className="chartBar" onClick={() => selectedChart === 'charge_type_breakdown' && row.label && setFilters({ ...filters, charge_type: row.label })}>
        <span>{row.label || row.client}</span>
        <i style={{ width: `${Math.min(100, Math.abs(row.value || row.outstanding || 0) / 100)}%` }} />
        <strong>{row.value_inr !== undefined ? dualMoney(row.value, row.value_inr) : money(row.value ?? row.outstanding)}</strong>
      </button>
    ))}</div>
  );
}

function Breakdown({ title, data }) {
  const rows = Object.entries(data);
  return (
    <div className="panel breakdownPanel">
      <h2>{title}</h2>
      {rows.length === 0 ? <p className="muted">No client usage yet.</p> : rows.map(([name, count]) => (
        <div className="breakdownRow" key={name}>
          <span>{name}</span>
          <strong>{count}</strong>
        </div>
      ))}
    </div>
  );
}

function ManagementSection({ title, children }) {
  return (
    <div className="managementSection">
      <h2>{title}</h2>
      <div className="tableWrap">{children}</div>
    </div>
  );
}

function ClusterAccountRow({ row, clients, saving, onSave, canEdit }) {
  const [clientId, setClientId] = useState(row.client_id || '');
  useEffect(() => setClientId(row.client_id || ''), [row.client_id]);
  const key = `cluster-${row.cluster_id}`;
  return (
    <tr>
      <td>{row.cluster}</td>
      <td>{canEdit ? <ClientSelect value={clientId} clients={clients} onChange={setClientId} /> : row.client_name || '-'}</td>
      <td>{row.inbound_ip || <span className="missing">Missing</span>}</td>
      <td><StatusPill value={row.status} /></td>
      <td>{canEdit ? <button onClick={() => onSave(key, '/management/cluster-assignments', { cluster_id: row.cluster_id, client_id: clientId ? Number(clientId) : null })}>{saving === key ? 'Saving...' : 'Save'}</button> : '-'}</td>
    </tr>
  );
}

function RdpClusterRow({ row, rdps, saving, onSave, canEdit }) {
  const [selected, setSelected] = useState(row.rdp_vos_id ? String(row.rdp_vos_id) : '');
  useEffect(() => setSelected(row.rdp_vos_id ? String(row.rdp_vos_id) : ''), [row.rdp_vos_id]);
  const selectedRdp = rdps.find((rdp) => String(rdp.id) === selected);
  const key = `rdp-${row.cluster_id}`;
  return (
      <tr className={row.duplicate_alert ? 'duplicateRow' : ''}>
      <td>{row.cluster}</td>
      <td>{row.client_name || <span className="missing">Unassigned</span>}</td>
      <td>
        {!canEdit ? (row.assigned_rdp || '-') : (
        <select value={selected} onChange={(event) => setSelected(event.target.value)}>
          <option value="">Unassigned</option>
          {rdps.map((rdp) => <option key={rdp.id} value={rdp.id}>{rdp.name} - {rdp.ip}</option>)}
        </select>
        )}
      </td>
      <td>{selectedRdp?.ip || row.assigned_rdp_ip || '-'}</td>
      <td><StatusPill value={row.status} /></td>
      <td>{row.duplicate_alert ? <span className="duplicateText">Duplicate</span> : <span className="okText">Clear</span>}</td>
      <td>{canEdit ? <button onClick={() => onSave(key, '/management/rdp-cluster-assignments', { cluster_id: row.cluster_id, rdp_vos_id: selected ? Number(selected) : null })}>{saving === key ? 'Saving...' : 'Save'}</button> : '-'}</td>
    </tr>
  );
}

function RoutingMediaRow({ row, rdps, rtngs, saving, onSave, canEdit }) {
  const [form, setForm] = useState(row);
  useEffect(() => setForm(row), [row]);
  const key = `routing-${row.rtng_vos_id || row.gateway_name}`;

  const update = (field, value) => {
    const next = { ...form, [field]: value };
    if (field === 'gateway_name') {
      const gateway = rtngs.find((item) => item.portal_type === value || String(item.id) === String(value));
      next.gateway_ip = gateway?.server_ip || '';
      next.rtng_vos_id = gateway?.id || null;
      next.gateway_name = gateway?.portal_type || value;
    }
    if (field === 'media1_name') {
      const rdp = rdps.find((item) => item.name === value || String(item.id) === String(value));
      next.media1_ip = rdp?.ip || '';
      next.media1_vos_id = rdp?.id || null;
      next.media1_name = rdp?.name || value;
    }
    if (field === 'media2_name') {
      const rdp = rdps.find((item) => item.name === value || String(item.id) === String(value));
      next.media2_ip = rdp?.ip || '';
      next.media2_vos_id = rdp?.id || null;
      next.media2_name = rdp?.name || value;
    }
    setForm(next);
  };

  return (
    <tr className={hasMissing(form) ? 'needsAttention' : ''}>
      <td>
        {canEdit ? <select value={form.gateway_name || ''} onChange={(event) => update('gateway_name', event.target.value)}>
          <option value="">Select gateway</option>
          {rtngs.map((gateway) => <option key={gateway.id} value={gateway.portal_type}>{gateway.portal_type}</option>)}
        </select> : form.gateway_name || '-'}
      </td>
      <td>{form.gateway_ip || <span className="missing">Missing</span>}</td>
      <td>{form.clients || <span className="missing">Unassigned</span>}</td>
      <td>{canEdit ? <RdpSelect value={form.media1_name || ''} rdps={rdps} gatewayName={form.gateway_name} onChange={(value) => update('media1_name', value)} /> : form.media1_name || '-'}</td>
      <td>{form.media1_ip || <span className="missing">Missing</span>}</td>
      <td>{canEdit ? <RdpSelect value={form.media2_name || ''} rdps={rdps} gatewayName={form.gateway_name} onChange={(value) => update('media2_name', value)} /> : form.media2_name || '-'}</td>
      <td>{form.media2_ip || <span className="missing">Missing</span>}</td>
      <td>{canEdit ? <input value={form.carrier_ip || ''} onChange={(event) => update('carrier_ip', event.target.value)} /> : form.carrier_ip || '-'}</td>
      <td>{canEdit ? <input value={form.ports || ''} onChange={(event) => update('ports', event.target.value)} /> : form.ports || '-'}</td>
      <td>{canEdit ? <input value={form.vendor_name || ''} onChange={(event) => update('vendor_name', event.target.value)} /> : form.vendor_name || '-'}</td>
      <td>
        {canEdit ? <select value={form.status || 'Active'} onChange={(event) => update('status', event.target.value)}>
          {statuses.map((status) => <option key={status}>{status}</option>)}
        </select> : <StatusPill value={form.status} />}
      </td>
      <td>
        {canEdit ? <button onClick={() => onSave(key, '/management/routing-media-assignments', {
          gateway_name: form.gateway_name,
          rtng_vos_id: form.rtng_vos_id || null,
          media1_name: form.media1_name || null,
          media1_vos_id: form.media1_vos_id || null,
          media2_name: form.media2_name || null,
          media2_vos_id: form.media2_vos_id || null,
          carrier_ip: form.carrier_ip || null,
          ports: form.ports || null,
          vendor_name: form.vendor_name || null,
          status: form.status || 'Active',
        })}>{saving === key ? 'Saving...' : 'Save'}</button> : '-'}
      </td>
    </tr>
  );
}

function RdpSelect({ value, rdps, gatewayName, onChange }) {
  return (
    <select value={value} onChange={(event) => onChange(event.target.value)}>
      <option value="">Unassigned</option>
      {rdps.map((rdp) => {
        const usedElsewhere = rdp.used_in_routing && rdp.used_in_routing !== gatewayName && rdp.name !== value;
        return <option key={rdp.id} value={rdp.name} disabled={usedElsewhere}>{rdp.name} - {rdp.ip}{usedElsewhere ? ' (Already Assigned)' : ''}</option>;
      })}
    </select>
  );
}

function ClientSelect({ value, clients, onChange }) {
  return (
    <select value={value || ''} onChange={(event) => onChange(event.target.value)}>
      <option value="">Unassigned</option>
      {clients.map((client) => <option key={client.id} value={client.id}>{client.name}</option>)}
    </select>
  );
}

function money(value) {
  return usd(value);
}

function usd(value) {
  return `$${Number(value || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function inr(value) {
  return `₹${Number(value || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function dualMoney(usdValue, inrValue) {
  return <span className="dualMoney"><b>{usd(usdValue)}</b><small>{inr(inrValue)}</small></span>;
}

function exchangeText(rate) {
  return `1 USD = ${inr(rate)}`;
}

function exportRows(filename, rows) {
  if (!rows.length) return;
  const headers = Object.keys(rows[0]);
  const csv = [headers.join(','), ...rows.map((row) => headers.map((key) => `"${String(row[key] ?? '').replaceAll('"', '""')}"`).join(','))].join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function CustomerDashboard({ billing, user }) {
  const summary = billing.ledgerSummary || {};
  return (
    <section>
      <div className="customerHeader">
        <h2>{user.username.toUpperCase()} Billing Overview</h2>
        <span className="rolePill">customer scoped</span>
      </div>
      <BillingCards summary={summary} />
      <div className="split">
        <div className="panel">
          <h2>Ledger Snapshot</h2>
          <div className="breakdownRow"><span>Total Outstanding</span><strong className={summary.total_outstanding > 0 ? 'outstandingText' : ''}>{dualMoney(summary.total_outstanding, summary.total_outstanding_inr)}</strong></div>
          <div className="breakdownRow"><span>Monthly Charges</span><strong>{dualMoney(summary.monthly_charges, summary.monthly_charges_inr)}</strong></div>
          <div className="breakdownRow"><span>Monthly Payments</span><strong className="creditText">{dualMoney(summary.monthly_payments, summary.monthly_payments_inr)}</strong></div>
        </div>
        <div className="panel">
          <h2>Billing Focus</h2>
          <div className="breakdownRow"><span>Today Charges</span><strong>{dualMoney(summary.today_total_charges, summary.today_total_charges_inr)}</strong></div>
          <div className="breakdownRow"><span>Today Payments</span><strong className="creditText">{dualMoney(summary.today_payments, summary.today_payments_inr)}</strong></div>
          <div className="breakdownRow"><span>Outstanding</span><strong className={summary.total_outstanding > 0 ? 'outstandingText' : ''}>{dualMoney(summary.total_outstanding, summary.total_outstanding_inr)}</strong></div>
        </div>
      </div>
    </section>
  );
}

function BillingCards({ summary }) {
  const cards = [
    ['Today Charges', summary.today_total_charges, summary.today_total_charges_inr],
    ['Today Payments', summary.today_payments, summary.today_payments_inr],
    ['Monthly Charges', summary.monthly_charges, summary.monthly_charges_inr],
    ['Monthly Payments', summary.monthly_payments, summary.monthly_payments_inr],
    ['Total Outstanding', summary.total_outstanding, summary.total_outstanding_inr],
  ];
  return (
    <div className="cards billingCards">
      {cards.map(([label, value, inrValue]) => (
        <div className={`metric ${label.includes('Outstanding') && Number(value) > 0 ? 'metricAlert' : ''} ${label.includes('Payments') ? 'payment' : ''} ${label.includes('Charges') ? 'revenue' : ''}`} key={label}><span>{label}</span><strong>{dualMoney(value, inrValue)}</strong></div>
      ))}
    </div>
  );
}

function ClientOutstandingTable({ rows }) {
  return (
    <div className="panel">
      <h2>Client-wise Outstanding</h2>
      <table><thead><tr><th>Client</th><th>Outstanding USD</th><th>Outstanding INR</th></tr></thead><tbody>{rows.map((row) => (
        <tr key={row.client}><td>{row.client}</td><td className={row.outstanding > 0 ? 'outstandingText' : 'okText'}>{usd(row.outstanding)}</td><td className={row.outstanding_inr > 0 ? 'outstandingText' : 'okText'}>{inr(row.outstanding_inr)}</td></tr>
      ))}</tbody></table>
    </div>
  );
}

function OutstandingPage({ billing }) {
  return (
    <section>
      <BillingCards summary={billing.ledgerSummary || {}} />
      <ClientOutstandingTable rows={billing.ledgerSummary?.client_outstanding || []} />
    </section>
  );
}

function BillingPage({ billing, data, reload, refreshBilling, user, settings }) {
  const billingPageKey = user.role === 'customer' ? 'my_ledger' : 'billing';
  const canCreate = canDo(user, 'billing', 'can_create');
  const canEdit = canDo(user, 'billing', 'can_edit');
  const canDelete = canDo(user, 'billing', 'can_delete');
  const canExport = canDo(user, billingPageKey, 'can_export');
  const defaultRate = settings?.usd_to_inr_rate || 83;
  const [form, setForm] = useState({ client_id: '', entry_date: new Date().toISOString().slice(0, 10), entry_type: 'Debit', category: 'Usage Charges', description: '', amount_usd: '', amount_inr: '', exchange_rate: defaultRate });
  const [editingLedger, setEditingLedger] = useState(null);
  const [lastEdited, setLastEdited] = useState('usd');
  const [entryError, setEntryError] = useState('');
  const [entryMessage, setEntryMessage] = useState('');
  const [filters, setFilters] = useState({ client_id: '', from_date: '', to_date: '', entry_type: '', category: '', search: '', created_by: '', page: 1, page_size: '50' });
  useEffect(() => {
    if (!form.exchange_rate) setForm((current) => ({ ...current, exchange_rate: settings?.usd_to_inr_rate || 83 }));
  }, [settings?.usd_to_inr_rate]);
  const roundMoney = (value) => Number.isFinite(value) ? String(Math.round(value * 100) / 100) : '';
  const updateUsd = (value) => {
    const rate = Number(form.exchange_rate || defaultRate);
    setLastEdited('usd');
    setEntryError('');
    setForm({ ...form, amount_usd: value, amount_inr: value === '' || !rate ? '' : roundMoney(Number(value) * rate) });
  };
  const updateInr = (value) => {
    const rate = Number(form.exchange_rate || defaultRate);
    setLastEdited('inr');
    setEntryError('');
    setForm({ ...form, amount_inr: value, amount_usd: value === '' || !rate ? '' : roundMoney(Number(value) / rate) });
  };
  const updateRate = (value) => {
    const rate = Number(value);
    setEntryError('');
    setForm((current) => {
      if (!rate) return { ...current, exchange_rate: value };
      if (lastEdited === 'inr') return { ...current, exchange_rate: value, amount_usd: current.amount_inr === '' ? '' : roundMoney(Number(current.amount_inr) / rate) };
      return { ...current, exchange_rate: value, amount_inr: current.amount_usd === '' ? '' : roundMoney(Number(current.amount_usd) * rate) };
    });
  };
  const filteredRows = billing.ledger || [];
  const pageInfo = billing.ledgerPage || { total: filteredRows.length, page: 1, page_size: filteredRows.length || 50, total_pages: 1 };
  const entryMatchesFilters = (entry, activeFilters) => {
    if (!entry) return true;
    if (activeFilters.client_id && String(entry.client_id) !== String(activeFilters.client_id)) return false;
    if (activeFilters.from_date && entry.entry_date < activeFilters.from_date) return false;
    if (activeFilters.to_date && entry.entry_date > activeFilters.to_date) return false;
    if (activeFilters.entry_type && entry.entry_type !== activeFilters.entry_type) return false;
    if (activeFilters.category && entry.category !== activeFilters.category) return false;
    if (activeFilters.search && !String(entry.description || '').toLowerCase().includes(activeFilters.search.toLowerCase())) return false;
    if (activeFilters.created_by && !String(entry.created_by || '').toLowerCase().includes(activeFilters.created_by.toLowerCase())) return false;
    return true;
  };
  const refreshLedger = async (activeFilters = filters) => {
    console.log('[NOC360] Billing filters applied', activeFilters);
    const pageMeta = refreshBilling ? await refreshBilling(activeFilters) : null;
    if (pageMeta && pageMeta.page !== activeFilters.page) setFilters((current) => ({ ...current, page: pageMeta.page }));
    if (!refreshBilling) await reload();
  };
  const applyFilters = (next = filters) => {
    const activeFilters = { ...next, page: next.page || 1 };
    setFilters(activeFilters);
    refreshLedger(activeFilters);
  };
  const dateString = (value) => value.toISOString().slice(0, 10);
  const quickFilter = (mode) => {
    const today = new Date();
    let fromDate = '';
    let toDate = '';
    if (mode === 'today') {
      fromDate = dateString(today);
      toDate = fromDate;
    }
    if (mode === 'week') {
      const start = new Date(today);
      start.setDate(today.getDate() - ((today.getDay() + 6) % 7));
      fromDate = dateString(start);
      toDate = dateString(today);
    }
    if (mode === 'month') {
      fromDate = dateString(new Date(today.getFullYear(), today.getMonth(), 1));
      toDate = dateString(today);
    }
    if (mode === 'lastMonth') {
      const start = new Date(today.getFullYear(), today.getMonth() - 1, 1);
      const end = new Date(today.getFullYear(), today.getMonth(), 0);
      fromDate = dateString(start);
      toDate = dateString(end);
    }
    applyFilters({ ...filters, from_date: fromDate, to_date: toDate, page: 1 });
  };
  const goToClientLedger = (row) => {
    const next = { ...filters, client_id: String(row.client_id || ''), from_date: '', to_date: '', entry_type: '', category: '', search: '', created_by: '', page: 1, page_size: 'all' };
    applyFilters(next);
  };
  const save = async (event) => {
    event.preventDefault();
    setEntryMessage('');
    const rate = Number(form.exchange_rate || defaultRate);
    let amountUsd = Number(form.amount_usd || 0);
    let amountInr = Number(form.amount_inr || 0);
    if (!form.client_id) {
      setEntryError('Select a valid client before saving.');
      return;
    }
    if (!data.clients.some((client) => String(client.id) === String(form.client_id))) {
      setEntryError('Selected client is missing from Client Master.');
      return;
    }
    if (!form.amount_usd && !form.amount_inr) {
      setEntryError('Enter Amount ($) or Amount (₹) before saving.');
      return;
    }
    if (!rate) {
      setEntryError('Enter a valid USD to INR rate.');
      return;
    }
    if (!amountUsd && amountInr) amountUsd = amountInr / rate;
    if (!amountInr && amountUsd) amountInr = amountUsd * rate;
    const body = { client_id: Number(form.client_id), entry_date: form.entry_date, entry_type: form.entry_type, category: form.category, description: form.description, amount_usd: Number(amountUsd.toFixed(2)), amount_inr: Number(amountInr.toFixed(2)), exchange_rate: rate, debit_amount: form.entry_type === 'Debit' ? Number(amountUsd.toFixed(2)) : 0, credit_amount: form.entry_type === 'Credit' ? Number(amountUsd.toFixed(2)) : 0 };
    const response = await request(editingLedger ? `/billing/ledger/${editingLedger.id}` : '/billing/ledger', { method: editingLedger ? 'PUT' : 'POST', body: JSON.stringify(body) });
    console.log('[NOC360] Ledger mutation response', response);
    const savedEntry = response.entry || response;
    const nextFilters = entryMatchesFilters(savedEntry, filters)
      ? { ...filters, page: 1 }
      : { ...filters, client_id: String(savedEntry.client_id || ''), from_date: savedEntry.entry_date || '', to_date: savedEntry.entry_date || '', entry_type: savedEntry.entry_type || '', category: savedEntry.category || '', page: 1 };
    if (nextFilters !== filters) setFilters(nextFilters);
    setEntryError('');
    setEntryMessage(editingLedger ? 'Entry Updated' : 'Entry Saved');
    setEditingLedger(null);
    setForm({ client_id: '', entry_date: new Date().toISOString().slice(0, 10), entry_type: 'Debit', category: 'Usage Charges', description: '', amount_usd: '', amount_inr: '', exchange_rate: defaultRate });
    await refreshLedger(nextFilters);
  };
  const startEdit = (row) => {
    setEditingLedger(row);
    setLastEdited('usd');
    setEntryError('');
    setForm({
      client_id: row.client_id || '',
      entry_date: row.entry_date,
      entry_type: row.entry_type,
      category: row.category,
      description: row.description || '',
      amount_usd: String(row.amount_usd ?? row.debit_usd ?? row.credit_usd ?? ''),
      amount_inr: String(row.amount_inr ?? row.debit_inr ?? row.credit_inr ?? ''),
      exchange_rate: row.exchange_rate || defaultRate,
    });
  };
  const cancelEdit = () => {
    setEditingLedger(null);
    setEntryError('');
    setForm({ client_id: '', entry_date: new Date().toISOString().slice(0, 10), entry_type: 'Debit', category: 'Usage Charges', description: '', amount_usd: '', amount_inr: '', exchange_rate: defaultRate });
  };
  const deleteLedger = async (row) => {
    if (!confirm(`Delete ledger entry for ${row.client_name || 'client'}?`)) return;
    const response = await request(`/billing/ledger/${row.id}`, { method: 'DELETE' });
    console.log('[NOC360] Ledger delete response', response);
    setEntryMessage('Entry Deleted');
    await refreshLedger();
  };
  const previewUsd = Number(form.amount_usd || 0);
  const previewRate = Number(form.exchange_rate || defaultRate);
  const previewInr = Number(form.amount_inr || (previewUsd * previewRate) || 0);
  const ledgerEntryForm = (
    <form className="inlineForm billingEntryForm" onSubmit={save}>
      <ClientSelect value={form.client_id} clients={data.clients} onChange={(value) => setForm({ ...form, client_id: value })} />
      <input type="date" value={form.entry_date} onChange={(event) => setForm({ ...form, entry_date: event.target.value })} />
      <select value={form.entry_type} onChange={(event) => setForm({ ...form, entry_type: event.target.value })}><option>Debit</option><option>Credit</option></select>
      <select value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })}>{ledgerCategories.map((type) => <option key={type}>{type}</option>)}</select>
      <input placeholder="Description" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} />
      <div className="currencyGrid">
        <label className={`fieldLabel currencyField usdField ${lastEdited === 'usd' ? 'activeCurrency' : ''}`}>Amount ($)<input type="number" step="0.01" placeholder="Amount ($)" value={form.amount_usd} onChange={(event) => updateUsd(event.target.value)} /></label>
        <label className={`fieldLabel currencyField inrField ${lastEdited === 'inr' ? 'activeCurrency' : ''}`}>Amount (₹)<input type="number" step="0.01" placeholder="Amount (₹)" value={form.amount_inr} onChange={(event) => updateInr(event.target.value)} /></label>
        <label className="fieldLabel currencyField rateField">Rate (USD→INR)<input type="number" step="0.0001" value={form.exchange_rate} onChange={(event) => updateRate(event.target.value)} /></label>
        <div className="conversionPreview">
          <span>{exchangeText(form.exchange_rate)}</span>
          <strong>Converted Value: {inr(previewInr)}</strong>
          <small>= {usd(previewUsd)} × {Number(previewRate || 0).toFixed(2)} = {inr(previewInr)}</small>
        </div>
      </div>
      {entryError && <span className="formError">{entryError}</span>}
      <button className="primary"><Plus size={16} /> {editingLedger ? 'Update Entry' : 'Save Entry'}</button>
      {editingLedger && <button type="button" onClick={cancelEdit}>Cancel Edit</button>}
    </form>
  );
  return (
    <section>
      <BillingCards summary={billing.ledgerSummary || {}} />
      {Number(billing.ledgerSummary?.total_outstanding || 0) > 0 && <div className="alert billingAlert">💸 Payment pending – follow up before it disappears</div>}
      {user.role === 'admin' && <BillingRateConfig settings={settings} reload={reload} />}
      {false && (
        <form className="inlineForm billingEntryForm" onSubmit={save}>
          <ClientSelect value={form.client_id} clients={data.clients} onChange={(value) => setForm({ ...form, client_id: value })} />
          <input type="date" value={form.entry_date} onChange={(event) => setForm({ ...form, entry_date: event.target.value })} />
          <select value={form.entry_type} onChange={(event) => setForm({ ...form, entry_type: event.target.value })}><option>Debit</option><option>Credit</option></select>
          <select value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })}>{ledgerCategories.map((type) => <option key={type}>{type}</option>)}</select>
          <input placeholder="Description" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} />
          <div className="currencyGrid">
            <label className={`fieldLabel currencyField usdField ${lastEdited === 'usd' ? 'activeCurrency' : ''}`}>Amount ($)<input type="number" step="0.01" placeholder="Amount ($)" value={form.amount_usd} onChange={(event) => updateUsd(event.target.value)} /></label>
            <label className={`fieldLabel currencyField inrField ${lastEdited === 'inr' ? 'activeCurrency' : ''}`}>Amount (₹)<input type="number" step="0.01" placeholder="Amount (₹)" value={form.amount_inr} onChange={(event) => updateInr(event.target.value)} /></label>
            <label className="fieldLabel currencyField rateField">Rate (USD→INR)<input type="number" step="0.0001" value={form.exchange_rate} onChange={(event) => updateRate(event.target.value)} /></label>
            <div className="conversionPreview">
              <span>{exchangeText(form.exchange_rate)}</span>
              <strong>Converted Value: {inr(previewInr)}</strong>
              <small>= {usd(previewUsd)} × {Number(previewRate || 0).toFixed(2)} = {inr(previewInr)}</small>
            </div>
          </div>
          {entryError && <span className="formError">{entryError}</span>}
          <button className="primary"><Plus size={16} /> {editingLedger ? 'Update Entry' : 'Save Entry'}</button>
          {editingLedger && <button type="button" onClick={cancelEdit}>Cancel Edit</button>}
        </form>
      )}
      {canCreate && !editingLedger && ledgerEntryForm}
      {editingLedger && (
        <div className="modalBackdrop modal-overlay">
          <div className="modal modal-box ledgerModal">
            <div className="modalHeader">
              <h2>Edit Ledger Entry</h2>
              <button type="button" className="iconButton" onClick={cancelEdit} title="Close"><X size={18} /></button>
            </div>
            {ledgerEntryForm}
          </div>
        </div>
      )}
      {entryMessage && <div className="toastSuccess">{entryMessage}</div>}
      <div className="toolbar">
        {user.role !== 'customer' && <ClientSelect value={filters.client_id} clients={data.clients} onChange={(value) => setFilters({ ...filters, client_id: value, page: 1 })} />}
        <input type="date" title="From Date" value={filters.from_date} onChange={(event) => setFilters({ ...filters, from_date: event.target.value, page: 1 })} />
        <input type="date" title="To Date" value={filters.to_date} onChange={(event) => setFilters({ ...filters, to_date: event.target.value, page: 1 })} />
        <select value={filters.entry_type} onChange={(event) => setFilters({ ...filters, entry_type: event.target.value, page: 1 })}>
          <option value="">All types</option>
          <option>Debit</option>
          <option>Credit</option>
        </select>
        <select value={filters.category} onChange={(event) => setFilters({ ...filters, category: event.target.value, page: 1 })}>
          <option value="">All categories</option>
          {ledgerCategories.map((type) => <option key={type}>{type}</option>)}
        </select>
        <input placeholder="Search description" value={filters.search} onChange={(event) => setFilters({ ...filters, search: event.target.value, page: 1 })} />
        {user.role !== 'customer' && <input placeholder="Created By" value={filters.created_by} onChange={(event) => setFilters({ ...filters, created_by: event.target.value, page: 1 })} />}
        <select value={filters.page_size} onChange={(event) => applyFilters({ ...filters, page_size: event.target.value, page: 1 })}>
          <option value="25">25</option>
          <option value="50">50</option>
          <option value="100">100</option>
          <option value="all">All</option>
        </select>
        <button onClick={() => applyFilters({ ...filters, page: 1 })}>Run</button>
        <button onClick={() => quickFilter('today')}>Today</button>
        <button onClick={() => quickFilter('week')}>This Week</button>
        <button onClick={() => quickFilter('month')}>This Month</button>
        <button onClick={() => quickFilter('lastMonth')}>Last Month</button>
        <button onClick={() => quickFilter('all')}>All Time</button>
        {canExport && <button onClick={() => exportRows('ledger.csv', filteredRows)}><Download size={16} /> Export CSV</button>}
      </div>
      <div className="paginationBar">
        <span>{pageInfo.total} ledger entries • Page {pageInfo.page} of {pageInfo.total_pages}</span>
        <button disabled={pageInfo.page <= 1 || filters.page_size === 'all'} onClick={() => applyFilters({ ...filters, page: Math.max(1, pageInfo.page - 1) })}>Previous</button>
        <button disabled={pageInfo.page >= pageInfo.total_pages || filters.page_size === 'all'} onClick={() => applyFilters({ ...filters, page: pageInfo.page + 1 })}>Next</button>
        <button onClick={() => applyFilters({ ...filters, page: 1, page_size: 'all' })}>Load All</button>
      </div>
      {user.role !== 'customer' && <ClientOutstandingTable rows={billing.ledgerSummary?.client_outstanding || []} />}
      <div className="tableWrap">
        <table>
          <thead><tr><th>Date</th><th>Client</th><th>Type</th><th>Category</th><th>Description</th><th>Debit $</th><th>Credit $</th><th>Balance $</th><th>Debit ₹</th><th>Credit ₹</th><th>Balance ₹</th><th>Rate</th><th>Created By</th>{(canEdit || canDelete) && <th>Actions</th>}</tr></thead>
          <tbody>{filteredRows.map((row) => (
            <tr key={row.id} className={row.entry_type === 'Credit' ? 'creditRow' : 'debitRow'}>
              <td>{row.entry_date}</td><td><button className="linkButton" onClick={() => goToClientLedger(row)}>{row.client_name}</button></td><td>{row.entry_type}</td><td>{row.category}</td><td>{row.description}</td><td>{usd(row.debit_usd ?? row.debit_amount)}</td><td>{usd(row.credit_usd ?? row.credit_amount)}</td><td className={row.balance_usd > 0 ? 'outstandingText' : 'okText'}>{usd(row.balance_usd ?? row.balance_after_entry)}</td><td>{inr(row.debit_inr)}</td><td>{inr(row.credit_inr)}</td><td className={row.balance_inr > 0 ? 'outstandingText' : 'okText'}>{inr(row.balance_inr)}</td><td>{exchangeText(row.exchange_rate)}</td><td>{row.created_by}</td>{(canEdit || canDelete) && <td className="actions">{canEdit && <button className="iconButton" onClick={() => startEdit(row)} title="Edit ledger entry"><Edit3 size={16} /></button>}{canDelete && <button className="iconButton danger" onClick={() => deleteLedger(row)} title="Delete ledger entry"><Trash2 size={16} /></button>}</td>}
            </tr>
          ))}</tbody>
        </table>
      </div>
    </section>
  );
}

function BillingRateConfig({ settings, reload }) {
  const [rate, setRate] = useState(settings?.usd_to_inr_rate || 83);
  useEffect(() => setRate(settings?.usd_to_inr_rate || 83), [settings?.usd_to_inr_rate]);
  const save = async (event) => {
    event.preventDefault();
    await request('/settings/billing-rate', { method: 'PUT', body: JSON.stringify({ usd_to_inr_rate: Number(rate) }) });
    await reload();
  };
  return (
    <form className="inlineForm settingsForm" onSubmit={save}>
      <strong>Billing Rate</strong>
      <label className="fieldLabel">USD to INR<input type="number" step="0.0001" value={rate} onChange={(event) => setRate(event.target.value)} /></label>
      <span className="ratePreview">{exchangeText(rate)}</span>
      <button className="primary">Save Rate</button>
    </form>
  );
}

function ClientsPage({ clients, reload, user }) {
  const canCreate = canDo(user, 'clients', 'can_create');
  const canEdit = canDo(user, 'clients', 'can_edit');
  const canDelete = canDo(user, 'clients', 'can_delete');
  const canExport = canDo(user, 'clients', 'can_export');
  const [form, setForm] = useState({ name: '', status: 'Active', notes: '', login_username: '', login_password: '', confirm_password: '' });
  const [detail, setDetail] = useState(null);
  const [message, setMessage] = useState('');
  const [resetClient, setResetClient] = useState(null);
  const [newPassword, setNewPassword] = useState('');
  const save = async (event) => {
    event.preventDefault();
    setMessage('');
    if (form.login_password !== form.confirm_password) {
      setMessage('Passwords do not match');
      return;
    }
    await request('/clients', { method: 'POST', body: JSON.stringify(form) });
    setForm({ name: '', status: 'Active', notes: '', login_username: '', login_password: '', confirm_password: '' });
    setMessage('Client and login user created successfully.');
    await reload();
  };
  const remove = async (id) => {
    await request(`/clients/${id}`, { method: 'DELETE' });
    await reload();
  };
  const openDetail = async (id) => setDetail(await request(`/clients/${id}/detail`));
  const resetPassword = async () => {
    if (!resetClient || !newPassword) return;
    await request(`/clients/${resetClient.id}/reset-password`, { method: 'POST', body: JSON.stringify({ password: newPassword }) });
    setMessage(`Password reset for ${resetClient.name}.`);
    setResetClient(null);
    setNewPassword('');
  };
  return (
    <section>
      {message && <div className={message.includes('match') ? 'error' : 'loading'}>{message}</div>}
      {canCreate && <form className="inlineForm" onSubmit={save}>
        <input placeholder="Client name" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
        <select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })}><option>Active</option><option>Inactive</option></select>
        <input placeholder="Notes" value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} />
        <input placeholder="Login username" value={form.login_username} onChange={(event) => setForm({ ...form, login_username: event.target.value })} />
        <input type="password" placeholder="Login password" value={form.login_password} onChange={(event) => setForm({ ...form, login_password: event.target.value })} />
        <input type="password" placeholder="Confirm password" value={form.confirm_password} onChange={(event) => setForm({ ...form, confirm_password: event.target.value })} />
        <button className="primary"><Plus size={16} /> Add Client</button>
      </form>}
      <div className="tableWrap"><table><thead><tr><th>Client</th><th>Status</th><th>Username</th><th>Outstanding USD</th><th>Outstanding INR</th>{(canEdit || canDelete) && <th>Actions</th>}</tr></thead><tbody>{clients.map((client) => (
        <tr key={client.id}><td><button className="linkButton" onClick={() => openDetail(client.id)}>{client.name}</button></td><td><StatusPill value={client.status} /></td><td>{client.username || '-'}</td><td className={client.outstanding_usd > 0 ? 'outstandingText' : ''}>{usd(client.outstanding_usd)}</td><td className={client.outstanding_inr > 0 ? 'outstandingText' : ''}>{inr(client.outstanding_inr)}</td>{(canEdit || canDelete) && <td className="actions">{canEdit && <button onClick={() => setResetClient(client)}>Reset Login Password</button>}{canDelete && <button className="iconButton danger" onClick={() => remove(client.id)}><Trash2 size={16} /></button>}</td>}</tr>
      ))}</tbody></table></div>
      {resetClient && <div className="modalBackdrop modal-overlay"><div className="modal modal-box"><div className="modalHeader"><h2>Reset {resetClient.name}</h2><button className="iconButton" onClick={() => setResetClient(null)}><X size={18} /></button></div><input type="password" placeholder="New password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} /><button className="primary" onClick={resetPassword}>Reset Password</button></div></div>}
      {detail && <ClientDetailModal detail={detail} onClose={() => setDetail(null)} canExport={canExport} />}
    </section>
  );
}

function UserAccessPage({ users, clients, reload, user }) {
  const canCreate = canDo(user, 'user_access', 'can_create');
  const canEdit = canDo(user, 'user_access', 'can_edit');
  const canDelete = canDo(user, 'user_access', 'can_delete');
  const [form, setForm] = useState({ username: '', full_name: '', email: '', role: 'viewer', password: '', status: 'Active', client_id: '' });
  const [selectedUser, setSelectedUser] = useState(null);
  const [permissions, setPermissions] = useState([]);
  const [clientIds, setClientIds] = useState([]);
  const [resetPassword, setResetPassword] = useState('');

  const cards = [
    ['Total Users', users.length],
    ['Admin Users', users.filter((u) => u.role === 'admin').length],
    ['NOC Users', users.filter((u) => u.role === 'noc_user').length],
    ['Customer Users', users.filter((u) => u.role === 'customer').length],
    ['Inactive Users', users.filter((u) => u.status !== 'Active').length],
  ];

  const loadUserAccess = async (user) => {
    setSelectedUser(user);
    const [perms, access] = await Promise.all([request(`/users/${user.id}/permissions`), request(`/users/${user.id}/client-access`)]);
    const byKey = Object.fromEntries(perms.map((item) => [item.page_key, item]));
    setPermissions(pageKeys.map((page_key) => byKey[page_key] || { page_key, can_view: false, can_create: false, can_edit: false, can_delete: false, can_export: false }));
    setClientIds((access.client_ids || []).map(String));
  };

  const createUser = async (event) => {
    event.preventDefault();
    await request('/users', { method: 'POST', body: JSON.stringify({ ...form, client_id: form.client_id ? Number(form.client_id) : null }) });
    setForm({ username: '', full_name: '', email: '', role: 'viewer', password: '', status: 'Active', client_id: '' });
    await reload();
  };

  const updatePermission = (pageKey, field, value) => {
    setPermissions((rows) => rows.map((row) => row.page_key === pageKey ? { ...row, [field]: value } : row));
  };

  const savePermissions = async () => {
    if (!selectedUser) return;
    await request(`/users/${selectedUser.id}/permissions`, { method: 'POST', body: JSON.stringify(permissions) });
    await reload();
  };

  const saveClientAccess = async () => {
    if (!selectedUser) return;
    await request(`/users/${selectedUser.id}/client-access`, { method: 'POST', body: JSON.stringify({ client_ids: clientIds.map(Number) }) });
    await reload();
  };

  const resetUserPassword = async () => {
    if (!selectedUser || !resetPassword) return;
    await request(`/users/${selectedUser.id}/reset-password`, { method: 'POST', body: JSON.stringify({ password: resetPassword }) });
    setResetPassword('');
  };

  const toggleStatus = async (user) => {
    await request(`/users/${user.id}`, { method: 'PUT', body: JSON.stringify({ username: user.username, full_name: user.full_name, email: user.email, role: user.role, client_id: user.client_id, status: user.status === 'Active' ? 'Inactive' : 'Active' }) });
    await reload();
  };

  const remove = async (user) => {
    await request(`/users/${user.id}`, { method: 'DELETE' });
    await reload();
  };

  return (
    <section>
      <div className="cards managementCards">{cards.map(([label, value]) => <div className="metric" key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>
      {canCreate && <form className="inlineForm" onSubmit={createUser}>
        <input placeholder="Username" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
        <input placeholder="Full name" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
        <input placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}><option>admin</option><option>noc_user</option><option>customer</option><option>viewer</option></select>
        {form.role === 'customer' && <ClientSelect value={form.client_id} clients={clients} onChange={(value) => setForm({ ...form, client_id: value })} />}
        <input type="password" placeholder="Password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
        <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}><option>Active</option><option>Inactive</option></select>
        <button className="primary"><Plus size={16} /> Create User</button>
      </form>}

      <div className="tableWrap"><table><thead><tr><th>Username</th><th>Full Name</th><th>Email</th><th>Role</th><th>Client</th><th>Status</th><th>Actions</th></tr></thead><tbody>{users.map((user) => (
        <tr key={user.id}><td>{user.username}</td><td>{user.full_name || '-'}</td><td>{user.email || '-'}</td><td>{user.role}</td><td>{user.client_name || '-'}</td><td><StatusPill value={user.status} /></td><td className="actions"><button onClick={() => loadUserAccess(user)}>Manage</button>{canEdit && <button onClick={() => toggleStatus(user)}>{user.status === 'Active' ? 'Deactivate' : 'Activate'}</button>}{canDelete && <button className="danger" onClick={() => remove(user)}><Trash2 size={15} /></button>}</td></tr>
      ))}</tbody></table></div>

      {selectedUser && (
        <div className="managementSection">
          <h2>Manage {selectedUser.username}</h2>
          <div className="inlineForm">
            <input type="password" placeholder="New password" value={resetPassword} onChange={(e) => setResetPassword(e.target.value)} />
            {canEdit && <button onClick={resetUserPassword}>Reset Password</button>}
          </div>
          <div className="tableWrap"><table><thead><tr><th>Page</th><th>View</th><th>Create</th><th>Edit</th><th>Delete</th><th>Export</th></tr></thead><tbody>{permissions.map((row) => (
            <tr key={row.page_key}><td>{row.page_key.replaceAll('_', ' ')}</td>{['can_view', 'can_create', 'can_edit', 'can_delete', 'can_export'].map((field) => <td key={field}><input type="checkbox" disabled={!canEdit} checked={Boolean(row[field])} onChange={(e) => updatePermission(row.page_key, field, e.target.checked)} /></td>)}</tr>
          ))}</tbody></table></div>
          {canEdit && <button className="primary" onClick={savePermissions}>Save Permissions</button>}
          <div className="managementSection">
            <h2>Client Access</h2>
            <MultiSelect values={clientIds} options={clients} onChange={setClientIds} />
            {canEdit && <button onClick={saveClientAccess}>Save Client Access</button>}
          </div>
        </div>
      )}
    </section>
  );
}

function ClientDetailModal({ detail, onClose, canExport = true }) {
  return (
    <div className="modalBackdrop modal-overlay">
      <div className="modal modal-box clientDetailModal">
        <div className="clientHero"><div><span className="eyebrow">Client Command Profile</span><h2>{detail.client.name}</h2><StatusPill value={detail.client.status} /></div><button className="iconButton" onClick={onClose}><X size={18} /></button></div>
        <h2>Billing Summary</h2>
        <div className="cards billingCards">
          <div className="metric"><span>Status</span><strong>{detail.client.status}</strong></div>
          <div className="metric"><span>Assigned Clusters</span><strong>{detail.assigned_clusters.length}</strong></div>
          <div className="metric"><span>Total Charges</span><strong>{dualMoney(detail.total_charges, detail.total_charges_inr)}</strong></div>
          <div className="metric"><span>Total Payments</span><strong className="creditText">{dualMoney(detail.total_payments, detail.total_payments_inr)}</strong></div>
          <div className={`metric ${detail.total_outstanding > 0 ? 'metricAlert' : ''}`}><span>Total Outstanding</span><strong>{dualMoney(detail.total_outstanding, detail.total_outstanding_inr)}</strong></div>
        </div>
        <div className="panel infraPanel"><h2>Assigned Infrastructure</h2><p><strong>Assigned RDPs:</strong> {detail.assigned_rdps.join(', ') || '-'}</p><p><strong>Routing Gateways:</strong> {detail.routing_gateways.join(', ') || '-'}</p></div>
        <h2>Ledger</h2>
        <div className="tableWrap"><table><thead><tr><th>Date</th><th>Type</th><th>Category</th><th>Description</th><th>Debit $</th><th>Credit $</th><th>Balance $</th><th>Debit ₹</th><th>Credit ₹</th><th>Balance ₹</th><th>Rate</th></tr></thead><tbody>{detail.ledger.map((row) => (
          <tr key={row.id} className={row.entry_type === 'Credit' ? 'creditRow' : 'debitRow'}><td>{row.entry_date}</td><td>{row.entry_type}</td><td>{row.category}</td><td>{row.description}</td><td>{usd(row.debit_usd ?? row.debit_amount)}</td><td>{usd(row.credit_usd ?? row.credit_amount)}</td><td className={row.balance_usd > 0 ? 'outstandingText' : ''}>{usd(row.balance_usd ?? row.balance_after_entry)}</td><td>{inr(row.debit_inr)}</td><td>{inr(row.credit_inr)}</td><td className={row.balance_inr > 0 ? 'outstandingText' : ''}>{inr(row.balance_inr)}</td><td>{exchangeText(row.exchange_rate)}</td></tr>
        ))}</tbody></table></div>
        {canExport && <div className="toolbar"><button onClick={() => exportRows(`${detail.client.name}-ledger.csv`, detail.ledger || [])}><Download size={16} /> Export Ledger CSV</button></div>}
        <h2>Data Cost</h2>
        <div className="tableWrap"><table><thead><tr><th>Date</th><th>Quantity</th><th>Rate $</th><th>Total $</th><th>Total ₹</th><th>Description</th></tr></thead><tbody>{(detail.data_costs || []).map((row) => (
          <tr key={row.id}><td>{row.entry_date}</td><td>{row.quantity}</td><td>{usd(row.rate_usd ?? row.rate)}</td><td>{usd(row.total_cost_usd ?? row.total_cost)}</td><td>{inr(row.total_cost_inr)}</td><td>{row.description}</td></tr>
        ))}</tbody></table></div>
      </div>
    </div>
  );
}

function DownloadsPage({ billing, user }) {
  const canExportLedger = canDo(user, 'my_ledger', 'can_export');
  return (
    <section className="panel downloadsPanel">
      <h2>Downloads</h2>
      {canExportLedger && <button onClick={() => exportRows('my-ledger.csv', billing.ledger || [])}><Download size={16} /> Ledger CSV</button>}
      {canExportLedger && <button onClick={() => exportRows('my-billing.csv', billing.rows || [])}><Download size={16} /> Billing CSV</button>}
    </section>
  );
}

function CustomerCdrPage({ user }) {
  const [rows, setRows] = useState([]);
  const canExport = canDo(user, 'my_cdr', 'can_export');
  useEffect(() => {
    request('/cdr').then(setRows).catch(() => setRows([]));
  }, []);
  return (
    <section>
      <div className="toolbar">{canExport && <button onClick={() => exportRows('my-cdr.csv', rows)}><Download size={16} /> Export CSV</button>}</div>
      <div className="tableWrap"><table><thead><tr><th>Call Date</th><th>Caller</th><th>Destination</th><th>Duration</th><th>Disposition</th><th>Cost</th><th>Route</th><th>Gateway</th></tr></thead><tbody>{rows.map((row) => (
        <tr key={row.id}><td>{String(row.call_date).replace('T', ' ').slice(0, 19)}</td><td>{row.caller_id}</td><td>{row.destination}</td><td>{row.duration}</td><td>{row.disposition}</td><td>{usd(row.cost)}</td><td>{row.route}</td><td>{row.gateway}</td></tr>
      ))}</tbody></table></div>
    </section>
  );
}

function Dashboard({ dashboard, data, setActive }) {
  const summary = dashboard?.summary || {};
  const cards = [
    ['RDP Total', summary.rdp_total, MonitorCog],
    ['Used RDP', summary.rdp_used, Activity],
    ['Free RDP', summary.rdp_free, Server],
    ['Routing Gateways', summary.routing_gateways, Router],
    ['Clusters', summary.clusters, RadioTower],
    ['Clients', summary.clients, Users],
    ['Alerts', summary.alerts, AlertTriangle],
  ];

  return (
    <section className="dashboard">
      <div className="cards">
        {cards.map(([label, value, Icon]) => (
          <button className={`metric ${label === 'Alerts' && value ? 'metricAlert' : ''}`} key={label}>
            <Icon size={24} />
            <span>{label}</span>
            <strong>{value ?? 0}</strong>
          </button>
        ))}
      </div>

      <BriefTable title="RDP Brief View" rows={dashboard?.rdp_brief || []} columns={[['rdp_name','RDP Name'],['ip','IP'],['status','Status'],['assigned_cluster','Assigned Cluster'],['client','Client'],['used_in_routing','Used In Routing'],['usage_status','Usage Status']]} />
      <BriefTable title="Routing Brief View" rows={dashboard?.routing_brief || []} columns={[['gateway_name','RTNG'],['gateway_ip','Gateway IP'],['media1_name','Media 1'],['media2_name','Media 2'],['carrier_ip','Carrier IP'],['ports','Ports'],['vendor_name','Vendor']]} />
      <BriefTable title="Cluster Brief View" rows={dashboard?.cluster_brief || []} columns={[['cluster_no','Cluster No'],['cluster_name','Cluster Name'],['inbound_ip','Inbound IP'],['client','Client'],['assigned_rdp','Assigned RDP'],['assigned_rdp_ip','RDP IP']]} />
      <BriefTable title="Client Brief View" rows={dashboard?.client_brief || []} columns={[['client','Client'],['assigned_clusters','Assigned Clusters'],['used_rdp','Used RDP'],['outstanding','Outstanding']]} moneyKey="outstanding" moneyInrKey="outstanding_inr" />
      <div className="panel">
        <h2><AlertTriangle size={19} /> Alerts</h2>
        <div className="alertList">
          {(dashboard?.alerts || []).length === 0 && <p className="muted">No duplicate or missing-IP alerts.</p>}
          {(dashboard?.alerts || []).map((alert, index) => <div className={`alert ${alert.type}`} key={`${alert.message}-${index}`}><AlertTriangle size={17} />{cyberAlertMessage(alert)}</div>)}
        </div>
      </div>
    </section>
  );
}

function BriefTable({ title, rows, columns, moneyKey, moneyInrKey }) {
  return (
    <div className="managementSection">
      <h2>{title}</h2>
      <div className="tableWrap"><table><thead><tr>{columns.map(([, label]) => <th key={label}>{label}</th>)}</tr></thead><tbody>{rows.map((row, index) => (
        <tr key={index}>{columns.map(([key]) => <td key={key} className={moneyKey === key && row[key] > 0 ? 'outstandingText' : ''}>{moneyKey === key ? (moneyInrKey ? dualMoney(row[key], row[moneyInrKey]) : money(row[key])) : (key.includes('status') ? <StatusPill value={row[key]} /> : row[key] || '-')}</td>)}</tr>
      ))}</tbody></table></div>
    </div>
  );
}

function CrudPage({ moduleKey, config, rows, rdps, rtngs, clients = [], reload, user }) {
  const [query, setQuery] = useState('');
  const [editing, setEditing] = useState(null);
  const [saving, setSaving] = useState(false);
  const pageKey = modulePageKeys[moduleKey];
  const canCreate = canDo(user, pageKey, 'can_create');
  const canEdit = canDo(user, pageKey, 'can_edit');
  const canDelete = canDo(user, pageKey, 'can_delete');
  const canExport = canDo(user, pageKey, 'can_export');

  const filtered = useMemo(() => {
    const needle = query.toLowerCase();
    return rows.filter((row) => Object.values(row).join(' ').toLowerCase().includes(needle));
  }, [rows, query]);

  const exportCsv = () => {
    const headers = ['id', ...config.fields.map(([key]) => key)];
    const csv = [
      headers.join(','),
      ...filtered.map((row) => headers.map((key) => `"${String(row[key] ?? '').replaceAll('"', '""')}"`).join(',')),
    ].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${moduleKey}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const save = async (record) => {
    setSaving(true);
    try {
      const method = record.id ? 'PUT' : 'POST';
      const path = `${config.endpoint}${record.id ? `/${record.id}` : ''}`;
      const body = Object.fromEntries(config.fields.map(([key, , type]) => {
        if (['number', 'client'].includes(type)) return [key, record[key] ? Number(record[key]) : null];
        if (type === 'boolean') return [key, Boolean(record[key])];
        return [key, record[key] || null];
      }));
      await request(path, { method, body: JSON.stringify(body) });
      setEditing(null);
      await reload();
    } finally {
      setSaving(false);
    }
  };

  const remove = async (record) => {
    if (!confirm(`Delete ${record[config.titleField] || 'record'}?`)) return;
    await request(`${config.endpoint}/${record.id}`, { method: 'DELETE' });
    await reload();
  };

  return (
    <section className="page">
      <div className="toolbar">
        <div className="search">
          <Search size={18} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search inventory..." />
        </div>
        {canExport && <button onClick={exportCsv}><Download size={17} /> Export CSV</button>}
        {!config.readOnlyInventory && canCreate && (
          <button className="primary" onClick={() => setEditing(emptyRecord(config.fields))}><Plus size={17} /> Add</button>
        )}
      </div>

      <div className="tableWrap">
        <table>
          <thead>
            <tr>
              {config.fields.slice(0, 7).map(([, label]) => <th key={label}>{label}</th>)}
              {!config.readOnlyInventory && (canEdit || canDelete) && <th>Actions</th>}
            </tr>
          </thead>
          <tbody>
            {filtered.map((row) => (
              <tr key={row.id} className={hasMissing(row) ? 'needsAttention' : ''}>
                {config.fields.slice(0, 7).map(([key, , type]) => (
                  <td key={key}>{key === 'status' || type === 'readonlyStatus' ? <StatusPill value={row[key]} /> : type === 'client' ? (row.client_name || <span className="missing">Unassigned</span>) : row[key] || (config.readOnlyInventory ? '-' : <span className="missing">Missing</span>)}</td>
                ))}
                {!config.readOnlyInventory && (canEdit || canDelete) && <td className="actions">
                  {canEdit && <button className="iconButton" onClick={() => setEditing(row)} title="Edit"><Edit3 size={16} /></button>}
                  {canDelete && <button className="iconButton danger" onClick={() => remove(row)} title="Delete"><Trash2 size={16} /></button>}
                </td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {editing && (
        <Editor
          config={config}
          record={editing}
          rdps={rdps}
          rtngs={rtngs}
          clients={clients}
          saving={saving}
          onClose={() => setEditing(null)}
          onSave={save}
        />
      )}
    </section>
  );
}

function hasMissing(row) {
  return Object.values(row).some((value) => value === '' || String(value).toUpperCase() === '#N/A');
}

function Editor({ config, record, rdps, rtngs = [], clients = [], saving, onClose, onSave }) {
  const [form, setForm] = useState(record);

  const setField = (key, value) => {
    const next = { ...form, [key]: value };
    if (key === 'assigned_rdp') {
      const rdp = rdps.find((item) => item.name === value);
      next.assigned_rdp_ip = rdp?.ip || '';
    }
    if (key === 'gateway_name') {
      const gateway = rtngs.find((item) => item.portal_type === value);
      next.gateway_ip = gateway?.server_ip || '';
    }
    if (key === 'media1_name') {
      const rdp = rdps.find((item) => item.name === value);
      next.media1_ip = rdp?.ip || '';
    }
    if (key === 'media2_name') {
      const rdp = rdps.find((item) => item.name === value);
      next.media2_ip = rdp?.ip || '';
    }
    setForm(next);
  };

  return (
    <div className="modalBackdrop modal-overlay">
      <form className="modal modal-box" onSubmit={(event) => { event.preventDefault(); onSave(form); }}>
        <div className="modalHeader">
          <h2>{record.id ? 'Edit' : 'Add'} {config.label}</h2>
          <button type="button" className="iconButton" onClick={onClose} title="Close"><X size={18} /></button>
        </div>
        <div className="formGrid">
          {config.fields.map(([key, label, type]) => (
            <label key={key} className={type === 'textarea' ? 'wide' : ''}>
              <span>{label}</span>
              {type === 'status' && (
                <select value={form[key] || 'Active'} onChange={(event) => setField(key, event.target.value)}>
                  {statuses.map((status) => <option key={status}>{status}</option>)}
                </select>
              )}
              {type === 'readonlyStatus' && <StatusPill value={form[key]} />}
              {type === 'rdp' && (
                <select value={form[key] || ''} onChange={(event) => setField(key, event.target.value)}>
                  <option value="">Unassigned</option>
                  {rdps.map((rdp) => <option key={rdp.id} value={rdp.name}>{rdp.name} - {rdp.ip}</option>)}
                </select>
              )}
              {type === 'rtng' && (
                <select value={form[key] || ''} onChange={(event) => setField(key, event.target.value)}>
                  <option value="">Select gateway</option>
                  {rtngs.map((gateway) => (
                    <option key={gateway.id} value={gateway.portal_type}>{gateway.portal_type} - {gateway.server_ip}</option>
                  ))}
                </select>
              )}
              {type === 'client' && <ClientSelect value={form[key] || ''} clients={clients} onChange={(value) => setField(key, value)} />}
              {type === 'boolean' && <input type="checkbox" checked={Boolean(form[key])} onChange={(event) => setField(key, event.target.checked)} />}
              {type === 'textarea' && <textarea value={form[key] || ''} onChange={(event) => setField(key, event.target.value)} />}
              {type === 'readonly' && <input value={form[key] || ''} readOnly />}
              {!['status', 'readonlyStatus', 'rdp', 'rtng', 'client', 'boolean', 'textarea', 'readonly'].includes(type) && (
                <input type={type} value={form[key] ?? ''} onChange={(event) => setField(key, event.target.value)} />
              )}
            </label>
          ))}
        </div>
        <div className="modalActions">
          <button type="button" onClick={onClose}>Cancel</button>
          <button className="primary" disabled={saving}>{saving ? 'Saving...' : 'Save'}</button>
        </div>
      </form>
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
