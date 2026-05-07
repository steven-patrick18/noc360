import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Activity,
  AlertTriangle,
  Bell,
  ChevronDown,
  ChevronRight,
  Copy,
  Download,
  Edit3,
  ExternalLink,
  Eye,
  EyeOff,
  FileAudio,
  FolderOpen,
  Globe2,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  MonitorCog,
  Mic,
  MicOff,
  Phone,
  PhoneOff,
  Palette,
  PanelLeftClose,
  PanelLeftOpen,
  Play,
  Plus,
  ReceiptText,
  RadioTower,
  RefreshCcw,
  Router,
  Search,
  Send,
  Server,
  Settings,
  Star,
  Terminal as TerminalIcon,
  Ticket,
  Trash2,
  Upload,
  Users,
  X,
} from 'lucide-react';
import { Terminal as XTerm } from 'xterm';
import { FitAddon } from 'xterm-addon-fit';
import 'xterm/css/xterm.css';
import './styles.css';
import './themes.css';

const API_BASE_URL = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '');
const statuses = ['Active', 'Pending', 'Inactive'];
const chargeTypes = ['Usage Charges', 'DID Charges', 'Data Charges', 'Server Charges', 'Port Charges', 'Setup Charges', 'Other Charges'];
const ledgerCategories = [...chargeTypes, 'Payment', 'Adjustment'];
const themeOptions = [
  { id: 'executive', name: 'Executive NOC', description: 'Dark luxury command center', colors: ['#06080f', '#00e5ff', '#d6b46a'] },
  { id: 'cyber', name: 'Cyber Neon', description: 'High-energy cyber operations', colors: ['#020617', '#00f0ff', '#ff2bd6'] },
  { id: 'minimal', name: 'Dark Minimal', description: 'Quiet enterprise workspace', colors: ['#09090b', '#d4d4d8', '#71717a'] },
  { id: 'deep-blue', name: 'Deep Blue Command', description: 'Oceanic telecom control', colors: ['#04111f', '#38bdf8', '#2563eb'] },
  { id: 'purple', name: 'Purple Matrix', description: 'Violet intelligence grid', colors: ['#10081f', '#a855f7', '#22d3ee'] },
  { id: 'emerald', name: 'Emerald Ops', description: 'Green uptime operations', colors: ['#03140d', '#00ff9c', '#a3e635'] },
  { id: 'amber', name: 'Amber Terminal', description: 'Classic operator console', colors: ['#120d05', '#ffb800', '#f97316'] },
  { id: 'red-alert', name: 'Red Alert', description: 'Incident response mode', colors: ['#140609', '#ff4d4d', '#f97316'] },
  { id: 'light', name: 'Light Professional', description: 'Clean daytime SaaS', colors: ['#f7fafc', '#0369a1', '#0f766e'] },
  { id: 'glass-ultra', name: 'Glass Ultra', description: 'Transparent premium glass', colors: ['#030712', '#7dd3fc', '#c084fc'] },
];
const CUSTOM_BACKGROUND_KEY = 'noc360_theme_custom_background';
const MAX_CUSTOM_BACKGROUND_BYTES = 2 * 1024 * 1024;
const MAX_CUSTOM_BACKGROUND_SOURCE_BYTES = 10 * 1024 * 1024;
const defaultCustomBackground = { image: '', opacity: 55, blur: 0, overlayColor: '#000000' };

function resolveTheme(themeId) {
  if (themeId !== 'auto') return themeId || 'executive';
  const hour = new Date().getHours();
  return hour >= 7 && hour < 18 ? 'light' : 'executive';
}

function clampNumber(value, min, max, fallback) {
  const number = Number(value);
  if (!Number.isFinite(number)) return fallback;
  return Math.min(max, Math.max(min, number));
}

function normalizeHexColor(value, fallback = '#000000') {
  const text = String(value || '').trim();
  return /^#[0-9a-f]{6}$/i.test(text) ? text : fallback;
}

function hexToRgb(value) {
  const hex = normalizeHexColor(value).slice(1);
  return `${parseInt(hex.slice(0, 2), 16)}, ${parseInt(hex.slice(2, 4), 16)}, ${parseInt(hex.slice(4, 6), 16)}`;
}

function normalizeCustomBackground(value = {}) {
  return {
    image: typeof value.image === 'string' ? value.image : '',
    opacity: clampNumber(value.opacity, 0, 100, defaultCustomBackground.opacity),
    blur: clampNumber(value.blur, 0, 20, defaultCustomBackground.blur),
    overlayColor: normalizeHexColor(value.overlayColor, defaultCustomBackground.overlayColor),
  };
}

function loadCustomBackground() {
  try {
    return normalizeCustomBackground(JSON.parse(localStorage.getItem(CUSTOM_BACKGROUND_KEY) || '{}'));
  } catch {
    localStorage.removeItem(CUSTOM_BACKGROUND_KEY);
    return defaultCustomBackground;
  }
}

function applyCustomBackground(settings) {
  const next = normalizeCustomBackground(settings);
  if (!next.image) {
    document.body.removeAttribute('data-custom-bg');
    document.body.style.removeProperty('--custom-bg-image');
    document.body.style.removeProperty('--custom-bg-overlay-opacity');
    document.body.style.removeProperty('--custom-bg-blur');
    document.body.style.removeProperty('--custom-bg-overlay-rgb');
    return;
  }
  document.body.setAttribute('data-custom-bg', '1');
  document.body.style.setProperty('--custom-bg-image', `url("${next.image.replaceAll('"', '\\"')}")`);
  document.body.style.setProperty('--custom-bg-overlay-opacity', String(next.opacity / 100));
  document.body.style.setProperty('--custom-bg-blur', `${next.blur}px`);
  document.body.style.setProperty('--custom-bg-overlay-rgb', hexToRgb(next.overlayColor));
}

function dataUrlBytes(dataUrl) {
  const payload = String(dataUrl || '').split(',')[1] || '';
  return Math.ceil((payload.length * 3) / 4);
}

function loadImageFromUrl(url) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error('Unable to read image file.'));
    image.src = url;
  });
}

async function optimizeCustomBackground(file) {
  if (!file) throw new Error('Select an image first.');
  if (!file.type.startsWith('image/')) throw new Error('Only image files are supported.');
  if (file.size > MAX_CUSTOM_BACKGROUND_SOURCE_BYTES) throw new Error('Image is too large. Please choose an image under 10MB.');
  const objectUrl = URL.createObjectURL(file);
  try {
    const image = await loadImageFromUrl(objectUrl);
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');
    const maxSide = file.size > MAX_CUSTOM_BACKGROUND_BYTES ? 1600 : 1920;
    const scale = Math.min(1, maxSide / Math.max(image.width, image.height));
    canvas.width = Math.max(1, Math.round(image.width * scale));
    canvas.height = Math.max(1, Math.round(image.height * scale));
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    let dataUrl = '';
    for (const quality of [0.86, 0.76, 0.66, 0.56, 0.48]) {
      dataUrl = canvas.toDataURL('image/jpeg', quality);
      if (dataUrlBytes(dataUrl) <= MAX_CUSTOM_BACKGROUND_BYTES) return dataUrl;
    }
    if (dataUrlBytes(dataUrl) <= MAX_CUSTOM_BACKGROUND_BYTES) return dataUrl;
    throw new Error('Compressed image is still above 2MB. Try a smaller background.');
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

const pageKeys = ['dashboard', 'my_dashboard', 'business_ai', 'reports', 'my_reports', 'management_portal', 'billing', 'my_ledger', 'clients', 'cdr', 'my_cdr', 'vos_portals', 'vos_desktop_launcher', 'dialer_clusters', 'rdp_media', 'routing_gateways', 'user_access', 'activity_logs', 'chat_center', 'my_chat', 'group_chat', 'tickets', 'my_tickets', 'webphone', 'terminal', 'asterisk_sound_manager', 'bare_metal_os_installer', 'update_center'];
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
  activityLogs: 'activity_logs',
  chatCenter: 'chat_center',
  tickets: 'tickets',
  myChat: 'my_chat',
  myTickets: 'my_tickets',
  webphone: 'webphone',
  terminal: 'terminal',
  asteriskSoundManager: 'asterisk_sound_manager',
  bareMetalOsInstaller: 'bare_metal_os_installer',
  updateCenter: 'update_center',
  dangerZone: 'danger_zone',
};

const modules = {
  dashboard: { label: 'Command Center', icon: Activity },
  businessAi: { label: 'Intelligence Core', icon: Activity },
  reports: { label: 'Data Intelligence', icon: Download },
  management: { label: 'Management Portal', icon: LayoutDashboard },
  billing: { label: 'Money Engine', icon: ReceiptText },
  clients: { label: 'Clients', icon: Users },
  chatCenter: { label: 'Chat Center', icon: MessageSquare },
  tickets: { label: 'Tickets', icon: Ticket },
  webphone: { label: 'Webphone', icon: Phone },
  terminal: { label: 'Terminal', icon: TerminalIcon },
  asteriskSoundManager: { label: 'Asterisk Sound Manager', icon: FileAudio },
  bareMetalOsInstaller: { label: 'Bare Metal OS Installer', icon: Server },
  updateCenter: { label: 'Update Center', icon: RefreshCcw },
  dangerZone: { label: 'Settings', icon: Settings },
  userAccess: { label: 'User Access', icon: Users },
  activityLogs: { label: 'Activity Logs', icon: Activity },
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
    tableFields: [
      ['gateway_name', 'Routing Gateway'],
      ['gateway_ip', 'Gateway IP'],
      ['media_1_name', 'Media 1'],
      ['media_1_ip', 'Media 1 IP'],
      ['media_2_name', 'Media 2'],
      ['media_2_ip', 'Media 2 IP'],
      ['carrier_ip', 'Carrier IP'],
      ['ports', 'Ports'],
      ['vendor', 'Vendor'],
      ['status', 'Status'],
      ['validation_alerts', 'Alerts'],
    ],
    fields: [
      ['gateway_name', 'Gateway Name', 'rtng'],
      ['gateway_ip', 'Gateway IP', 'readonly'],
      ['media_1_name', 'Media 1 Name', 'media'],
      ['media_1_ip', 'Media 1 IP', 'readonly'],
      ['media_2_name', 'Media 2 Name', 'media'],
      ['media_2_ip', 'Media 2 IP', 'readonly'],
      ['carrier_ip', 'Carrier IP', 'text'],
      ['ports', 'Ports', 'text'],
      ['vendor', 'Vendor Name', 'text'],
      ['status', 'Status', 'status'],
    ],
  },
};

const customerModules = {
  myDashboard: { label: 'My Dashboard', icon: Activity },
  myChat: { label: 'My Chat', icon: MessageSquare },
  myTickets: { label: 'My Tickets', icon: Ticket },
  myBilling: { label: 'My Ledger', icon: ReceiptText },
  myCdr: { label: 'My CDR', icon: RadioTower },
  myReports: { label: 'My Reports', icon: Download },
};

const sidebarGroups = [
  { id: 'core', label: 'Core', keys: ['dashboard', 'myDashboard', 'businessAi', 'reports', 'myReports'] },
  { id: 'operations', label: 'Operations', keys: ['management', 'clients', 'vos', 'vosDesktop', 'clusters', 'rdps', 'gateways'] },
  { id: 'finance', label: 'Finance', keys: ['billing', 'myBilling'] },
  { id: 'communication', label: 'Communication', keys: ['chatCenter', 'myChat', 'tickets', 'myTickets'] },
  { id: 'voipTools', label: 'VoIP Tools', keys: ['webphone', 'terminal', 'asteriskSoundManager', 'myCdr'] },
  { id: 'admin', label: 'Admin', keys: ['bareMetalOsInstaller', 'updateCenter', 'userAccess', 'activityLogs', 'dangerZone'] },
];

function emptyRecord(fields) {
  return Object.fromEntries(fields.map(([key, , type]) => [key, type === 'number' ? 0 : type === 'boolean' ? false : key === 'status' ? 'Active' : '']));
}

async function request(path, options = {}) {
  const token = localStorage.getItem('noc360_token');
  const isFormData = options.body instanceof FormData;
  const headers = { ...(isFormData ? {} : { 'Content-Type': 'application/json' }), ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers,
    ...options,
  });
  if (!response.ok) {
    const contentType = response.headers.get('content-type') || '';
    const error = contentType.includes('application/json') ? await response.json().catch(() => ({})) : {};
    const fallback = await (!contentType.includes('application/json') ? response.text().catch(() => '') : Promise.resolve(''));
    const message = error.detail || fallback || `Request failed (${response.status})`;
    if (response.status === 401 && path !== '/auth/login') {
      localStorage.removeItem('noc360_token');
      localStorage.removeItem('noc360_user');
      if (window.location.pathname !== '/login') window.history.pushState({}, '', '/login');
    }
    throw new Error(message);
  }
  return response.json();
}

async function requestBlob(path, options = {}) {
  const token = localStorage.getItem('noc360_token');
  const headers = { ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${API_BASE_URL}${path}`, { headers, ...options });
  if (!response.ok) {
    const message = await response.text().catch(() => '') || `Request failed (${response.status})`;
    throw new Error(message);
  }
  return response.blob();
}

function websocketEndpoint(path) {
  const token = localStorage.getItem('noc360_token') || '';
  const base = API_BASE_URL.startsWith('http') ? API_BASE_URL : `${window.location.origin}${API_BASE_URL}`;
  const url = new URL(`${base}${path}`);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  if (token) url.searchParams.set('token', token);
  return url.toString();
}

function StatusPill({ value }) {
  const raw = String(value || 'Unknown');
  const normalized = raw.toLowerCase().trim();
  const displayStatus = {
    active: 'ONLINE',
    pending: 'WARMING',
    inactive: 'OFFLINE',
    'high usage': 'HIGH LOAD',
    'high load': 'HIGH LOAD',
  }[normalized] || raw;
  const className = normalized === 'high usage' ? 'high-load' : normalized.replace(/[^a-z0-9]+/g, '-');
  return <span className={`status ${className}`}>{displayStatus}</span>;
}

function canDo(user, pageKey, action = 'can_view') {
  if (user?.role === 'admin') return true;
  return Boolean(user?.permissions?.[pageKey]?.[action]);
}

function isMediaPortal(portal) {
  const type = String(portal?.portal_type || portal?.name || '').toUpperCase();
  return type.startsWith('RDP') || type.startsWith('DID') || type.includes('DID');
}

function todayDate() {
  return new Date().toISOString().slice(0, 10);
}

function isRtngPortalName(value) {
  return String(value || '').toUpperCase().startsWith('RTNG');
}

function cyberAlertMessage(alert) {
  const message = String(alert?.message || alert || '');
  if (/rdp|media/i.test(message)) return `Media node attention - ${message}`;
  if (/payment|outstanding|billing/i.test(message)) return 'Payment follow-up required';
  return message;
}

function cyberInsightText(item, fallbackClient = 'ROLEX') {
  const text = String(item || '');
  if (/outstanding|cashflow|payment/i.test(text)) return `Cashflow signal: improve collection from ${fallbackClient}`;
  if (/revenue|billing|growth/i.test(text)) return `Growth signal: ${text}`;
  if (/rdp|gateway|risk|drop/i.test(text)) return `Risk signal: ${text}`;
  return `Insight: ${text}`;
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
  const [communicationSummary, setCommunicationSummary] = useState({ direct_unread: 0, group_unread: 0, chat_unread: 0, open_tickets: 0 });
  const [settings, setSettings] = useState({ usd_to_inr_rate: 83 });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [profileOpen, setProfileOpen] = useState(false);
  const [themeOpen, setThemeOpen] = useState(false);
  const [theme, setTheme] = useState(() => localStorage.getItem('noc360_theme') || 'executive');
  const [customBackground, setCustomBackground] = useState(loadCustomBackground);
  const [toast, setToast] = useState('');
  const [terminalHasMounted, setTerminalHasMounted] = useState(false);
  const [isSidebarCompact, setIsSidebarCompact] = useState(() => localStorage.getItem('noc360_sidebar_compact') === '1');
  const [collapsedSidebarGroups, setCollapsedSidebarGroups] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('noc360_sidebar_groups') || '{}') || {};
    } catch {
      localStorage.removeItem('noc360_sidebar_groups');
      return {};
    }
  });

  const refreshBillingData = async (ledgerFilters = {}) => {
    if (!auth) return;
    const canBilling = canDo(auth.user, 'billing') || canDo(auth.user, 'my_ledger');
    if (!canBilling) {
      setBilling({ rows: [], summary: null, ledger: [], ledgerPage: { total: 0, page: 1, page_size: 50, total_pages: 1 }, ledgerSummary: null });
      return null;
    }
    if (auth.user.role === 'customer') {
      const billingRate = await request('/settings/billing-rate');
      setBilling({ rows: [], summary: null, ledger: [], ledgerPage: { total: 0, page: 1, page_size: 50, total_pages: 1 }, ledgerSummary: null });
      setSettings(billingRate);
      return { total: 0, page: 1, page_size: 50, total_pages: 1 };
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
      const hasComms = ['chat_center', 'my_chat', 'group_chat', 'tickets', 'my_tickets'].some((pageKey) => canDo(auth.user, pageKey));
      if (hasComms) {
        request('/communication/summary').then(setCommunicationSummary).catch(() => setCommunicationSummary({ direct_unread: 0, group_unread: 0, chat_unread: 0, open_tickets: 0 }));
      }

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
    const applyTheme = () => {
      document.body.setAttribute('data-theme', resolveTheme(theme));
      document.body.setAttribute('data-theme-choice', theme);
      applyCustomBackground(customBackground);
    };
    applyTheme();
    if (theme !== 'auto') return undefined;
    const timer = window.setInterval(applyTheme, 60000);
    return () => window.clearInterval(timer);
  }, [theme, customBackground]);

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

  const updateTheme = (themeId) => {
    localStorage.setItem('noc360_theme', themeId);
    setTheme(themeId);
    showToast(themeId === 'auto' ? 'Auto theme enabled' : `${themeOptions.find((item) => item.id === themeId)?.name || 'Theme'} applied`);
  };

  const updateCustomBackground = (settings) => {
    const next = normalizeCustomBackground(settings);
    try {
      localStorage.setItem(CUSTOM_BACKGROUND_KEY, JSON.stringify(next));
    } catch {
      showToast('Custom background storage is full. Try a smaller image.');
      return;
    }
    setCustomBackground(next);
    applyCustomBackground(next);
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
    request('/activity-logs/track', {
      method: 'POST',
      body: JSON.stringify({ action: 'logout', module: 'auth', record_type: 'User', record_id: auth?.user?.id, description: 'User logged out' }),
    }).catch(() => {});
    localStorage.removeItem('noc360_token');
    localStorage.removeItem('noc360_user');
    localStorage.removeItem('noc360_terminal_tabs');
    localStorage.removeItem('noc360_terminal_active_tab');
    setTerminalHasMounted(false);
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
  const isSuperAdmin = auth.user.role === 'admin' && auth.user.username === 'admin';
  const activeModules = auth.user.role === 'customer'
    ? Object.fromEntries(Object.entries(customerModules).filter(([key]) => hasPermission(key)))
    : Object.fromEntries(Object.entries(modules).filter(([key]) => (key !== 'dangerZone' || isSuperAdmin) && hasPermission(key)));
  const moduleBadges = {
    chatCenter: communicationSummary.chat_unread,
    myChat: communicationSummary.direct_unread,
    tickets: communicationSummary.open_tickets,
    myTickets: communicationSummary.open_tickets,
  };
  const activeKey = activeModules[active] ? active : Object.keys(activeModules)[0];
  const ActiveIcon = activeModules[activeKey]?.icon || Activity;
  const alertCount = dashboard?.summary?.alerts ?? management.summary?.duplicate_alerts ?? 0;
  const outstandingValue = billing.ledgerSummary?.total_outstanding ? usd(billing.ledgerSummary.total_outstanding) : '$0.00';
  const groupedKeys = new Set(sidebarGroups.flatMap((group) => group.keys));
  const visibleSidebarGroups = sidebarGroups
    .map((group) => ({
      ...group,
      items: group.keys.filter((key) => activeModules[key]).map((key) => [key, activeModules[key]]),
    }))
    .filter((group) => group.items.length);
  const ungroupedModules = Object.entries(activeModules).filter(([key]) => !groupedKeys.has(key));
  if (ungroupedModules.length) visibleSidebarGroups.push({ id: 'other', label: 'Other', items: ungroupedModules });
  const toggleSidebarCompact = () => {
    setIsSidebarCompact((current) => {
      const next = !current;
      localStorage.setItem('noc360_sidebar_compact', next ? '1' : '0');
      return next;
    });
  };
  const toggleSidebarGroup = (groupId) => {
    setCollapsedSidebarGroups((current) => {
      const next = { ...current, [groupId]: !current[groupId] };
      localStorage.setItem('noc360_sidebar_groups', JSON.stringify(next));
      return next;
    });
  };

  return (
    <div className={`app ${loading ? 'isSyncing' : ''} ${isSidebarCompact ? 'sidebarCompact' : ''}`}>
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
          <button type="button" className="sidebarToggle" onClick={toggleSidebarCompact} title={isSidebarCompact ? 'Expand sidebar' : 'Compact sidebar'}>
            {isSidebarCompact ? <PanelLeftOpen size={17} /> : <PanelLeftClose size={17} />}
          </button>
        </div>
        <nav className="sidebarNav">
          {visibleSidebarGroups.map((group, groupIndex) => {
            const hasActiveItem = group.items.some(([key]) => key === activeKey);
            const isCollapsed = Boolean(collapsedSidebarGroups[group.id]) && !hasActiveItem && !isSidebarCompact;
            const GroupIcon = isCollapsed ? ChevronRight : ChevronDown;
            return (
              <section className="navGroup" key={group.id}>
                <button type="button" className="navGroupToggle" onClick={() => toggleSidebarGroup(group.id)} title={group.label}>
                  <GroupIcon size={14} />
                  <span>{group.label}</span>
                  <em>{group.items.length}</em>
                </button>
                {!isCollapsed && (
                  <div className="navGroupItems">
                    {group.items.map(([key, item], index) => {
                      const Icon = item.icon;
                      return (
                        <button
                          type="button"
                          key={key}
                          className={`navItem ${activeKey === key ? 'active' : ''}`}
                          onClick={() => {
                            if (key === 'terminal') setTerminalHasMounted(true);
                            setActive(key);
                          }}
                          style={{ '--nav-index': (groupIndex * 10) + index }}
                          title={item.label}
                        >
                          <Icon size={18} />
                          <span>{item.label}</span>
                          {moduleBadges[key] > 0 && <b className="navBadge">{moduleBadges[key]}</b>}
                          <i className="navPulse" />
                        </button>
                      );
                    })}
                  </div>
                )}
              </section>
            );
          })}
        </nav>
      </aside>

      <main>
        <header className="topbar">
          <div className="topbarTitle">
            <span className="eyebrow">NOC360 Global VoIP Grid</span>
            <h1><ActiveIcon size={28} /> {activeModules[activeKey]?.label || 'No Access'}</h1>
          </div>
          <div className="topbarStatus">
            <div className={`topStatusItem ${loading ? 'syncing' : 'ready'}`}><Activity size={16} /><span>Sync</span><strong>{loading ? 'Syncing' : 'Ready'}</strong></div>
            <div className={alertCount > 0 ? 'topStatusItem warning' : 'topStatusItem'}><Bell size={16} /><span>Alerts</span><strong>{alertCount}</strong></div>
            {auth.user.role !== 'customer' && <div className="topStatusItem"><ReceiptText size={16} /><span>Outstanding</span><strong>{outstandingValue}</strong></div>}
          </div>
          <div className="topActions">
            <button className="themeTrigger" onClick={() => setThemeOpen(true)} title="Theme Settings"><Palette size={17} /></button>
            <button className="rolePill accountTrigger" onClick={() => setProfileOpen(true)} title="Account Settings">{auth.user.username || auth.user.role}</button>
            <button className="refreshButton" onClick={loadAll} title="Refresh live master data"><RefreshCcw size={18} /> Refresh</button>
            <button className="iconButton" onClick={logout} title="Logout"><LogOut size={18} /></button>
          </div>
        </header>

        {toast && <div className="toastSuccess appToast">{toast}</div>}
        {error && <div className="error"><AlertTriangle size={18} /> {error}</div>}
        {loading && <div className="loading">Syncing NOC inventory...</div>}

        {activeModules.terminal && (terminalHasMounted || activeKey === 'terminal') && (
          <section className={`pageShell persistentTerminalShell ${activeKey === 'terminal' ? 'isActive' : ''}`} aria-hidden={activeKey !== 'terminal'}>
            <PersistentTerminalCenterPage user={auth.user} visible={activeKey === 'terminal'} />
          </section>
        )}

        {activeKey !== 'terminal' && (
        <section className="pageShell" key={activeKey || 'no-access'}>
          {auth.user.role === 'customer' && activeKey === 'myDashboard' ? (
            <CustomerDashboard billing={billing} user={auth.user} />
          ) : auth.user.role === 'customer' && activeKey === 'myChat' ? (
            <ChatCenterPage user={auth.user} clients={data.clients} onSummaryRefresh={loadAll} />
          ) : auth.user.role === 'customer' && activeKey === 'myTickets' ? (
            <TicketsPage user={auth.user} clients={data.clients} onSummaryRefresh={loadAll} />
          ) : auth.user.role === 'customer' && activeKey === 'myBilling' ? (
            <BillingPage billing={billing} data={data} reload={loadAll} refreshBilling={refreshBillingData} user={auth.user} settings={settings} />
          ) : auth.user.role === 'customer' && activeKey === 'myCdr' ? (
            <CustomerCdrPage user={auth.user} />
          ) : auth.user.role === 'customer' && activeKey === 'myReports' ? (
            <ClientInvoiceLedgerView user={auth.user} pageKey="my_reports" title="My Reports" />
          ) : activeKey === 'dashboard' ? (
          <Dashboard dashboard={dashboard} data={data} user={auth.user} onDashboardUpdate={setDashboard} />
          ) : activeKey === 'management' ? (
          <ManagementPortal management={management} data={data} reload={loadAll} user={auth.user} />
          ) : activeKey === 'businessAi' ? (
            <BusinessAIPage data={data} />
          ) : activeKey === 'reports' ? (
            <ReportsPage data={data} user={auth.user} />
          ) : activeKey === 'chatCenter' ? (
            <ChatCenterPage user={auth.user} clients={data.clients} onSummaryRefresh={loadAll} />
          ) : activeKey === 'tickets' ? (
            <TicketsPage user={auth.user} clients={data.clients} onSummaryRefresh={loadAll} />
          ) : activeKey === 'webphone' ? (
            <WebphonePage user={auth.user} />
          ) : activeKey === 'asteriskSoundManager' ? (
            <AsteriskSoundManagerPage user={auth.user} />
          ) : activeKey === 'bareMetalOsInstaller' ? (
            <BareMetalOsInstallerPage user={auth.user} />
          ) : activeKey === 'updateCenter' ? (
            <UpdateCenterPage user={auth.user} />
          ) : activeKey === 'dangerZone' ? (
            <DangerZonePage user={auth.user} reload={loadAll} />
          ) : activeKey === 'vosDesktop' ? (
            <VOSDesktopPage rows={data.vosDesktop} user={auth.user} reload={loadAll} />
          ) : activeKey === 'billing' ? (
            <BillingPage billing={billing} data={data} reload={loadAll} refreshBilling={refreshBillingData} user={auth.user} settings={settings} />
          ) : activeKey === 'clients' ? (
          <ClientsPage clients={data.clients} reload={loadAll} user={auth.user} />
          ) : activeKey === 'userAccess' ? (
          <UserAccessPage users={data.users} clients={data.clients} reload={loadAll} user={auth.user} />
          ) : activeKey === 'activityLogs' ? (
            <ActivityLogsPage users={data.users} user={auth.user} />
          ) : activeKey ? (
            <CrudPage
              moduleKey={activeKey}
              config={modules[activeKey]}
              rows={data[activeKey]}
              rdps={data.rdps}
              mediaPortals={data.vos.filter(isMediaPortal)}
            clients={data.clients}
            rtngs={data.vos.filter((portal) => portal.portal_type?.toUpperCase().startsWith('RTNG'))}
            reload={loadAll}
            user={auth.user}
          />
          ) : (
            <div className="panel"><h2>No page access</h2><p className="muted">Ask an admin to assign page permissions.</p></div>
          )}
        </section>
        )}
      </main>
      {themeOpen && <ThemeSettingsModal selected={theme} customBackground={customBackground} onSelect={updateTheme} onCustomBackgroundChange={updateCustomBackground} onClose={() => setThemeOpen(false)} />}
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

function ThemeSettingsModal({ selected, customBackground, onSelect, onCustomBackgroundChange, onClose }) {
  const activeTheme = resolveTheme(selected);
  const backgroundInputRef = useRef(null);
  const [backgroundError, setBackgroundError] = useState('');
  const [isOptimizingBackground, setIsOptimizingBackground] = useState(false);
  const backgroundSettings = normalizeCustomBackground(customBackground);
  const selectTheme = (themeId) => {
    onSelect(themeId);
  };
  const updateBackground = (patch) => {
    setBackgroundError('');
    onCustomBackgroundChange({ ...backgroundSettings, ...patch });
  };
  const uploadBackground = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    setBackgroundError('');
    setIsOptimizingBackground(true);
    try {
      const image = await optimizeCustomBackground(file);
      onCustomBackgroundChange({ ...backgroundSettings, image });
    } catch (err) {
      setBackgroundError(err.message);
    } finally {
      setIsOptimizingBackground(false);
    }
  };
  const removeBackground = () => {
    setBackgroundError('');
    onCustomBackgroundChange({ ...backgroundSettings, image: '' });
  };

  return (
    <div className="modalBackdrop modal-overlay">
      <div className="modal modal-box themeModal">
        <div className="modalHeader themeHero">
          <div>
            <span className="eyebrow">Interface control</span>
            <h2>Theme Settings</h2>
            <p className="muted">Choose a global NOC360 visual mode. Changes apply instantly across every module.</p>
          </div>
          <button type="button" className="iconButton" onClick={onClose} title="Close"><X size={18} /></button>
        </div>
        <div className="themeGrid">
          {themeOptions.map((themeItem) => (
            <button
              type="button"
              key={themeItem.id}
              className={`themeCard ${activeTheme === themeItem.id && selected !== 'auto' ? 'selectedTheme' : ''}`}
              onClick={() => selectTheme(themeItem.id)}
            >
              <span className="themePreview" style={{ '--c0': themeItem.colors[0], '--c1': themeItem.colors[1], '--c2': themeItem.colors[2] }}>
                <i />
                <i />
                <i />
              </span>
              <strong>{themeItem.name}</strong>
              <small>{themeItem.description}</small>
            </button>
          ))}
          <button type="button" className={`themeCard autoThemeCard ${selected === 'auto' ? 'selectedTheme' : ''}`} onClick={() => selectTheme('auto')}>
            <span className="themePreview" style={{ '--c0': '#f7fafc', '--c1': '#00e5ff', '--c2': '#06080f' }}>
              <i />
              <i />
              <i />
            </span>
            <strong>Auto Theme</strong>
            <small>Light by day, Executive NOC at night.</small>
          </button>
        </div>
        <div className="customBackgroundPanel">
          <div>
            <span className="eyebrow">Custom Background</span>
            <h3>Custom Background</h3>
            <p className="muted">Use a local image behind the app shell. Images are compressed and stored in this browser only.</p>
          </div>
          <div className={`customBackgroundPreview ${backgroundSettings.image ? 'hasImage' : ''}`} style={{ backgroundImage: backgroundSettings.image ? `url(${backgroundSettings.image})` : undefined }}>
            {!backgroundSettings.image && <span>No custom image</span>}
          </div>
          <div className="customBackgroundControls">
            <input ref={backgroundInputRef} type="file" accept="image/*" onChange={uploadBackground} hidden />
            <button type="button" onClick={() => backgroundInputRef.current?.click()}><Upload size={16} /> {isOptimizingBackground ? 'Optimizing...' : 'Upload Image'}</button>
            <button type="button" onClick={removeBackground} disabled={!backgroundSettings.image}><Trash2 size={16} /> Remove Image</button>
            <label className="fieldLabel">Opacity {Math.round(backgroundSettings.opacity)}%
              <input type="range" min="0" max="100" value={backgroundSettings.opacity} onChange={(event) => updateBackground({ opacity: Number(event.target.value) })} />
            </label>
            <label className="fieldLabel">Blur {Math.round(backgroundSettings.blur)}px
              <input type="range" min="0" max="20" value={backgroundSettings.blur} onChange={(event) => updateBackground({ blur: Number(event.target.value) })} />
            </label>
            <label className="fieldLabel">Overlay Color
              <input type="color" value={backgroundSettings.overlayColor} onChange={(event) => updateBackground({ overlayColor: event.target.value })} />
            </label>
          </div>
          {backgroundError && <span className="formError">{backgroundError}</span>}
        </div>
        <div className="modalActions themeActions">
          <span className="muted">Active: {selected === 'auto' ? `Auto (${themeOptions.find((item) => item.id === activeTheme)?.name})` : themeOptions.find((item) => item.id === activeTheme)?.name}</span>
          <button type="button" className="primary" onClick={onClose}>Done</button>
        </div>
      </div>
    </div>
  );
}

function DangerZonePage({ user, reload }) {
  const emptyOptions = {
    billing: false,
    clients: false,
    vos: false,
    chat_tickets: false,
    webphone: false,
    activity_logs: false,
    full_factory_reset: false,
  };
  const [options, setOptions] = useState(emptyOptions);
  const [modalOpen, setModalOpen] = useState(false);
  const [confirmText, setConfirmText] = useState('');
  const [adminPassword, setAdminPassword] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const isSuperAdmin = user?.role === 'admin' && user?.username === 'admin';
  const selectedCount = Object.entries(options).filter(([key, value]) => key !== 'full_factory_reset' && value).length;
  const fullOptions = options.full_factory_reset
    ? { ...options, billing: true, clients: true, vos: true, chat_tickets: true, webphone: true }
    : options;

  const toggleOption = (key) => {
    setResult(null);
    setOptions((current) => {
      const next = { ...current, [key]: !current[key] };
      if (key === 'full_factory_reset' && !current.full_factory_reset) {
        return { ...next, billing: true, clients: true, vos: true, chat_tickets: true, webphone: true };
      }
      return next;
    });
  };

  const submitClear = async (event) => {
    event.preventDefault();
    setError('');
    setResult(null);
    if (confirmText !== 'CLEAR NOC360 DATA') {
      setError('Confirmation text does not match.');
      return;
    }
    if (!adminPassword) {
      setError('Admin password is required.');
      return;
    }
    setBusy(true);
    try {
      const response = await request('/admin/danger-zone/clear-data', {
        method: 'POST',
        body: JSON.stringify({ confirm_text: confirmText, admin_password: adminPassword, options: fullOptions }),
      });
      setResult(response);
      setOptions(emptyOptions);
      setConfirmText('');
      setAdminPassword('');
      setModalOpen(false);
      await reload?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  if (!isSuperAdmin) {
    return <div className="panel"><h2>Danger Zone</h2><p className="muted">Super Admin access required.</p></div>;
  }

  const optionRows = [
    ['billing', 'Clear Billing Data', 'Deletes ledger entries, billing charges, and data cost rows.'],
    ['clients', 'Clear Client Data', 'Deletes clients, customer users, client access, and linked client-owned records.'],
    ['vos', 'Clear VOS/Routing/RDP Data', 'Deletes VOS portals, media nodes, routing gateways, and dialer clusters.'],
    ['chat_tickets', 'Clear Chat/Tickets', 'Deletes direct chat, group chat, tickets, and ticket messages.'],
    ['webphone', 'Clear Webphone Data', 'Deletes Webphone profiles and call logs.'],
    ['activity_logs', 'Clear Activity Logs', 'Deletes audit logs. A new reset audit entry is created after clearing.'],
    ['full_factory_reset', 'Full Factory Reset', 'Selects all operational data areas except Activity Logs unless checked.'],
  ];

  return (
    <section className="dangerZonePage">
      <div className="panel dangerHero">
        <span className="eyebrow">Settings / Danger Zone</span>
        <h2><AlertTriangle size={24} /> Database Clear / Factory Reset</h2>
        <p>This rare-use tool clears selected operational data only after exact confirmation, super admin password verification, and a successful automatic database backup.</p>
        <strong>It never runs during install or update, never drops tables, and keeps the admin login and system permissions intact.</strong>
      </div>

      {error && <div className="error"><AlertTriangle size={18} /> {error}</div>}
      {result && (
        <div className="toastSuccess dangerResult">
          <strong>Selected data cleared after backup.</strong>
          <span>Backup: {result.backup_file}</span>
          <small>Deleted rows: {Object.entries(result.deleted_counts || {}).map(([key, value]) => `${key}: ${value}`).join(', ') || '0'}</small>
        </div>
      )}

      <div className="panel dangerPanel">
        <div className="sectionHeader">
          <div>
            <span className="eyebrow">Manual destructive action</span>
            <h2>Clear Selected Data</h2>
          </div>
          <span className="typeBadge">{selectedCount || (options.full_factory_reset ? 5 : 0)} selected</span>
        </div>
        <div className="dangerOptionsGrid">
          {optionRows.map(([key, label, description]) => (
            <label key={key} className={`dangerOption ${key === 'full_factory_reset' ? 'factoryOption' : ''}`}>
              <input type="checkbox" checked={Boolean(options[key])} onChange={() => toggleOption(key)} />
              <span>
                <strong>{label}</strong>
                <small>{description}</small>
              </span>
            </label>
          ))}
        </div>
        <div className="dangerNotice">
          <AlertTriangle size={18} />
          <span>Backup is created first at <code>backend/backups/factory_reset_before_YYYYMMDD_HHMM.db</code>. If backup fails, nothing is deleted.</span>
        </div>
        <button className="danger dangerClearButton" disabled={!Object.values(fullOptions).some(Boolean)} onClick={() => { setError(''); setModalOpen(true); }}>
          Clear Selected Data
        </button>
      </div>

      {modalOpen && (
        <div className="modalBackdrop modal-overlay">
          <form className="modal modal-box dangerConfirmModal" onSubmit={submitClear}>
            <div className="modalHeader">
              <div>
                <span className="eyebrow">Final confirmation</span>
                <h2><AlertTriangle size={22} /> Clear NOC360 Data</h2>
              </div>
              <button type="button" className="iconButton" onClick={() => setModalOpen(false)}><X size={18} /></button>
            </div>
            <div className="dangerFinalWarning">
              This will delete selected operational data after creating a backup. Type the exact phrase and enter the admin password.
            </div>
            <label>
              <span>Type exactly: CLEAR NOC360 DATA</span>
              <input value={confirmText} onChange={(event) => setConfirmText(event.target.value)} placeholder="CLEAR NOC360 DATA" autoFocus />
            </label>
            <label>
              <span>Admin Password</span>
              <input type="password" value={adminPassword} onChange={(event) => setAdminPassword(event.target.value)} autoComplete="current-password" />
            </label>
            {error && <div className="error"><AlertTriangle size={18} /> {error}</div>}
            <div className="modalActions">
              <button type="button" onClick={() => setModalOpen(false)}>Cancel</button>
              <button className="danger" disabled={busy}>{busy ? 'Backing up and clearing...' : 'I Understand, Clear Data'}</button>
            </div>
          </form>
        </div>
      )}
    </section>
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

function VOSDesktopDetailsModal({ details, revealed, onToggleReveal, onClose, onCopy, onOpenWeb, onOpenAntiHack }) {
  const [copyStatus, setCopyStatus] = useState('');
  const valueOrDash = (value) => (value === undefined || value === null || value === '' ? '-' : value);
  const secretValue = (value) => {
    if (value === undefined || value === null || value === '') return '-';
    return revealed ? value : '************';
  };
  const copyValue = async (value, label) => {
    if (value === undefined || value === null || value === '') return;
    await onCopy(String(value));
    setCopyStatus(`${label} copied`);
    window.setTimeout(() => setCopyStatus(''), 1800);
  };
  const allDetails = [
    ['VOS Name / Portal Type', details.vos_name || details.portal_type || ''],
    ['VOS Version', details.vos_version || ''],
    ['Portal Type', details.portal_type || ''],
    ['Server IP', details.server_ip || ''],
    ['Web Panel URL', details.web_panel_url || ''],
    ['Username', details.username || ''],
    ['Password', details.password || ''],
    ['Anti-Hack URL', details.anti_hack_url || ''],
    ['Anti-Hack Password / PIN', details.anti_hack_password || ''],
    ['UUID', details.uuid || ''],
    ['Notes', details.notes || details.vos_notes || ''],
    ['Status', details.status || ''],
  ].map(([label, value]) => `${label}: ${value}`).join('\n');
  const fields = [
    ['VOS Name / Portal Type', valueOrDash(details.vos_name || details.portal_type)],
    ['VOS Version', valueOrDash(details.vos_version)],
    ['Portal Type', valueOrDash(details.portal_type)],
    ['Server IP', valueOrDash(details.server_ip)],
    ['Web Panel URL', valueOrDash(details.web_panel_url), 'openWeb'],
    ['Username', valueOrDash(details.username), 'copyUsername'],
    ['Password', secretValue(details.password), 'copyPassword', true],
    ['Anti-Hack URL', valueOrDash(details.anti_hack_url), 'openAntiHack'],
    ['Anti-Hack Password / PIN', secretValue(details.anti_hack_password), 'copyPin', true],
    ['UUID', secretValue(details.uuid), 'copyUuid', true],
    ['Notes', valueOrDash(details.notes || details.vos_notes)],
    ['Status', valueOrDash(details.status)],
  ];
  const actionFor = {
    openWeb: <button type="button" onClick={onOpenWeb} disabled={!details.web_panel_url && !details.server_ip}><ExternalLink size={14} /> Open</button>,
    openAntiHack: <button type="button" onClick={onOpenAntiHack} disabled={!details.anti_hack_url}><ExternalLink size={14} /> Open</button>,
    copyUsername: <button type="button" onClick={() => copyValue(details.username, 'Username')} disabled={!details.username}><Copy size={14} /> Copy</button>,
    copyPassword: <button type="button" onClick={() => copyValue(details.password, 'Password')} disabled={!details.password}><Copy size={14} /> Copy</button>,
    copyPin: <button type="button" onClick={() => copyValue(details.anti_hack_password, 'Anti-Hack PIN')} disabled={!details.anti_hack_password}><Copy size={14} /> Copy</button>,
    copyUuid: <button type="button" onClick={() => copyValue(details.uuid, 'UUID')} disabled={!details.uuid}><Copy size={14} /> Copy</button>,
  };

  return (
    <div className="modalBackdrop modal-overlay">
      <div className="modal modal-box vosDetailsModal">
        <div className="modalHeader vosDetailHeader">
          <div>
            <span className="eyebrow">Secure VOS credential vault</span>
            <h2>{details.vos_name || details.portal_type || 'VOS Portal'} Details</h2>
            <p className="muted">Full record from VOS Portal Master. Sensitive values stay masked until revealed.</p>
          </div>
          <div className="vosDetailHeaderActions">
            <button type="button" onClick={onToggleReveal}>{revealed ? <EyeOff size={16} /> : <Eye size={16} />} {revealed ? 'Hide Secrets' : 'Reveal Secrets'}</button>
            <button type="button" className="iconButton" onClick={onClose} title="Close"><X size={18} /></button>
          </div>
        </div>

        <div className="vosDetailHero">
          <div>
            <span className="eyebrow">Portal</span>
            <strong>{details.portal_type || '-'}</strong>
          </div>
          <div>
            <span className="eyebrow">Server IP</span>
            <strong>{details.server_ip || '-'}</strong>
          </div>
          <div>
            <span className="eyebrow">Status</span>
            <StatusPill value={details.status} />
          </div>
        </div>

        <div className="vosDetailGrid">
          {fields.map(([label, value, action, secret]) => (
            <div className={`vosDetailItem ${secret ? 'secretItem' : ''}`} key={label}>
              <span>{label}</span>
              <div className="vosDetailValue">
                <code className={secret ? 'secretValue' : ''}>{value}</code>
                {action && actionFor[action]}
              </div>
            </div>
          ))}
        </div>

        <div className="modalActions vosDetailActions">
          <button type="button" onClick={() => copyValue(details.username, 'Username')} disabled={!details.username}><Copy size={15} /> Copy Username</button>
          <button type="button" onClick={() => copyValue(details.password, 'Password')} disabled={!details.password}><Copy size={15} /> Copy Password</button>
          <button type="button" onClick={() => copyValue(details.anti_hack_password, 'Anti-Hack PIN')} disabled={!details.anti_hack_password}><Copy size={15} /> Copy Anti-Hack PIN</button>
          <button type="button" onClick={() => copyValue(details.uuid, 'UUID')} disabled={!details.uuid}><Copy size={15} /> Copy UUID</button>
          <button type="button" onClick={() => copyValue(allDetails, 'All VOS details')}><Copy size={15} /> Copy All Details</button>
          <button type="button" onClick={onOpenWeb} disabled={!details.web_panel_url && !details.server_ip}><ExternalLink size={15} /> Open Web Panel</button>
          <button type="button" onClick={onOpenAntiHack} disabled={!details.anti_hack_url}><ExternalLink size={15} /> Open Anti-Hack URL</button>
        </div>
        {copyStatus && <div className="copyStatus">{copyStatus}</div>}
      </div>
    </div>
  );
}

function VOSDesktopPage({ rows, user, reload }) {
  const canUseLauncher = canDo(user, 'vos_desktop_launcher', 'can_export') || user?.role === 'admin';
  const canEdit = canDo(user, 'vos_desktop_launcher', 'can_edit') || user?.role === 'admin';
  const [query, setQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('All');
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
  const [detailsModal, setDetailsModal] = useState(null);
  const [detailsRevealed, setDetailsRevealed] = useState(false);
  const [editing, setEditing] = useState(null);
  const [agentStatus, setAgentStatus] = useState({ checking: true, running: false, message: 'Checking launcher...' });
  const [agentVersions, setAgentVersions] = useState([]);
  const [autoLogin, setAutoLogin] = useState(() => localStorage.getItem('vos_auto_login') !== 'false');
  const [message, setMessage] = useState('');
  const [launchDetails, setLaunchDetails] = useState([]);
  const [error, setError] = useState('');

  const launcherVersions = agentVersions.length ? agentVersions : [];
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

  const refreshAgent = async () => {
    setAgentStatus({ checking: true, running: false, message: 'Checking launcher...' });
    try {
      const health = await fetch('http://127.0.0.1:5055/health', { method: 'GET' });
      if (!health.ok) throw new Error('Launcher health check failed');
      const versionsResponse = await fetch('http://127.0.0.1:5055/versions', { method: 'GET' });
      if (!versionsResponse.ok) throw new Error('Unable to load launcher versions');
      const versionData = await versionsResponse.json();
      const versions = Array.isArray(versionData.versions) ? versionData.versions : [];
      setAgentVersions(versions);
      setAgentStatus({ checking: false, running: true, message: versions.length ? `${versions.length} VOS version(s) detected` : 'Running, but no VOS versions detected' });
      setError('');
    } catch {
      setAgentVersions([]);
      setAgentStatus({ checking: false, running: false, message: 'Not Installed / Not Running' });
    }
  };

  useEffect(() => {
    refreshAgent();
  }, []);

  const downloadLauncher = async () => {
    try {
      const token = localStorage.getItem('noc360_token');
      const response = await fetch(`${API_BASE_URL}/vos-desktop/download-launcher`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail.detail || 'Launcher download failed');
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'noc360-local-launcher.zip';
      link.click();
      URL.revokeObjectURL(url);
      const downloadMessage = 'Download complete. Run NOC360 Launcher once on this PC. After that, Launch buttons will open VOS automatically.';
      setMessage(downloadMessage);
      window.alert(downloadMessage);
      setError('');
    } catch (err) {
      setError(err.message);
    }
  };

  const selectedVersionFor = (row) => {
    const saved = selectedVersions[row.id];
    if (launcherVersions.some((version) => version.name === saved)) return saved;
    return launcherVersions[0]?.name || '';
  };

  const setSelectedVersion = (row, version) => {
    const next = { ...selectedVersions, [row.id]: version };
    setSelectedVersions(next);
    localStorage.setItem('vos_launcher_selected_versions', JSON.stringify(next));
  };

  const setAutoLoginPreference = (value) => {
    setAutoLogin(value);
    localStorage.setItem('vos_auto_login', value ? 'true' : 'false');
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

  const openDetails = async (row) => {
    if (!canUseLauncher) return;
    try {
      const details = await request(`/vos-desktop/${row.id}/details`);
      setDetailsModal(details);
      setDetailsRevealed(false);
      setError('');
    } catch (err) {
      setError(err.message);
    }
  };

  const launchDesktop = async (row) => {
    if (!canUseLauncher) return;
    const versionName = selectedVersionFor(row);
    if (!agentStatus.running) {
      setError('NOC360 Launcher not running. Please start local launcher.');
      return;
    }
    if (!versionName) {
      setError('No local VOS version detected. Edit C:\\NOC360\\config.json, then click Refresh Agent.');
      return;
    }
    try {
      const login = await fetchLogin(row);
      setMessage(autoLogin ? 'Auto-login started...' : 'Launching VOS. Login will be copied to clipboard.');
      setLaunchDetails([]);
      const response = await fetch('http://127.0.0.1:5055/launch-vos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          version_name: versionName,
          server_ip: login.server || row.server_ip || '',
          username: login.username || row.username || '',
          password: login.password || '',
          anti_hack_url: login.anti_hack_url || row.anti_hack_url || '',
          anti_hack_password: login.anti_hack_password || '',
          system_tag: '',
          auto_login: autoLogin,
          focus_strategy: 'vos_window',
          login_wait_seconds: 5,
          anti_hack_use_ctrl_l: false,
          anti_hack_press_escape: true,
          anti_hack_tab_count_to_pin: 1,
        }),
      });
      const result = await response.json().catch(() => ({}));
      setLaunchDetails(Array.isArray(result.details) ? result.details : []);
      if (!response.ok) {
        throw new Error(result.message || result.error || result.detail || 'Launcher command failed');
      }
      markLastUsed(row);
      request('/activity-logs/track', {
        method: 'POST',
        body: JSON.stringify({
          action: 'launch_desktop',
          module: 'vos_desktop',
          record_type: 'VOSPortal',
          record_id: row.id,
          description: `Local agent launch requested for ${row.vos_name} using ${versionName}`,
        }),
      }).catch(() => {});
      setMessage(result.message || `VOS launched for ${row.vos_name}. Login copied to clipboard.`);
      setError('');
    } catch (err) {
      const message = err?.message || '';
      setError(message.includes('Failed to fetch') ? 'NOC360 Launcher not running. Please start local launcher.' : message);
    }
  };

  const openWhitelist = (row) => {
    const url = row.anti_hack_url || (row.server_ip ? `http://${row.server_ip}:8989/anti-atck` : '');
    if (!url) {
      setError('Anti-hack URL is missing');
      return;
    }
    window.open(url, '_blank', 'noopener,noreferrer');
    request('/activity-logs/track', {
      method: 'POST',
      body: JSON.stringify({ action: 'open_anti_hack', module: 'vos_desktop', record_type: 'VOSPortal', record_id: row.id, description: `Anti-hack URL opened for ${row.vos_name}` }),
    }).catch(() => {});
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
    request('/activity-logs/track', {
      method: 'POST',
      body: JSON.stringify({ action: 'open_web_panel', module: 'vos_desktop', record_type: 'VOSPortal', record_id: row.id, description: `Web panel opened for ${row.vos_name}` }),
    }).catch(() => {});
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
          <h2><Play size={20} /> Local agent launch from VOS Portal Master</h2>
          <p className="muted">RDP, RTNG, DID, and every other VOS portal launch through the NOC360 Local Launcher Agent running on this PC.</p>
        </div>
        <div className="launcherStats">
          <span>{rows.length} VOS records</span>
          <span>{favorites.length} favorites</span>
          <span>{Object.keys(lastUsed).length} launched</span>
        </div>
      </div>

      <div className="panel launcherAgentPanel">
        <div>
          <span className="eyebrow">Local Agent</span>
          <h2>127.0.0.1:5055 Launcher</h2>
          <p className="muted">Install and run the NOC360 Launcher once on this PC. Local VOS app paths stay inside <code>C:\NOC360\config.json</code>.</p>
        </div>
        <div className="launcherAgentControls">
          <span className={`agentStatus ${agentStatus.running ? 'running' : 'offline'}`}>{agentStatus.checking ? 'CHECKING' : agentStatus.running ? 'ONLINE' : 'OFFLINE'} - {agentStatus.message}</span>
          <label className="autoLoginToggle"><span>Auto Login</span><input type="checkbox" checked={autoLogin} onChange={(event) => setAutoLoginPreference(event.target.checked)} /></label>
          <button onClick={downloadLauncher}><Download size={16} /> Download NOC360 Launcher</button>
          <button onClick={refreshAgent}><RefreshCcw size={16} /> Refresh Agent</button>
        </div>
      </div>

      {message && <div className="toastSuccess">{message}</div>}
      {launchDetails.length > 0 && (
        <div className="panel launcherDetails">
          <h3>Launcher Details</h3>
          <ul>{launchDetails.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul>
        </div>
      )}
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
                        <select value={selectedVersionFor(row)} onChange={(event) => setSelectedVersion(row, event.target.value)} disabled={!agentVersions.length}>
                          {!agentVersions.length && <option value="">No versions detected</option>}
                          {agentVersions.map((version) => <option key={version.name} value={version.name}>{version.name}</option>)}
                        </select>
                        {agentVersions.find((version) => version.name === selectedVersionFor(row))?.args_template && <small className="muted">CLI args enabled</small>}
                      </td>
                      <td className="actions vosActions">
                        {canUseLauncher && <button className="primary" onClick={() => launchDesktop(row)}><Play size={15} /> Launch Desktop Client</button>}
                        <button onClick={() => openWhitelist(row)}>Whitelist IP</button>
                        {canUseLauncher && <button onClick={() => copyLogin(row)}><Copy size={15} /> Copy Login</button>}
                        <button onClick={() => openWebPanel(row)}><ExternalLink size={15} /> Open Web Panel</button>
                        {canUseLauncher && <button onClick={() => openDetails(row)}><Eye size={15} /> Show Password</button>}
                        {canEdit && <button className="iconButton" onClick={() => setEditing(row)} title="Edit"><Edit3 size={16} /></button>}
                      </td>
                    </tr>
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
      {!groupedRows.length && <div className="panel muted">No VOS desktop records found.</div>}
      {detailsModal && (
        <VOSDesktopDetailsModal
          details={detailsModal}
          revealed={detailsRevealed}
          onToggleReveal={() => setDetailsRevealed((current) => !current)}
          onClose={() => setDetailsModal(null)}
          onCopy={copyText}
          onOpenWeb={() => window.open(detailsModal.web_panel_url || `http://${detailsModal.server_ip}`, '_blank', 'noopener,noreferrer')}
          onOpenAntiHack={() => window.open(detailsModal.anti_hack_url || '', '_blank', 'noopener,noreferrer')}
        />
      )}
      {editing && <VOSDesktopEditModal record={editing} onClose={() => setEditing(null)} onSave={saveEdit} />}
    </section>
  );
}

function ManagementPortal({ management, data, reload, user }) {
  const rtngs = data.vos.filter((portal) => portal.portal_type?.toUpperCase().startsWith('RTNG'));
  const mediaPortals = data.vos.filter(isMediaPortal);
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
              <RoutingMediaRow key={row.gateway_name} row={row} routingRows={management.routing} mediaPortals={mediaPortals} rtngs={rtngs} saving={saving} onSave={saveManagement} canEdit={canEdit} />
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
  if (filters.type) params.set('type', filters.type);
  return params.toString() ? `?${params}` : '';
}

function activityQuery(filters) {
  const params = new URLSearchParams();
  if (filters.date_from) params.set('date_from', filters.date_from);
  if (filters.date_to) params.set('date_to', filters.date_to);
  if (filters.username) params.set('username', filters.username);
  if (filters.role) params.set('role', filters.role);
  if (filters.module) params.set('module', filters.module);
  if (filters.action) params.set('action', filters.action);
  if (filters.search) params.set('search', filters.search);
  params.set('limit', '1000');
  return `?${params}`;
}

function formatLogValue(value) {
  if (!value) return '-';
  try {
    return JSON.stringify(JSON.parse(value), null, 2);
  } catch {
    return String(value);
  }
}

function activityLocation(row) {
  const parts = [row.country, row.city].filter(Boolean);
  const location = parts.length ? parts.join(', ') : 'Unknown';
  return row.isp ? `${location} - ${row.isp}` : location;
}

function ActivityLogsPage({ users, user }) {
  const [filters, setFilters] = useState({ date_from: '', date_to: '', username: '', role: '', module: '', action: '', search: '' });
  const [logs, setLogs] = useState([]);
  const [summary, setSummary] = useState({});
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const canExport = canDo(user, 'activity_logs', 'can_export');
  const modules = ['auth', 'clients', 'billing', 'reports', 'management_portal', 'vos_portals', 'vos_desktop', 'dialer_clusters', 'routing_gateways', 'user_access', 'chat', 'group_chat', 'tickets', 'webphone'];
  const actions = ['login_success', 'login_failed', 'logout', 'create', 'update', 'delete', 'create_ledger', 'update_ledger', 'delete_ledger', 'reset_password', 'update_permissions', 'update_client_access', 'copy_credentials', 'launch_desktop', 'open_anti_hack', 'export_report', 'chat_sent', 'group_created', 'group_message_sent', 'ticket_created', 'ticket_updated', 'ticket_status_changed', 'ticket_message_sent', 'webphone_call_test'];

  const loadLogs = async () => {
    setLoading(true);
    setError('');
    try {
      const [logRows, logSummary] = await Promise.all([
        request(`/activity-logs${activityQuery(filters)}`),
        request('/activity-logs/summary'),
      ]);
      setLogs(logRows);
      setSummary(logSummary);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLogs();
  }, []);

  const setFilter = (key, value) => setFilters((current) => ({ ...current, [key]: value }));
  const cards = [
    ['Total Activities Today', summary.total_today || 0],
    ['Login Attempts', summary.login_attempts || 0],
    ['Billing Changes', summary.billing_changes || 0],
    ['User Access Changes', summary.user_access_changes || 0],
    ['VOS Credential Actions', summary.vos_credential_actions || 0],
  ];

  return (
    <section className="page activityLogsPage">
      <div className="cards managementCards">
        {cards.map(([label, value]) => <div className="metric" key={label}><span>{label}</span><strong>{value}</strong></div>)}
      </div>
      <div className="reportFilters">
        <label>From Date<input type="date" value={filters.date_from} onChange={(event) => setFilter('date_from', event.target.value)} /></label>
        <label>To Date<input type="date" value={filters.date_to} onChange={(event) => setFilter('date_to', event.target.value)} /></label>
        <label>User<select value={filters.username} onChange={(event) => setFilter('username', event.target.value)}><option value="">All Users</option>{users.map((item) => <option key={item.id} value={item.username}>{item.username}</option>)}</select></label>
        <label>Role<select value={filters.role} onChange={(event) => setFilter('role', event.target.value)}><option value="">All Roles</option>{['admin', 'noc_user', 'viewer', 'customer'].map((role) => <option key={role}>{role}</option>)}</select></label>
        <label>Module<select value={filters.module} onChange={(event) => setFilter('module', event.target.value)}><option value="">All Modules</option>{modules.map((module) => <option key={module}>{module}</option>)}</select></label>
        <label>Action<select value={filters.action} onChange={(event) => setFilter('action', event.target.value)}><option value="">All Actions</option>{actions.map((action) => <option key={action}>{action}</option>)}</select></label>
        <label>Search Description<input value={filters.search} onChange={(event) => setFilter('search', event.target.value)} placeholder="Search activity..." /></label>
        <button className="primary" onClick={loadLogs}>Run</button>
        {canExport && <button onClick={() => exportRows('activity-logs.csv', logs)}><Download size={16} /> Export CSV</button>}
      </div>
      {error && <div className="error"><AlertTriangle size={18} /> {error}</div>}
      {loading && <div className="loading">Loading activity trail...</div>}
      <div className="tableWrap">
        <table>
          <thead><tr><th>Date/Time</th><th>User</th><th>Role</th><th>Module</th><th>Action</th><th>Description</th><th>IP</th><th>Location</th><th>ISP</th><th>Details</th></tr></thead>
          <tbody>{logs.map((row) => (
            <tr key={row.id}>
              <td>{row.created_at ? new Date(row.created_at).toLocaleString() : '-'}</td>
              <td>{row.username || '-'}</td>
              <td>{row.role || '-'}</td>
              <td>{row.module}</td>
              <td>{row.action}</td>
              <td>{row.description || '-'}</td>
              <td>{row.ip_address || '-'}</td>
              <td>{[row.country, row.city].filter(Boolean).join(', ') || 'Unknown'}</td>
              <td>{row.isp || 'Unknown'}</td>
              <td><button onClick={() => setSelected(row)}>Details</button></td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      {selected && (
        <div className="modalBackdrop modal-overlay">
          <div className="modal modal-box activityDetailModal">
            <div className="modalHeader"><h2>Activity Details</h2><button className="iconButton" onClick={() => setSelected(null)}><X size={18} /></button></div>
            <div className="activityDetailGrid">
              <p><strong>User:</strong> {selected.username || '-'}</p>
              <p><strong>Role:</strong> {selected.role || '-'}</p>
              <p><strong>Module:</strong> {selected.module}</p>
              <p><strong>Action:</strong> {selected.action}</p>
              <p><strong>Record:</strong> {selected.record_type || '-'} #{selected.record_id || '-'}</p>
              <p><strong>IP:</strong> {selected.ip_address || '-'}</p>
              <p><strong>Location:</strong> {activityLocation(selected)}</p>
              <p><strong>ISP:</strong> {selected.isp || 'Unknown'}</p>
              <p className="wide"><strong>User Agent:</strong> {selected.user_agent || '-'}</p>
              <div className="wide"><strong>Old Value</strong><pre>{formatLogValue(selected.old_value)}</pre></div>
              <div className="wide"><strong>New Value</strong><pre>{formatLogValue(selected.new_value)}</pre></div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function ChatCenterPage({ user, clients, onSummaryRefresh }) {
  const [rooms, setRooms] = useState([]);
  const [selectedRoom, setSelectedRoom] = useState(null);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState('');
  const [groups, setGroups] = useState([]);
  const [selectedGroup, setSelectedGroup] = useState(null);
  const [groupMessages, setGroupMessages] = useState([]);
  const [groupDraft, setGroupDraft] = useState('');
  const [chatUsers, setChatUsers] = useState([]);
  const [groupForm, setGroupForm] = useState({ name: '', member_ids: [] });
  const [error, setError] = useState('');
  const isCustomer = user.role === 'customer';
  const canGroup = !isCustomer && canDo(user, 'group_chat');
  const canCreateGroup = !isCustomer && canDo(user, 'group_chat', 'can_create');

  const loadRooms = async () => {
    setError('');
    const next = await request('/chat/rooms');
    setRooms(next);
    setSelectedRoom((current) => next.find((room) => room.id === current?.id) || next[0] || null);
  };

  const loadGroups = async () => {
    if (!canGroup) return;
    const [nextGroups, users] = await Promise.all([request('/chat/groups'), request('/chat/users')]);
    setGroups(nextGroups);
    setChatUsers(users);
    setSelectedGroup((current) => nextGroups.find((group) => group.id === current?.id) || nextGroups[0] || null);
  };

  useEffect(() => {
    loadRooms().catch((err) => setError(err.message));
    loadGroups().catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedRoom?.id) {
      setMessages([]);
      return;
    }
    request(`/chat/rooms/${selectedRoom.id}/messages`)
      .then((rows) => {
        setMessages(rows);
        onSummaryRefresh?.();
      })
      .catch((err) => setError(err.message));
  }, [selectedRoom?.id]);

  useEffect(() => {
    if (!selectedGroup?.id) {
      setGroupMessages([]);
      return;
    }
    request(`/chat/groups/${selectedGroup.id}/messages`)
      .then(setGroupMessages)
      .catch((err) => setError(err.message));
  }, [selectedGroup?.id]);

  const sendMessage = async () => {
    if (!draft.trim() || !selectedRoom) return;
    const row = await request(`/chat/rooms/${selectedRoom.id}/messages`, { method: 'POST', body: JSON.stringify({ message: draft }) });
    setMessages((current) => [...current, row]);
    setDraft('');
    await loadRooms();
    onSummaryRefresh?.();
  };

  const createGroup = async () => {
    if (!groupForm.name.trim()) return;
    const group = await request('/chat/groups', { method: 'POST', body: JSON.stringify({ name: groupForm.name, member_ids: groupForm.member_ids.map(Number) }) });
    setGroupForm({ name: '', member_ids: [] });
    await loadGroups();
    setSelectedGroup(group);
  };

  const sendGroupMessage = async () => {
    if (!groupDraft.trim() || !selectedGroup) return;
    const row = await request(`/chat/groups/${selectedGroup.id}/messages`, { method: 'POST', body: JSON.stringify({ message: groupDraft }) });
    setGroupMessages((current) => [...current, row]);
    setGroupDraft('');
    await loadGroups();
  };

  const roomTitle = isCustomer ? 'My NOC Chat' : 'Client Chat';

  return (
    <section className="communicationPage">
      {error && <div className="error"><AlertTriangle size={18} /> {error}</div>}
      <div className={`chatGrid ${isCustomer ? 'singleChatGrid' : ''}`}>
        {!isCustomer && (
          <aside className="chatList panel">
            <div className="chatListHeader">
              <h2>{roomTitle}</h2>
              <button onClick={() => loadRooms().catch((err) => setError(err.message))}>Refresh</button>
            </div>
            {rooms.length === 0 && (
              <div className="chatEmptyState">
                <strong>No clients found</strong>
                <small>Chat rooms are created from the Clients master. Add a client, then refresh.</small>
              </div>
            )}
            {rooms.map((room) => (
              <button key={room.id} className={selectedRoom?.id === room.id ? 'activeChat' : ''} onClick={() => setSelectedRoom(room)}>
                <span>{room.client_name || `Client #${room.client_id}`}</span>
                {room.unread_count > 0 && <b>{room.unread_count}</b>}
                <small>{room.last_message || 'No messages yet'}</small>
              </button>
            ))}
          </aside>
        )}
        <div className="chatWindow panel">
          <div className="chatHeader">
            <div><span className="eyebrow">{roomTitle}</span><h2>{selectedRoom?.client_name || user.client_name || 'Select Client'}</h2></div>
            <span className="typeBadge">{messages.length} messages</span>
          </div>
          <div className="messageStream">
            {!selectedRoom && <p className="muted">{isCustomer ? 'No chat room is linked to your customer account.' : 'Select a client from the left to open chat.'}</p>}
            {selectedRoom && messages.length === 0 && <p className="muted">No messages yet. Start the conversation.</p>}
            {messages.map((message) => (
              <div key={message.id} className={`messageBubble ${message.sender_id === user.id ? 'mine' : 'theirs'}`}>
                <strong>{message.sender_name || message.sender_role}</strong>
                <p>{message.message}</p>
                <small>{message.created_at ? new Date(message.created_at).toLocaleString() : ''}{message.is_read ? ' • read' : ''}</small>
              </div>
            ))}
          </div>
          <div className="chatComposer">
            <textarea disabled={!selectedRoom} value={draft} onChange={(event) => setDraft(event.target.value)} placeholder={selectedRoom ? 'Type message...' : 'Select a client first'} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); sendMessage(); } }} />
            <button className="primary" disabled={!selectedRoom} onClick={sendMessage}><Send size={16} /> Send</button>
          </div>
        </div>
      </div>

      {canGroup && (
        <div className="chatGrid groupChatGrid">
          <aside className="chatList panel">
            <h2>Group Chat</h2>
            {groups.map((group) => (
              <button key={group.id} className={selectedGroup?.id === group.id ? 'activeChat' : ''} onClick={() => setSelectedGroup(group)}>
                <span>{group.name}</span>
                <small>{group.member_names?.join(', ') || 'Internal NOC'}</small>
              </button>
            ))}
            {canCreateGroup && (
              <div className="groupCreateBox">
                <input value={groupForm.name} onChange={(event) => setGroupForm({ ...groupForm, name: event.target.value })} placeholder="New group name" />
                <select multiple value={groupForm.member_ids} onChange={(event) => setGroupForm({ ...groupForm, member_ids: Array.from(event.target.selectedOptions).map((option) => option.value) })}>
                  {chatUsers.map((item) => <option key={item.id} value={item.id}>{item.full_name || item.username}</option>)}
                </select>
                <button onClick={createGroup}><Plus size={15} /> Create Group</button>
              </div>
            )}
          </aside>
          <div className="chatWindow panel">
            <div className="chatHeader"><div><span className="eyebrow">Internal NOC Team</span><h2>{selectedGroup?.name || 'Select Group'}</h2></div></div>
            <div className="messageStream">
              {groupMessages.length === 0 && <p className="muted">No group messages yet.</p>}
              {groupMessages.map((message) => (
                <div key={message.id} className={`messageBubble ${message.sender_id === user.id ? 'mine' : 'theirs'}`}>
                  <strong>{message.sender_name || 'NOC User'}</strong>
                  <p>{message.message}</p>
                  <small>{message.created_at ? new Date(message.created_at).toLocaleString() : ''}</small>
                </div>
              ))}
            </div>
            <div className="chatComposer">
              <textarea value={groupDraft} onChange={(event) => setGroupDraft(event.target.value)} placeholder="Message the NOC team..." onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); sendGroupMessage(); } }} />
              <button className="primary" disabled={!selectedGroup} onClick={sendGroupMessage}><Send size={16} /> Send</button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function TicketsPage({ user, clients, onSummaryRefresh }) {
  const isCustomer = user.role === 'customer';
  const pageKey = isCustomer ? 'my_tickets' : 'tickets';
  const [tickets, setTickets] = useState([]);
  const [selected, setSelected] = useState(null);
  const [messages, setMessages] = useState([]);
  const [reply, setReply] = useState('');
  const [replyVisibility, setReplyVisibility] = useState('client');
  const [users, setUsers] = useState([]);
  const [form, setForm] = useState({ client_id: '', title: '', description: '', category: 'Other', priority: 'Medium' });
  const [error, setError] = useState('');
  const canCreate = canDo(user, pageKey, 'can_create');
  const canEdit = !isCustomer && canDo(user, 'tickets', 'can_edit');
  const categories = ['Billing', 'Routing', 'VOS', 'RDP', 'DID', 'Other'];
  const priorities = ['Low', 'Medium', 'High', 'Critical'];
  const statuses = ['Open', 'In Progress', 'Waiting Client', 'Resolved', 'Closed'];

  const loadTickets = async () => {
    const rows = await request('/tickets');
    setTickets(rows);
    setSelected((current) => rows.find((ticket) => ticket.id === current?.id) || current);
    onSummaryRefresh?.();
  };

  useEffect(() => {
    loadTickets().catch((err) => setError(err.message));
    if (!isCustomer) request('/chat/users').then(setUsers).catch(() => setUsers([]));
  }, []);

  useEffect(() => {
    if (!selected?.id) {
      setMessages([]);
      return;
    }
    request(`/tickets/${selected.id}/messages`).then(setMessages).catch((err) => setError(err.message));
  }, [selected?.id]);

  const createTicket = async () => {
    if (!form.title.trim()) return;
    const payload = {
      ...form,
      client_id: isCustomer ? null : Number(form.client_id),
    };
    const ticket = await request('/tickets', { method: 'POST', body: JSON.stringify(payload) });
    setForm({ client_id: '', title: '', description: '', category: 'Other', priority: 'Medium' });
    await loadTickets();
    setSelected(ticket);
  };

  const updateTicket = async (patch) => {
    if (!selected) return;
    const updated = await request(`/tickets/${selected.id}`, { method: 'PUT', body: JSON.stringify(patch) });
    setSelected(updated);
    await loadTickets();
  };

  const sendReply = async () => {
    if (!reply.trim() || !selected) return;
    const row = await request(`/tickets/${selected.id}/messages`, { method: 'POST', body: JSON.stringify({ message: reply, visibility: replyVisibility }) });
    setMessages((current) => [...current, row]);
    setReply('');
    await loadTickets();
  };

  return (
    <section className="communicationPage ticketsPage">
      {error && <div className="error"><AlertTriangle size={18} /> {error}</div>}
      {canCreate && (
        <div className="panel ticketCreatePanel">
          <div><span className="eyebrow">Issue Tracking</span><h2>Create Ticket</h2></div>
          <div className="ticketFormGrid">
            {!isCustomer && <label><span>Client</span><ClientSelect value={form.client_id} clients={clients} onChange={(value) => setForm({ ...form, client_id: value })} /></label>}
            <label><span>Title</span><input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} placeholder="Short issue title" /></label>
            <label><span>Category</span><select value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })}>{categories.map((item) => <option key={item}>{item}</option>)}</select></label>
            <label><span>Priority</span><select value={form.priority} onChange={(event) => setForm({ ...form, priority: event.target.value })}>{priorities.map((item) => <option key={item}>{item}</option>)}</select></label>
            <label className="wide"><span>Description</span><textarea value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} placeholder="Describe the issue..." /></label>
            <button className="primary" onClick={createTicket}><Plus size={16} /> Create Ticket</button>
          </div>
        </div>
      )}

      <div className="tableWrap">
        <table>
          <thead><tr><th>Ticket</th><th>Client</th><th>Title</th><th>Category</th><th>Priority</th><th>Status</th><th>Assigned</th><th>Updated</th><th>Actions</th></tr></thead>
          <tbody>{tickets.map((ticket) => (
            <tr key={ticket.id}>
              <td><strong>{ticket.ticket_no}</strong></td>
              <td>{ticket.client_name || '-'}</td>
              <td>{ticket.title}</td>
              <td>{ticket.category}</td>
              <td><span className={`priorityBadge ${ticket.priority?.toLowerCase()}`}>{ticket.priority}</span></td>
              <td><StatusPill value={ticket.status} /></td>
              <td>{ticket.assigned_to_name || 'Unassigned'}</td>
              <td>{ticket.updated_at ? new Date(ticket.updated_at).toLocaleString() : '-'}</td>
              <td><button onClick={() => setSelected(ticket)}>Open</button></td>
            </tr>
          ))}</tbody>
        </table>
      </div>

      {selected && (
        <div className="modalBackdrop modal-overlay">
          <div className="modal modal-box ticketModal">
            <div className="modalHeader">
              <div><span className="eyebrow">{selected.ticket_no}</span><h2>{selected.title}</h2></div>
              <button className="iconButton" onClick={() => setSelected(null)}><X size={18} /></button>
            </div>
            <div className="ticketDetailGrid">
              <div className="ticketMetaPanel">
                <p><strong>Client:</strong> {selected.client_name}</p>
                <p><strong>Category:</strong> {selected.category}</p>
                <p><strong>Priority:</strong> {selected.priority}</p>
                <p><strong>Status:</strong> <StatusPill value={selected.status} /></p>
                <p><strong>Description:</strong> {selected.description || '-'}</p>
                {canEdit && (
                  <div className="ticketControls">
                    <label>Status<select value={selected.status} onChange={(event) => updateTicket({ status: event.target.value })}>{statuses.map((item) => <option key={item}>{item}</option>)}</select></label>
                    <label>Assignee<select value={selected.assigned_to || ''} onChange={(event) => updateTicket({ assigned_to: event.target.value ? Number(event.target.value) : null })}><option value="">Unassigned</option>{users.map((item) => <option key={item.id} value={item.id}>{item.full_name || item.username}</option>)}</select></label>
                  </div>
                )}
              </div>
              <div className="ticketTimeline">
                {messages.map((message) => (
                  <div key={message.id} className={`ticketMessage ${message.visibility}`}>
                    <div><strong>{message.user_name || 'User'}</strong><span>{message.visibility}</span></div>
                    <p>{message.message}</p>
                    <small>{message.created_at ? new Date(message.created_at).toLocaleString() : ''}</small>
                  </div>
                ))}
                {messages.length === 0 && <p className="muted">No replies yet.</p>}
                <div className="chatComposer">
                  <textarea value={reply} onChange={(event) => setReply(event.target.value)} placeholder="Reply to ticket..." />
                  {!isCustomer && <select value={replyVisibility} onChange={(event) => setReplyVisibility(event.target.value)}><option value="client">Client Reply</option><option value="internal">Internal Note</option></select>}
                  <button className="primary" onClick={sendReply}><Send size={16} /> Reply</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function WebphonePage({ user }) {
  const canCreate = canDo(user, 'webphone', 'can_create');
  const canEdit = canDo(user, 'webphone', 'can_edit');
  const canDelete = canDo(user, 'webphone', 'can_delete');
  const canTest = canCreate;
  const isAdmin = user.role === 'admin';
  const [profiles, setProfiles] = useState([]);
  const [logs, setLogs] = useState([]);
  const [activeTab, setActiveTab] = useState('dialer');
  const [selectedId, setSelectedId] = useState('');
  const [registrationStatus, setRegistrationStatus] = useState('Unregistered');
  const [lastCallStatus, setLastCallStatus] = useState('Idle');
  const [destination, setDestination] = useState('');
  const [cli, setCli] = useState('');
  const [muted, setMuted] = useState(false);
  const [callSeconds, setCallSeconds] = useState(0);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({
    profile_name: '',
    sip_username: '',
    sip_password: '',
    websocket_url: '',
    sip_domain: '',
    outbound_proxy: '',
    cli: '',
    status: 'Active',
    notes: '',
  });
  const [pbxStatus, setPbxStatus] = useState(null);
  const [pbxConnected, setPbxConnected] = useState(false);
  const [webRtcEnabled, setWebRtcEnabled] = useState(false);
  const [pbxConnect, setPbxConnect] = useState({ ip: '127.0.0.1', username: '', password: '' });
  const uaRef = useRef(null);
  const sessionRef = useRef(null);
  const localStreamRef = useRef(null);
  const remoteAudioRef = useRef(null);
  const timerRef = useRef(null);
  const callStartedAtRef = useRef(null);
  const logSavedRef = useRef(false);

  const selectedProfile = profiles.find((profile) => String(profile.id) === String(selectedId));
  const todayKey = new Date().toISOString().slice(0, 10);
  const todayCalls = logs.filter((log) => String(log.created_at || '').slice(0, 10) === todayKey).length;
  const isRegistered = registrationStatus === 'Registered';
  const isConnecting = ['Requesting microphone', 'Connecting', 'Connected'].includes(registrationStatus);
  const registrationDisplay = isRegistered ? '🟢 Registered' : isConnecting ? '⚡ Connecting' : '🔴 Not Connected';
  const registrationClass = isRegistered ? 'running' : isConnecting ? 'warming' : 'offline';
  const inCall = Boolean(sessionRef.current);

  const loadWebphone = async () => {
    const [profileRows, logRows] = await Promise.all([
      request('/webphone/profiles'),
      request('/webphone/call-logs'),
    ]);
    setProfiles(profileRows);
    setLogs(logRows);
    setSelectedId((current) => current || String(profileRows[0]?.id || ''));
    if (!cli && profileRows[0]?.cli) setCli(profileRows[0].cli);
  };

  useEffect(() => {
    loadWebphone().catch((err) => setError(err.message));
    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
      try {
        sessionRef.current?.terminate();
        uaRef.current?.stop();
      } catch {
        // Best effort cleanup when leaving the page.
      }
      localStreamRef.current?.getTracks()?.forEach((track) => track.stop());
    };
  }, []);

  useEffect(() => {
    if (selectedProfile?.cli) setCli(selectedProfile.cli);
  }, [selectedId]);

  const setField = (key, value) => setForm((current) => ({ ...current, [key]: value }));
  const setPbxConnectField = (key, value) => setPbxConnect((current) => ({ ...current, [key]: value }));

  const loadPbxStatus = async () => {
    if (!isAdmin) return;
    try {
      const status = await request('/webphone/pbx/status');
      setPbxStatus(status);
    } catch (err) {
      setError(err.message);
    }
  };

  const connectPbx = async (event) => {
    event.preventDefault();
    if (!isAdmin) return;
    setError('');
    try {
      if (!pbxConnect.ip.trim()) throw new Error('IP is required');
      if (!pbxConnect.username.trim()) throw new Error('Username is required');
      if (!pbxConnect.password.trim()) throw new Error('Password is required');
      const result = await request('/webphone/pbx/connect', {
        method: 'POST',
        body: JSON.stringify(pbxConnect),
      });
      setPbxConnected(true);
      setPbxStatus(result.status);
      setMessage('PBX connected');
    } catch (err) {
      setPbxConnected(false);
      setError(err.message);
    }
  };

  const enableWebRtc = async () => {
    if (!isAdmin) return;
    setError('');
    try {
      const result = await request('/webphone/pbx/enable-webrtc', { method: 'POST', body: JSON.stringify({}) });
      setMessage(result.message || 'WebRTC Enabled Successfully');
      setWebRtcEnabled(true);
      setPbxStatus(result.status);
      await loadWebphone();
      setSelectedId(String(result.profile?.id || selectedId));
    } catch (err) {
      setError(err.message);
    }
  };

  const validateProfilePayload = (payload) => {
    if (!payload.profile_name.trim()) throw new Error('Profile name is required');
    if (!payload.sip_username.trim()) throw new Error('SIP username is required');
    if (!payload.sip_password.trim()) throw new Error('SIP password is required');
    if (!payload.websocket_url.trim().toLowerCase().startsWith('wss://')) throw new Error('Secure WSS required');
    if (!payload.sip_domain.trim()) throw new Error('SIP domain is required');
  };

  const resetProfileForm = () => {
    setEditingId(null);
    setForm({ profile_name: '', sip_username: '', sip_password: '', websocket_url: '', sip_domain: '', outbound_proxy: '', cli: '', status: 'Active', notes: '' });
  };

  const saveProfile = async (event) => {
    event.preventDefault();
    if (!canCreate && !editingId) return;
    if (!canEdit && editingId) return;
    setError('');
    try {
      validateProfilePayload(form);
      const path = editingId ? `/webphone/profiles/${editingId}` : '/webphone/profiles';
      const method = editingId ? 'PUT' : 'POST';
      const saved = await request(path, { method, body: JSON.stringify(form) });
      setMessage(editingId ? 'Webphone profile updated' : 'Webphone profile created');
      resetProfileForm();
      await loadWebphone();
      setSelectedId(String(saved.id));
    } catch (err) {
      setError(err.message);
    }
  };

  const editProfile = (profile) => {
    setEditingId(profile.id);
    setForm({
      profile_name: profile.profile_name || '',
      sip_username: profile.sip_username || '',
      sip_password: profile.sip_password || '',
      websocket_url: profile.websocket_url || '',
      sip_domain: profile.sip_domain || '',
      outbound_proxy: profile.outbound_proxy || '',
      cli: profile.cli || '',
      status: profile.status || 'Active',
      notes: profile.notes || '',
    });
  };

  const deleteProfile = async (profile) => {
    if (!canDelete) return;
    if (!window.confirm(`Delete Webphone profile ${profile.profile_name}?`)) return;
    await request(`/webphone/profiles/${profile.id}`, { method: 'DELETE' });
    setMessage('Webphone profile deleted');
    await loadWebphone();
  };

  const startTimer = () => {
    if (timerRef.current) window.clearInterval(timerRef.current);
    callStartedAtRef.current = Date.now();
    setCallSeconds(0);
    timerRef.current = window.setInterval(() => {
      setCallSeconds(Math.floor((Date.now() - callStartedAtRef.current) / 1000));
    }, 1000);
  };

  const stopTimer = () => {
    if (timerRef.current) window.clearInterval(timerRef.current);
    timerRef.current = null;
    return callStartedAtRef.current ? Math.floor((Date.now() - callStartedAtRef.current) / 1000) : 0;
  };

  const clearRemoteAudio = () => {
    if (!remoteAudioRef.current) return;
    remoteAudioRef.current.pause?.();
    remoteAudioRef.current.srcObject = null;
  };

  const saveCallLog = async (status, notes = '') => {
    if (logSavedRef.current || !selectedProfile || !destination.trim()) return;
    logSavedRef.current = true;
    const duration = stopTimer();
    try {
      await request('/webphone/call-logs', {
        method: 'POST',
        body: JSON.stringify({
          profile_id: selectedProfile.id,
          cli: cli || selectedProfile.cli || '',
          destination,
          status,
          duration,
          notes,
        }),
      });
      const nextLogs = await request('/webphone/call-logs');
      setLogs(nextLogs);
    } catch (err) {
      setError(err.message);
    }
  };

  const registerWebphone = async () => {
    if (!canTest) {
      setError('Webphone test permission is required');
      return;
    }
    if (!selectedProfile) {
      setError('Select a Webphone profile first');
      return;
    }
    if (!selectedProfile.websocket_url?.toLowerCase().startsWith('wss://')) {
      setError('Secure WSS required');
      return;
    }
    setError('');
    try {
      setRegistrationStatus('Requesting microphone');
      localStreamRef.current?.getTracks()?.forEach((track) => track.stop());
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      localStreamRef.current = stream;
      const JsSIPModule = await import('jssip');
      const JsSIP = JsSIPModule.default || JsSIPModule;
      const socket = new JsSIP.WebSocketInterface(selectedProfile.websocket_url);
      const ua = new JsSIP.UA({
        sockets: [socket],
        uri: `sip:${selectedProfile.sip_username}@${selectedProfile.sip_domain}`,
        authorization_user: selectedProfile.sip_username,
        password: selectedProfile.sip_password,
        register: true,
        register_expires: 300,
        connection_recovery_min_interval: 2,
        connection_recovery_max_interval: 30,
        session_timers: false,
        display_name: selectedProfile.cli || selectedProfile.sip_username,
      });
      ua.on('connecting', () => setRegistrationStatus('Connecting'));
      ua.on('connected', () => setRegistrationStatus('Connected'));
      ua.on('disconnected', () => setRegistrationStatus('Not Connected'));
      ua.on('registered', () => {
        setRegistrationStatus('Registered');
        setMessage('Webphone registered');
      });
      ua.on('unregistered', () => setRegistrationStatus('Unregistered'));
      ua.on('registrationFailed', (event) => {
        setRegistrationStatus('Registration Failed');
        setError(event?.cause || 'Registration failed');
      });
      uaRef.current?.stop();
      uaRef.current = ua;
      ua.start();
    } catch (err) {
      setRegistrationStatus('Microphone Failed');
      setError(err?.name === 'NotAllowedError' ? 'Allow microphone access' : err.message);
    }
  };

  const unregisterWebphone = () => {
    try {
      uaRef.current?.unregister();
      uaRef.current?.stop();
    } catch {
      // Ignore cleanup errors from a half-open WebRTC stack.
    }
    uaRef.current = null;
    setRegistrationStatus('Unregistered');
    clearRemoteAudio();
    localStreamRef.current?.getTracks()?.forEach((track) => track.stop());
    localStreamRef.current = null;
  };

  const attachRemoteAudio = (session) => {
    const connection = session.connection;
    if (!connection) return;
    connection.addEventListener('track', (event) => {
      const [remoteStream] = event.streams || [];
      if (remoteStream && remoteAudioRef.current) {
        remoteAudioRef.current.srcObject = remoteStream;
        remoteAudioRef.current.play?.().catch(() => {});
      }
    });
  };

  const callDid = () => {
    if (!canTest) {
      setError('Webphone test permission is required');
      return;
    }
    if (!selectedProfile || !uaRef.current || !isRegistered) {
      setError('Register the selected profile before calling');
      return;
    }
    const did = destination.trim();
    if (!did) {
      setError('Enter DID/destination number');
      return;
    }
    logSavedRef.current = false;
    setError('');
    setLastCallStatus('Calling');
    const callerId = cli || selectedProfile.cli || selectedProfile.sip_username;
    const target = `sip:${did}@${selectedProfile.sip_domain}`;
    const session = uaRef.current.call(target, {
      mediaStream: localStreamRef.current || undefined,
      mediaConstraints: { audio: true, video: false },
      pcConfig: { iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] },
      rtcOfferConstraints: { offerToReceiveAudio: true, offerToReceiveVideo: false },
      extraHeaders: [
        `P-Asserted-Identity: <sip:${callerId}@${selectedProfile.sip_domain}>`,
        `Remote-Party-ID: <sip:${callerId}@${selectedProfile.sip_domain}>;party=calling;privacy=off;screen=no`,
      ],
      eventHandlers: {
        progress: () => setLastCallStatus('Ringing'),
        confirmed: () => {
          setLastCallStatus('Connected');
          startTimer();
        },
        ended: (event) => {
          setLastCallStatus('Ended');
          sessionRef.current = null;
          clearRemoteAudio();
          saveCallLog('Ended', event?.cause || '');
        },
        failed: (event) => {
          const reason = event?.cause || 'Call failed';
          setLastCallStatus(`Failed: ${reason}`);
          sessionRef.current = null;
          clearRemoteAudio();
          saveCallLog('Failed', reason);
        },
      },
    });
    sessionRef.current = session;
    session.on('peerconnection', () => attachRemoteAudio(session));
    attachRemoteAudio(session);
  };

  const hangup = () => {
    if (!sessionRef.current) return;
    try {
      sessionRef.current.terminate();
    } catch {
      // Session may already be terminated by the remote side.
    }
    setLastCallStatus('Hangup');
    sessionRef.current = null;
    clearRemoteAudio();
    saveCallLog('Hangup', 'Manual hangup');
  };

  const toggleMute = () => {
    const nextMuted = !muted;
    localStreamRef.current?.getAudioTracks()?.forEach((track) => {
      track.enabled = !nextMuted;
    });
    setMuted(nextMuted);
  };

  const durationText = (seconds) => {
    const minutes = Math.floor(seconds / 60);
    const remain = seconds % 60;
    return `${String(minutes).padStart(2, '0')}:${String(remain).padStart(2, '0')}`;
  };

  const cards = [
    ['Registration Status', registrationDisplay],
    ['Selected Profile', selectedProfile?.profile_name || 'None'],
    ['Last Call Status', lastCallStatus],
    ['Today Test Calls', todayCalls],
  ];

  return (
    <section className="webphonePage">
      <div className="cards managementCards">
        {cards.map(([label, value]) => <div className="metric" key={label}><span>{label}</span><strong>{value}</strong></div>)}
      </div>
      {message && <div className="toastSuccess">{message}</div>}
      {error && <div className="error"><AlertTriangle size={18} /> {error}</div>}

      <div className="webphoneTabs">
        {['dialer', 'profiles', 'logs', ...(isAdmin ? ['pbx'] : [])].map((tab) => (
          <button key={tab} className={activeTab === tab ? 'activeTab' : ''} onClick={() => setActiveTab(tab)}>
            {tab === 'pbx' ? 'PBX Setup' : tab === 'logs' ? 'Call Logs' : tab[0].toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {activeTab === 'dialer' && (
        <div className="panel webphoneDialerPanel">
          <div className="sectionHeader">
            <div><span className="eyebrow">DID Test Dialer</span><h2>Browser WebRTC Webphone</h2></div>
            <span className={`agentStatus ${registrationClass}`}>{registrationDisplay}</span>
          </div>
          <div className="dialerForm">
            <label><span>Profile</span><select value={selectedId} onChange={(event) => setSelectedId(event.target.value)}><option value="">Select profile</option>{profiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.profile_name}</option>)}</select></label>
            <label><span>DID / Destination</span><input value={destination} onChange={(event) => setDestination(event.target.value)} placeholder="Enter DID to test" /></label>
            <label><span>CLI / Caller ID</span><input value={cli} onChange={(event) => setCli(event.target.value)} placeholder="Caller ID" /></label>
            <label><span>Call Timer</span><input value={durationText(callSeconds)} readOnly /></label>
          </div>
          <div className="dialerControls">
            <button onClick={registerWebphone} disabled={!canTest || isRegistered || !selectedProfile}><RadioTower size={16} /> Register</button>
            <button onClick={unregisterWebphone} disabled={!uaRef.current}><PhoneOff size={16} /> Unregister</button>
            <button className="primary" onClick={callDid} disabled={!canTest || !isRegistered || inCall}><Phone size={16} /> Call</button>
            <button className="danger" onClick={hangup} disabled={!inCall}><PhoneOff size={16} /> Hangup</button>
            <button onClick={toggleMute} disabled={!localStreamRef.current}>{muted ? <MicOff size={16} /> : <Mic size={16} />} {muted ? 'Unmute' : 'Mute'}</button>
          </div>
          <audio ref={remoteAudioRef} autoPlay playsInline />
          <p className="muted">Only secure WSS WebRTC is supported. Calls route through Asterisk to VOS/carrier trunks.</p>
        </div>
      )}

      {activeTab === 'profiles' && (
        <div className="panel webphoneProfilePanel">
          <div className="sectionHeader">
            <div><span className="eyebrow">WSS SIP Profile</span><h2>WebRTC Gateway Profiles</h2></div>
            <span className="typeBadge">{profiles.length} profiles</span>
          </div>
          {(canCreate || editingId) && (
            <form className="webphoneForm" onSubmit={saveProfile}>
              <label><span>Profile Name</span><input value={form.profile_name} onChange={(event) => setField('profile_name', event.target.value)} placeholder="pbx.voipzap.com DID Test" /></label>
              <label><span>SIP Username</span><input value={form.sip_username} onChange={(event) => setField('sip_username', event.target.value)} placeholder="1001" /></label>
              <label><span>SIP Password</span><input type="password" value={form.sip_password} onChange={(event) => setField('sip_password', event.target.value)} placeholder="SIP secret" /></label>
              <label><span>WebSocket URL</span><input value={form.websocket_url} onChange={(event) => setField('websocket_url', event.target.value)} placeholder="wss://pbx.voipzap.com:8089/ws" /></label>
              <label><span>SIP Domain</span><input value={form.sip_domain} onChange={(event) => setField('sip_domain', event.target.value)} placeholder="pbx.voipzap.com" /></label>
              <label><span>Outbound Proxy</span><input value={form.outbound_proxy} onChange={(event) => setField('outbound_proxy', event.target.value)} placeholder="Optional" /></label>
              <label><span>Default CLI</span><input value={form.cli} onChange={(event) => setField('cli', event.target.value)} placeholder="Caller ID" /></label>
              <label><span>Status</span><select value={form.status} onChange={(event) => setField('status', event.target.value)}>{statuses.map((status) => <option key={status}>{status}</option>)}</select></label>
              <label className="wide"><span>Notes</span><textarea value={form.notes} onChange={(event) => setField('notes', event.target.value)} placeholder="Gateway/trunk notes" /></label>
              <div className="wide formActions">
                <button className="primary">{editingId ? 'Update Profile' : 'Save Profile'}</button>
                {editingId && <button type="button" onClick={resetProfileForm}>Cancel Edit</button>}
              </div>
            </form>
          )}
          <div className="tableWrap webphoneProfileTable">
            <table>
              <thead><tr><th>Profile</th><th>SIP User</th><th>WSS</th><th>Domain</th><th>CLI</th><th>Status</th><th>Actions</th></tr></thead>
              <tbody>{profiles.map((profile) => (
                <tr key={profile.id} className={String(profile.id) === String(selectedId) ? 'selectedRow' : ''}>
                  <td><strong>{profile.profile_name}</strong><small>Password: ********</small></td>
                  <td>{profile.sip_username}</td>
                  <td>{profile.websocket_url}</td>
                  <td>{profile.sip_domain}</td>
                  <td>{profile.cli || '-'}</td>
                  <td><StatusPill value={profile.status} /></td>
                  <td className="actions">
                    <button onClick={() => { setSelectedId(String(profile.id)); setActiveTab('dialer'); }}>Use</button>
                    {canEdit && <button onClick={() => editProfile(profile)}><Edit3 size={15} /> Edit</button>}
                    {canDelete && <button className="danger" onClick={() => deleteProfile(profile)}><Trash2 size={15} /> Delete</button>}
                  </td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === 'logs' && (
        <div className="panel">
          <div className="sectionHeader">
            <div><span className="eyebrow">DID Test Trail</span><h2>Webphone Call Logs</h2></div>
            <button onClick={loadWebphone}><RefreshCcw size={16} /> Refresh</button>
          </div>
          <div className="tableWrap">
            <table>
              <thead><tr><th>Date/Time</th><th>Profile</th><th>CLI</th><th>DID</th><th>Status</th><th>Duration</th><th>Notes</th><th>Created By</th></tr></thead>
              <tbody>{logs.map((log) => (
                <tr key={log.id}>
                  <td>{log.created_at ? new Date(log.created_at).toLocaleString() : '-'}</td>
                  <td>{log.profile_name || '-'}</td>
                  <td>{log.cli || '-'}</td>
                  <td>{log.destination}</td>
                  <td><StatusPill value={log.status} /></td>
                  <td>{durationText(log.duration || 0)}</td>
                  <td>{log.notes || '-'}</td>
                  <td>{log.created_by || '-'}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === 'pbx' && isAdmin && (
        <div className="panel pbxSetupPanel">
          <div className="sectionHeader">
            <div><span className="eyebrow">Safe PBX Setup</span><h2>Connect &gt; Enable WebRTC &gt; Done</h2></div>
          </div>
          {pbxStatus?.message && <div className="error"><AlertTriangle size={18} /> {pbxStatus.message}</div>}
          {webRtcEnabled && <div className="toastSuccess">WebRTC Enabled Successfully</div>}
          {!pbxConnected ? (
            <form className="webphoneForm pbxConnectForm" onSubmit={connectPbx}>
              <label><span>IP</span><input value={pbxConnect.ip} onChange={(event) => setPbxConnectField('ip', event.target.value)} placeholder="127.0.0.1" /></label>
              <label><span>Username</span><input value={pbxConnect.username} onChange={(event) => setPbxConnectField('username', event.target.value)} placeholder="Server admin username" /></label>
              <label><span>Password</span><input type="password" value={pbxConnect.password} onChange={(event) => setPbxConnectField('password', event.target.value)} placeholder="Not stored" /></label>
              <div className="wide formActions">
                <button className="primary">Connect</button>
              </div>
            </form>
          ) : (
            <div className="pbxEnableBox">
              <button className="primary pbxEnableButton" onClick={enableWebRtc}>Enable WebRTC</button>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

const bareMetalStatuses = ['Pending', 'Connecting', 'Mounting ISO', 'Rebooting', 'Installing', 'Waiting for SSH', 'Completed'];

function BareMetalOsInstallerPage({ user }) {
  const canEdit = canDo(user, 'bare_metal_os_installer', 'can_edit');
  const [form, setForm] = useState({ server_name: '', ipmi_ip: '', username: '', password: '', public_ip: '', os_name: 'ViciBox 12' });
  const [status, setStatus] = useState('Pending');
  const [steps, setSteps] = useState([]);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState('');

  const setField = (field, value) => setForm((current) => ({ ...current, [field]: value }));
  const payload = () => ({ ...form });

  const testIpmi = async () => {
    setError('');
    setMessage('');
    setStatus('Connecting');
    setBusy('test');
    try {
      const result = await request('/ipmi/test', { method: 'POST', body: JSON.stringify(payload()) });
      setStatus('Completed');
      setMessage(result.message || 'IPMI connection successful');
      setSteps([{ step: 'Connecting', status: 'Completed', message: result.method || 'IPMI reachable' }]);
    } catch (err) {
      setStatus('Pending');
      setError(err.message);
    } finally {
      setBusy('');
    }
  };

  const startInstall = async () => {
    if (!window.confirm('This will erase all data on server')) return;
    setError('');
    setMessage('');
    setStatus('Mounting ISO');
    setBusy('install');
    try {
      const result = await request('/ipmi/install', { method: 'POST', body: JSON.stringify(payload()) });
      setSteps(result.steps || []);
      setStatus(result.status || 'Installing');
      setMessage(result.message || 'OS install started');
    } catch (err) {
      setStatus('Pending');
      setError(err.message);
    } finally {
      setBusy('');
    }
  };

  return (
    <section className="bareMetalPage">
      <div className="cards managementCards">
        <div className="metric"><span>Status</span><strong>{status}</strong></div>
        <div className="metric payment"><span>Target OS</span><strong>{form.os_name}</strong></div>
        <div className="metric revenue"><span>Server</span><strong>{form.server_name || '-'}</strong></div>
      </div>
      {message && <div className="toastSuccess">{message}</div>}
      {error && <div className="error"><AlertTriangle size={16} /> {error}</div>}
      <div className="bareMetalLimit">Works only on dedicated servers with IPMI (iDRAC/iLO/Supermicro). Not supported on VPS.</div>

      <div className="bareMetalLayout">
        <div className="panel bareMetalFormPanel">
          <div className="sectionHeader"><div><span className="eyebrow">Bare metal provisioning</span><h2>OS Installer</h2></div></div>
          <div className="bareMetalForm">
            <label><span>Server Name</span><input value={form.server_name} onChange={(event) => setField('server_name', event.target.value)} placeholder="BM-01" /></label>
            <label><span>IPMI IP</span><input value={form.ipmi_ip} onChange={(event) => setField('ipmi_ip', event.target.value)} placeholder="192.0.2.10" /></label>
            <label><span>Username</span><input value={form.username} onChange={(event) => setField('username', event.target.value)} placeholder="ADMIN" /></label>
            <label><span>Password</span><input type="password" value={form.password} onChange={(event) => setField('password', event.target.value)} /></label>
            <label><span>Public IP</span><input value={form.public_ip} onChange={(event) => setField('public_ip', event.target.value)} placeholder="203.0.113.10" /></label>
            <label><span>OS Selection</span><select value={form.os_name} onChange={(event) => setField('os_name', event.target.value)}><option>ViciBox 12</option><option>AlmaLinux 9</option><option>Debian 12</option><option>Proxmox VE</option></select></label>
          </div>
          <div className="formActions">
            <button type="button" onClick={testIpmi} disabled={busy === 'test'}><Server size={16} /> {busy === 'test' ? 'Testing...' : 'Test IPMI Connection'}</button>
            <button type="button" className="primary" onClick={startInstall} disabled={!canEdit || busy === 'install'}><Play size={16} /> {busy === 'install' ? 'Starting...' : 'Start OS Install'}</button>
          </div>
        </div>

        <aside className="panel bareMetalStatusPanel">
          <div className="sectionHeader"><div><span className="eyebrow">Status panel</span><h2>Install Flow</h2></div></div>
          <div className="bareMetalStatusList">
            {bareMetalStatuses.map((item) => <div className={item === status ? 'active' : ''} key={item}><span>{item}</span><StatusPill value={item === status ? 'Running' : item === 'Completed' && status === 'Completed' ? 'Success' : 'Pending'} /></div>)}
          </div>
          <div className="bareMetalStepLog">
            {steps.map((step, index) => <div key={`${step.step}-${index}`}><strong>{step.step}</strong><span>{step.status}</span><small>{step.message}</small></div>)}
            {steps.length === 0 && <p className="muted">IPMI test and install progress will appear here.</p>}
          </div>
        </aside>
      </div>
    </section>
  );
}

function UpdateCenterPage({ user }) {
  const canEdit = canDo(user, 'update_center', 'can_edit');
  const [status, setStatus] = useState(null);
  const [logs, setLogs] = useState([]);
  const [tab, setTab] = useState('status');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const logsRef = useRef(null);

  const loadStatus = async (quiet = false) => {
    try {
      const result = await request('/update/status');
      setStatus(result);
      setLogs(result.logs || []);
      if (!quiet) setError('');
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    loadStatus().catch(() => {});
    const timer = window.setInterval(() => loadStatus(true).catch(() => {}), 4000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!logsRef.current) return;
    logsRef.current.scrollTop = logsRef.current.scrollHeight;
  }, [logs]);

  const runCheck = async () => {
    setBusy('check');
    setError('');
    setMessage('');
    try {
      const result = await request('/update/check', { method: 'POST', body: JSON.stringify({}) });
      setStatus(result);
      setLogs(result.logs || []);
      setMessage(result.update_available ? 'Update available from GitHub.' : 'No new updates found.');
      setTab('features');
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy('');
    }
  };

  const runUpdate = async () => {
    if (!window.confirm('This will update NOC360 from GitHub and restart services. Continue?')) return;
    setBusy('run');
    setError('');
    setMessage('');
    try {
      const result = await request('/update/run', { method: 'POST', body: JSON.stringify({}) });
      setStatus(result.status || null);
      setLogs(result.status?.logs || []);
      setMessage(result.message || 'Update workflow started.');
      setTab('logs');
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy('');
    }
  };

  const runRollback = async () => {
    if (!window.confirm('Rollback last backup and restart services?')) return;
    setBusy('rollback');
    setError('');
    setMessage('');
    try {
      const result = await request('/update/rollback', { method: 'POST', body: JSON.stringify({}) });
      setStatus(result.status || null);
      setLogs(result.status?.logs || []);
      setMessage(result.message || 'Rollback workflow started.');
      setTab('logs');
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy('');
    }
  };

  const updateAvailable = status?.update_available ? 'Yes' : 'No';
  const serviceStatus = status?.service_status || 'Unknown';
  const commits = status?.new_commits || [];
  const changedFiles = status?.changed_files || [];

  return (
    <section className="updateCenterPage">
      <div className="cards managementCards">
        <div className="metric"><span>Current Version</span><strong>{status?.current_local_commit || '-'}</strong></div>
        <div className="metric payment"><span>Latest Version</span><strong>{status?.latest_remote_commit || '-'}</strong></div>
        <div className="metric revenue"><span>Update Available</span><strong>{updateAvailable}</strong></div>
        <div className="metric"><span>Last Update</span><strong>{status?.last_update_at ? new Date(status.last_update_at).toLocaleString() : '-'}</strong></div>
      </div>

      <div className="updateCenterLayout">
        <div className="panel updateCenterMain">
          <div className="sectionHeader">
            <div><span className="eyebrow">System Update Center</span><h2>Update Center</h2></div>
            <div className="actions">
              <button type="button" onClick={() => loadStatus()} disabled={busy === 'refresh'}><RefreshCcw size={16} /> Refresh</button>
              <button type="button" onClick={runCheck} disabled={busy === 'check' || busy === 'run' || busy === 'rollback'}>{busy === 'check' ? 'Checking...' : 'Check Updates'}</button>
              <button type="button" className="primary" onClick={runUpdate} disabled={!canEdit || busy === 'check' || busy === 'run' || busy === 'rollback'}>{busy === 'run' ? 'Updating...' : 'Update Now'}</button>
            </div>
          </div>
          {message && <div className="toastSuccess">{message}</div>}
          {error && <div className="error"><AlertTriangle size={16} /> {error}</div>}

          <div className="updateCenterStatusGrid">
            <div><span>Current Local Branch</span><strong>{status?.current_local_branch || '-'}</strong></div>
            <div><span>Current Local Commit</span><strong>{status?.current_local_commit || '-'}</strong></div>
            <div><span>Latest Remote Commit</span><strong>{status?.latest_remote_commit || '-'}</strong></div>
            <div><span>Service Status</span><strong>{serviceStatus}</strong></div>
            <div><span>Last Checked</span><strong>{status?.last_checked_at ? new Date(status.last_checked_at).toLocaleString() : '-'}</strong></div>
            <div><span>Job Status</span><strong>{status?.job_status || 'idle'}</strong></div>
          </div>

          <div className="updateCenterTabs">
            {[
              ['status', 'Status'],
              ['features', 'New Features'],
              ['logs', 'Update Logs'],
              ['rollback', 'Rollback'],
            ].map(([key, label]) => (
              <button type="button" key={key} className={tab === key ? 'active' : ''} onClick={() => setTab(key)}>{label}</button>
            ))}
          </div>

          {tab === 'status' && (
            <div className="panel updateCenterTabPanel">
              <p className="muted">Production path: <code>/opt/noc360</code></p>
              <p className="muted">Service: <code>noc360</code></p>
              <p className="muted">Update Available: <strong>{updateAvailable}</strong></p>
              <p className="muted">Feature Summary: {status?.feature_summary || 'No update summary yet.'}</p>
            </div>
          )}

          {tab === 'features' && (
            <div className="panel updateCenterTabPanel">
              <h3>New Commits</h3>
              <div className="updateCenterList">
                {commits.length ? commits.map((item) => <div key={item}>{item}</div>) : <div className="muted">No new commits detected.</div>}
              </div>
              <h3>Changed Files</h3>
              <div className="updateCenterList">
                {changedFiles.length ? changedFiles.map((item) => <div key={item}>{item}</div>) : <div className="muted">No file changes to show.</div>}
              </div>
            </div>
          )}

          {tab === 'logs' && (
            <div className="panel updateCenterTabPanel">
              <div className="updateCenterLogs" ref={logsRef}>
                {logs.length ? logs.map((entry, index) => (
                  <div key={`${entry.timestamp}-${index}`} className={`updateCenterLogRow ${entry.level || 'info'}`}>
                    <strong>{entry.timestamp ? new Date(entry.timestamp).toLocaleString() : '-'}</strong>
                    <span>{entry.message}</span>
                  </div>
                )) : <div className="muted">No logs yet.</div>}
              </div>
            </div>
          )}

          {tab === 'rollback' && (
            <div className="panel updateCenterTabPanel">
              <p className="muted">Last backup: {status?.last_backup_path || 'No backup created yet.'}</p>
              <button type="button" className="danger" onClick={runRollback} disabled={!canEdit || !status?.last_backup_path || busy === 'run' || busy === 'rollback'}>{busy === 'rollback' ? 'Rolling Back...' : 'Rollback Last Backup'}</button>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function AsteriskSoundManagerPage({ user }) {
  const canCreate = canDo(user, 'asterisk_sound_manager', 'can_create');
  const canEdit = canDo(user, 'asterisk_sound_manager', 'can_edit');
  const canDelete = canDo(user, 'asterisk_sound_manager', 'can_delete');
  const [servers, setServers] = useState([]);
  const [selectedIds, setSelectedIds] = useState([]);
  const [viewServerId, setViewServerId] = useState('');
  const [search, setSearch] = useState('');
  const [fileSearch, setFileSearch] = useState('');
  const [files, setFiles] = useState([]);
  const [form, setForm] = useState({ cluster_name: '', server_name: '', server_ip: '', ssh_port: 22, root_username: 'root', root_password: '', sounds_path: '/usr/share/asterisk/sounds/', status: 'Active' });
  const [editingId, setEditingId] = useState(null);
  const [uploadFile, setUploadFile] = useState(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState('');
  const [deploymentResults, setDeploymentResults] = useState([]);
  const deploymentStatusRef = useRef(null);
  const [targetFilter, setTargetFilter] = useState('');
  const [globalSearch, setGlobalSearch] = useState({ file_name: '', search_type: 'contains', extension_filter: '.wav' });
  const [globalSearchResults, setGlobalSearchResults] = useState([]);
  const [globalSearchSummary, setGlobalSearchSummary] = useState({ total_servers: 0, completed: 0, found: 0, failed: 0, timeout: 0 });
  const globalSearchStatusRef = useRef(null);
  const [serverAction, setServerAction] = useState({ action: 'restart_asterisk', mode: 'sequentially', command: '', delay_seconds: 10 });
  const [actionResults, setActionResults] = useState([]);
  const [actionSummary, setActionSummary] = useState({ total: 0, pending: 0, running: 0, success: 0, failed: 0 });
  const actionStatusRef = useRef(null);

  const loadServers = async () => {
    const rows = await request('/asterisk-sounds/servers');
    setServers(rows);
    if (selectedIds.length === 0 && rows[0]) {
      setSelectedIds([String(rows[0].id)]);
      setViewServerId(String(rows[0].id));
    }
  };

  useEffect(() => {
    loadServers().catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!deploymentStatusRef.current || deploymentResults.length === 0) return;
    deploymentStatusRef.current.scrollTop = deploymentStatusRef.current.scrollHeight;
  }, [deploymentResults]);

  useEffect(() => {
    if (!globalSearchStatusRef.current || globalSearchResults.length === 0) return;
    globalSearchStatusRef.current.scrollTop = globalSearchStatusRef.current.scrollHeight;
  }, [globalSearchResults]);

  useEffect(() => {
    if (!actionStatusRef.current || actionResults.length === 0) return;
    actionStatusRef.current.scrollTop = actionStatusRef.current.scrollHeight;
  }, [actionResults]);

  const selectedServers = servers.filter((server) => selectedIds.includes(String(server.id)));
  const selectedServer = selectedServers.length === 1 ? selectedServers[0] : null;
  const activeViewServer = servers.find((server) => String(server.id) === String(viewServerId)) || selectedServer || selectedServers[0] || null;
  const filteredServers = servers.filter((server) => `${server.cluster_name} ${server.server_name} ${server.server_ip} ${server.sounds_path}`.toLowerCase().includes(search.toLowerCase()));
  const targetFilterNormalized = targetFilter.trim().toLowerCase();
  const filteredTargetServers = servers.filter((server) => `${server.cluster_name} ${server.server_name} ${server.server_ip}`.toLowerCase().includes(targetFilterNormalized));
  const filteredFiles = files.filter((item) => item.filename.toLowerCase().includes(fileSearch.toLowerCase()));
  const uploadReady = selectedServers.length > 0 && uploadFile && uploadFile.name.toLowerCase().endsWith('.wav');
  const globalSearchReady = Boolean(globalSearch.file_name.trim());
  const searchableServers = servers.filter((server) => String(server.status || '').toLowerCase() === 'active');
  const pendingCount = deploymentResults.filter((item) => item.status === 'pending').length;
  const uploadingCount = deploymentResults.filter((item) => item.status === 'connecting' || item.status === 'uploading').length;
  const successCount = deploymentResults.filter((item) => item.status === 'success').length;
  const failedCount = deploymentResults.filter((item) => item.status === 'failed').length;
  const skippedCount = deploymentResults.filter((item) => item.status === 'skipped').length;
  const failedRows = deploymentResults.filter((item) => item.status === 'failed');
  const canRunCustomServerCommand = user?.role === 'admin';
  const bulkActionReady = selectedServers.length > 0 && (serverAction.action !== 'custom_safe_command' || Boolean(serverAction.command.trim()));

  const setField = (field, value) => setForm((current) => ({ ...current, [field]: value }));
  const setGlobalSearchField = (field, value) => setGlobalSearch((current) => ({ ...current, [field]: value }));
  const setServerActionField = (field, value) => setServerAction((current) => ({ ...current, [field]: value }));
  const updateDeploymentRow = (serverId, patch) => {
    setDeploymentResults((current) => current.map((item) => item.server_id === serverId ? { ...item, ...patch } : item));
  };
  const updateActionSummary = (rows) => {
    const normalizedRows = Array.isArray(rows) ? rows : [];
    setActionSummary({
      total: normalizedRows.length,
      pending: normalizedRows.filter((item) => item.status === 'pending').length,
      running: normalizedRows.filter((item) => item.status === 'running').length,
      success: normalizedRows.filter((item) => item.status === 'success').length,
      failed: normalizedRows.filter((item) => item.status === 'failed').length,
    });
  };
  const formatDeploymentTime = (value) => {
    if (!value) return '-';
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return String(value);
    return parsed.toLocaleString('en-IN', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true,
    });
  };
  const getAsteriskServerGroupName = (server) => {
    const cluster = String(server.cluster_name || '').trim();
    if (cluster) return cluster;
    const name = String(server.server_name || '').trim();
    const match = name.match(/^[A-Za-z]+/);
    return match?.[0] || 'Other';
  };
  const groupedTargetServers = filteredTargetServers.reduce((accumulator, server) => {
    const group = getAsteriskServerGroupName(server);
    if (!accumulator[group]) accumulator[group] = [];
    accumulator[group].push(server);
    return accumulator;
  }, {});
  const orderedTargetGroups = Object.entries(groupedTargetServers).sort(([left], [right]) => left.localeCompare(right));
  const deploymentStatusLabel = (status) => {
    const normalized = String(status || '').toLowerCase();
    return ({
      pending: 'Pending',
      connecting: 'Connecting',
      uploading: 'Uploading',
      success: 'Success',
      failed: 'Failed',
      skipped: 'Skipped',
    })[normalized] || 'Pending';
  };
  const downloadDeploymentLog = () => {
    if (!deploymentResults.length) return;
    const rows = deploymentResults.map((item) => ({
      server: item.server_name,
      ip: item.server_ip,
      status: deploymentStatusLabel(item.status),
      message: item.message || '',
      started_at: item.started_at || '',
      finished_at: item.finished_at || '',
      timestamp: item.timestamp || '',
    }));
    exportRows(`asterisk-upload-log-${new Date().toISOString().slice(0, 19).replaceAll(':', '-')}.csv`, rows);
  };
  const updateGlobalSearchSummary = (rows, totalServers) => {
    const normalizedRows = Array.isArray(rows) ? rows : [];
    const completed = normalizedRows.filter((item) => ['found', 'not_found', 'failed', 'timeout', 'skipped'].includes(String(item.status || '').toLowerCase())).length;
    const found = normalizedRows.reduce((sum, item) => sum + (String(item.status || '').toLowerCase() === 'found' ? Number(item.match_count || 0) || 0 : 0), 0);
    const failed = normalizedRows.filter((item) => String(item.status || '').toLowerCase() === 'failed').length;
    const timeout = normalizedRows.filter((item) => String(item.status || '').toLowerCase() === 'timeout').length;
    setGlobalSearchSummary({ total_servers: totalServers, completed, found, failed, timeout });
  };
  const sanitizeSearchErrorMessage = (message) => {
    const text = String(message || '').trim();
    if (!text) return 'Search failed. Try again.';
    if (/<\/?(html|body|head|title|div|span|p|h1)/i.test(text) || /gateway timeout|504/i.test(text)) {
      return 'Search timed out. Try fewer servers or increase timeout.';
    }
    return text.length > 220 ? `${text.slice(0, 217)}...` : text;
  };
  const mergeGlobalSearchRows = (currentRows, incomingRows, batchServerIds = []) => {
    const incomingMap = new Map((incomingRows || []).map((row) => [String(row.server_id), row]));
    const touched = new Set(batchServerIds.map((item) => String(item)));
    return currentRows.map((row) => {
      const key = String(row.server_id);
      if (incomingMap.has(key)) {
        return { ...row, ...incomingMap.get(key) };
      }
      if (touched.has(key) && ['pending', 'searching'].includes(String(row.status || '').toLowerCase())) {
        return {
          ...row,
          status: 'failed',
          message: 'Search failed before a server result was returned',
          finished_at: new Date().toISOString(),
          timestamp: new Date().toISOString(),
        };
      }
      return row;
    });
  };
  const runGlobalFileSearch = async (event) => {
    event?.preventDefault?.();
    setError('');
    setMessage('');
    if (!globalSearch.file_name.trim()) {
      setError('Enter a file name to search');
      return;
    }
    if (searchableServers.length === 0) {
      setError('No active Asterisk sound servers are available for search.');
      return;
    }
    const totalServers = searchableServers.length;
    const initialRows = searchableServers.map((server) => ({
      server_id: server.id,
      server_name: server.server_name,
      server_ip: server.server_ip,
      status: 'pending',
      message: 'Queued for search',
      timestamp: new Date().toISOString(),
      full_path: server.sounds_path || '/usr/share/asterisk/sounds/',
      file_name: '',
      size: 0,
      modified_at: null,
      match_count: 0,
    }));
    setGlobalSearchResults(initialRows);
    updateGlobalSearchSummary(initialRows, totalServers);
    setBusy('global-search');
    try {
      const batchSize = 5;
      let finalRows = initialRows;
      for (let index = 0; index < searchableServers.length; index += batchSize) {
        const batchServers = searchableServers.slice(index, index + batchSize);
        const batchIds = batchServers.map((server) => server.id);
        const batchStartedAt = new Date().toISOString();
        finalRows = finalRows.map((row) => batchIds.includes(row.server_id) ? { ...row, status: 'searching', message: 'Searching remote sounds path...', started_at: batchStartedAt, timestamp: batchStartedAt } : row);
        setGlobalSearchResults(finalRows);
        updateGlobalSearchSummary(finalRows, totalServers);
        try {
          const result = await request('/asterisk-sounds/search', {
            method: 'POST',
            body: JSON.stringify({ ...globalSearch, server_ids: batchIds }),
          });
          finalRows = mergeGlobalSearchRows(finalRows, result.results || [], batchIds);
        } catch (err) {
          const cleanMessage = sanitizeSearchErrorMessage(err.message);
          const finishedAt = new Date().toISOString();
          finalRows = finalRows.map((row) => batchIds.includes(row.server_id) ? { ...row, status: /timed out|timeout/i.test(cleanMessage) ? 'timeout' : 'failed', message: cleanMessage, finished_at: finishedAt, timestamp: finishedAt } : row);
        }
        setGlobalSearchResults(finalRows);
        updateGlobalSearchSummary(finalRows, totalServers);
      }
      const completed = finalRows.filter((item) => ['found', 'not_found', 'failed', 'timeout', 'skipped'].includes(String(item.status || '').toLowerCase())).length;
      const found = finalRows.reduce((sum, item) => sum + (String(item.status || '').toLowerCase() === 'found' ? Number(item.match_count || 0) || 0 : 0), 0);
      const failed = finalRows.filter((item) => ['failed', 'timeout'].includes(String(item.status || '').toLowerCase())).length;
      setMessage(`Search finished. Completed ${completed}/${totalServers} server(s). Found ${found} file(s). Failed ${failed}.`);
    } catch (err) {
      setError(sanitizeSearchErrorMessage(err.message));
    } finally {
      setBusy('');
    }
  };
  const globalStatusLabel = (status) => {
    const normalized = String(status || '').toLowerCase();
    return ({
      pending: 'Pending',
      searching: 'Searching',
      found: 'Found',
      not_found: 'Not Found',
      failed: 'Failed',
      timeout: 'Timeout',
      skipped: 'Skipped',
    })[normalized] || 'Pending';
  };
  const toggleServer = (serverId) => {
    const id = String(serverId);
    setSelectedIds((current) => {
      const next = current.includes(id) ? current.filter((item) => item !== id) : [...current, id];
      if (next.length === 1) setViewServerId(next[0]);
      if (next.length === 0) setViewServerId('');
      if (next.length > 1 && !next.includes(String(viewServerId))) setViewServerId(next[0]);
      return next;
    });
  };
  const selectAllServers = () => {
    const ids = servers.map((server) => String(server.id));
    setSelectedIds(ids);
    setViewServerId(ids[0] || '');
  };
  const selectFilteredServers = () => {
    const filteredIds = filteredTargetServers.map((server) => String(server.id));
    setSelectedIds((current) => Array.from(new Set([...current, ...filteredIds])));
    if (!viewServerId && filteredIds[0]) setViewServerId(filteredIds[0]);
  };
  const clearFilteredServers = () => {
    const filteredSet = new Set(filteredTargetServers.map((server) => String(server.id)));
    setSelectedIds((current) => {
      const remaining = current.filter((id) => !filteredSet.has(id));
      if (filteredSet.has(String(viewServerId))) setViewServerId(remaining[0] || '');
      return remaining;
    });
  };
  const clearSelection = () => {
    setSelectedIds([]);
    setViewServerId('');
    setFiles([]);
  };
  const resetForm = () => {
    setEditingId(null);
    setForm({ cluster_name: '', server_name: '', server_ip: '', ssh_port: 22, root_username: 'root', root_password: '', sounds_path: '/usr/share/asterisk/sounds/', status: 'Active' });
  };

  const saveServer = async (event) => {
    event.preventDefault();
    setError('');
    setMessage('');
    const isEditing = editingId !== null && editingId !== undefined;
    const payload = { ...form, ssh_port: Number(form.ssh_port || 22) };
    if (isEditing && !payload.root_password) delete payload.root_password;
    try {
      const saved = await request(isEditing ? `/asterisk-sounds/servers/${editingId}` : '/asterisk-sounds/servers', {
        method: isEditing ? 'PUT' : 'POST',
        body: JSON.stringify(payload),
      });
      setMessage(isEditing ? `Server updated: ${saved.server_name}` : `Server added: ${saved.server_name}`);
      setSelectedIds([String(saved.id)]);
      setViewServerId(String(saved.id));
      resetForm();
      await loadServers();
    } catch (err) {
      setError(err.message);
    }
  };

  const editServer = (server) => {
    setEditingId(server.id);
    setForm({
      cluster_name: server.cluster_name || '',
      server_name: server.server_name || '',
      server_ip: server.server_ip || '',
      ssh_port: server.ssh_port || 22,
      root_username: server.root_username || 'root',
      root_password: '',
      sounds_path: server.sounds_path || '/usr/share/asterisk/sounds/',
      status: server.status || 'Active',
    });
  };

  const deleteServer = async (server) => {
    if (!window.confirm(`Delete Asterisk sound server ${server.server_name}?`)) return;
    await request(`/asterisk-sounds/servers/${server.id}`, { method: 'DELETE' });
    setMessage('Server deleted');
    setFiles([]);
    setSelectedIds((current) => current.filter((id) => id !== String(server.id)));
    if (String(viewServerId) === String(server.id)) setViewServerId('');
    await loadServers();
  };

  const testServer = async (server) => {
    setError('');
    setMessage('');
    setBusy(`test-${server.id}`);
    try {
      const result = await request(`/asterisk-sounds/servers/${server.id}/test`, { method: 'POST' });
      setMessage(result.message || 'SSH login successful and sounds path is writable');
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy('');
    }
  };

  const viewFiles = async (server = activeViewServer) => {
    if (!server) {
      setError('Select a server library to view');
      return;
    }
    setError('');
    setBusy(`files-${server.id}`);
    try {
      const rows = await request(`/asterisk-sounds/servers/${server.id}/files`);
      setViewServerId(String(server.id));
      setFiles(rows);
      setMessage(`Loaded ${rows.length} WAV file${rows.length === 1 ? '' : 's'} from ${server.server_name}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy('');
    }
  };

  const runWavDeployment = async (serversToUpload) => {
    setError('');
    setMessage('');
    if (serversToUpload.length === 0) {
      setError('Select at least one target server');
      return;
    }
    if (!uploadFile) {
      setError('Select one .wav file to upload');
      return;
    }
    if (!uploadFile.name.toLowerCase().endsWith('.wav')) {
      setError('Only .wav files are allowed');
      return;
    }
    const startedAt = new Date().toISOString();
    setDeploymentResults(serversToUpload.map((server) => ({
      server_id: server.id,
      server: server.server_name,
      server_name: server.server_name,
      ip: server.server_ip,
      server_ip: server.server_ip,
      status: 'pending',
      ok: false,
      message: 'Queued for upload',
      started_at: '',
      finished_at: '',
      timestamp: startedAt,
    })));
    setBusy('upload');
    try {
      for (const server of serversToUpload) {
        const rowStart = new Date().toISOString();
        updateDeploymentRow(server.id, { status: 'connecting', message: 'Opening SSH connection...', started_at: rowStart, finished_at: '', timestamp: rowStart });
        await new Promise((resolve) => window.setTimeout(resolve, 40));
        updateDeploymentRow(server.id, { status: 'uploading', message: 'Uploading WAV file...', timestamp: new Date().toISOString() });
        const body = new FormData();
        body.append('file', uploadFile);
        body.append('server_ids', String(server.id));
        try {
          const result = await request('/asterisk-sounds/upload', { method: 'POST', body });
          const serverResult = (result.results || [])[0] || {};
          updateDeploymentRow(server.id, {
            ...serverResult,
            status: serverResult.status || 'success',
            message: serverResult.message || 'Upload completed successfully',
            started_at: serverResult.started_at || rowStart,
            finished_at: serverResult.finished_at || new Date().toISOString(),
            timestamp: serverResult.finished_at || new Date().toISOString(),
          });
        } catch (err) {
          const finishedAt = new Date().toISOString();
          updateDeploymentRow(server.id, {
            status: 'failed',
            ok: false,
            message: err.message || 'WAV upload failed',
            started_at: rowStart,
            finished_at: finishedAt,
            timestamp: finishedAt,
          });
        }
      }
      if (activeViewServer) setFiles(await request(`/asterisk-sounds/servers/${activeViewServer.id}/files`));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy('');
    }
  };
  const uploadWav = async (event) => {
    event.preventDefault();
    await runWavDeployment(selectedServers);
  };
  const retryFailedUploads = async () => {
    await runWavDeployment(selectedServers.filter((server) => failedRows.some((item) => item.server_id === server.id)));
  };

  const runServerAction = async (event) => {
    event?.preventDefault?.();
    setError('');
    setMessage('');
    if (selectedServers.length === 0) {
      setError('Select at least one target server');
      return;
    }
    if (serverAction.action === 'custom_safe_command' && !canRunCustomServerCommand) {
      setError('Only admin can run custom safe commands');
      return;
    }
    if (serverAction.action === 'custom_safe_command' && !serverAction.command.trim()) {
      setError('Enter a custom safe command');
      return;
    }
    if (serverAction.action === 'reboot' && !window.confirm('This will reboot selected servers. Continue?')) return;
    const customDangerous = serverAction.action === 'custom_safe_command' && /\b(rm|mkfs|dd|reboot|shutdown|poweroff|halt|userdel|passwd)\b/i.test(serverAction.command);
    if (customDangerous && !window.confirm('This command looks dangerous. Continue?')) return;
    const startedAt = new Date().toISOString();
    const initialRows = selectedServers.map((server) => ({
      server_id: server.id,
      server_name: server.server_name,
      server_ip: server.server_ip,
      action: serverAction.action,
      status: 'pending',
      message: 'Queued for action',
      started_at: startedAt,
      finished_at: '',
      timestamp: startedAt,
    }));
    setActionResults(initialRows);
    updateActionSummary(initialRows);
    setBusy('server-action');
    try {
      const runningRows = initialRows.map((row) => ({ ...row, status: 'running', message: serverAction.mode === 'sequentially' ? 'Waiting for sequential execution...' : 'Running action...' }));
      setActionResults(runningRows);
      updateActionSummary(runningRows);
      const result = await request('/asterisk-sounds/actions', {
        method: 'POST',
        body: JSON.stringify({
          server_ids: selectedServers.map((server) => server.id),
          action: serverAction.action,
          mode: serverAction.mode,
          command: serverAction.action === 'custom_safe_command' ? serverAction.command : null,
          delay_seconds: Number(serverAction.delay_seconds || 10),
          confirm_dangerous: customDangerous,
        }),
      });
      const resultMap = new Map((result.results || []).map((item) => [String(item.server_id), item]));
      const nextRows = runningRows.map((row) => resultMap.get(String(row.server_id)) || row);
      setActionResults(nextRows);
      updateActionSummary(nextRows);
      setMessage(result.message || 'Server action finished');
    } catch (err) {
      const finishedAt = new Date().toISOString();
      const failedRowsNext = initialRows.map((row) => ({ ...row, status: 'failed', message: err.message || 'Server action failed', finished_at: finishedAt, timestamp: finishedAt }));
      setActionResults(failedRowsNext);
      updateActionSummary(failedRowsNext);
      setError(err.message);
    } finally {
      setBusy('');
    }
  };

  useEffect(() => {
    if (!deploymentResults.length || busy === 'upload') return;
    const selectedCount = deploymentResults.length;
    setMessage(`Total Servers: ${selectedCount}. Successful: ${deploymentResults.filter((item) => item.status === 'success').length}. Failed: ${deploymentResults.filter((item) => item.status === 'failed').length}.`);
  }, [deploymentResults, busy]);

  const formatBytes = (value) => {
    const size = Number(value || 0);
    if (size < 1024) return `${size} B`;
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
    return `${(size / 1024 / 1024).toFixed(2)} MB`;
  };
  const actionStatusLabel = (status) => {
    const normalized = String(status || '').toLowerCase();
    return ({
      pending: 'Pending',
      running: 'Running',
      success: 'Success',
      failed: 'Failed',
    })[normalized] || 'Pending';
  };
  const actionLabel = serverAction.action === 'reboot' ? 'Reboot' : serverAction.action === 'restart_asterisk' ? 'Restart Asterisk' : 'Custom Safe Command';

  return (
    <section className="asteriskSoundPage">
      <div className="cards managementCards">
        <div className="metric"><span>Sound Servers</span><strong>{servers.length}</strong></div>
        <div className="metric payment"><span>Active</span><strong>{servers.filter((item) => item.status === 'Active').length}</strong></div>
        <div className="metric revenue"><span>Selected</span><strong>{selectedServers.length}</strong></div>
        <div className="metric"><span>WAV Files</span><strong>{files.length}</strong></div>
      </div>

      <div className="asteriskSoundLayout">
        <aside className="panel asteriskSoundSide">
          <div className="sectionHeader">
            <div><span className="eyebrow">Asterisk SSH Vault</span><h2>Sound Servers</h2></div>
            <div className="actions">
              {editingId && <button type="button" onClick={resetForm}><Plus size={16} /> New</button>}
              <button type="button" onClick={loadServers}><RefreshCcw size={16} /></button>
            </div>
          </div>
          {message && <div className="toastSuccess">{message}</div>}
          {error && <div className="error"><AlertTriangle size={16} /> {error}</div>}
          <div className="asteriskExample"><span>Format example</span><code>Cluster1NameAST1, Cluster1NameAST2</code></div>
          <div className="search terminalSearch"><Search size={16} /><input placeholder="Search servers" value={search} onChange={(event) => setSearch(event.target.value)} /></div>

          {(canCreate || editingId) && (
            <form className="terminalForm asteriskSoundForm" onSubmit={saveServer}>
              <label><span>Cluster Name</span><input value={form.cluster_name} onChange={(event) => setField('cluster_name', event.target.value)} placeholder="Cluster1Name" /></label>
              <label><span>Server Name</span><input value={form.server_name} onChange={(event) => setField('server_name', event.target.value)} placeholder="Cluster1NameAST1" /></label>
              <label><span>Server IP</span><input value={form.server_ip} onChange={(event) => setField('server_ip', event.target.value)} placeholder="203.0.113.10" /></label>
              <label><span>SSH Port</span><input type="number" min="1" max="65535" value={form.ssh_port} onChange={(event) => setField('ssh_port', event.target.value)} /></label>
              <label><span>Root Username</span><input value={form.root_username} onChange={(event) => setField('root_username', event.target.value)} placeholder="root" /></label>
              <label><span>Root Password</span><input type="password" value={form.root_password} onChange={(event) => setField('root_password', event.target.value)} placeholder={editingId ? 'Leave blank to keep saved password' : 'Root password'} /></label>
              <label className="wide"><span>Sounds Path</span><input value={form.sounds_path} onChange={(event) => setField('sounds_path', event.target.value)} placeholder="/usr/share/asterisk/sounds/" /></label>
              <label><span>Status</span><select value={form.status} onChange={(event) => setField('status', event.target.value)}>{statuses.map((status) => <option key={status}>{status}</option>)}</select></label>
              <div className="formActions wide">
                <button className="primary"><Plus size={16} /> {editingId ? 'Update Server' : 'Add Server'}</button>
                {editingId && <button type="button" onClick={resetForm}>Cancel</button>}
              </div>
            </form>
          )}

          <div className="asteriskServerList">
            {filteredServers.map((server) => (
              <div className={`asteriskServerCard ${selectedIds.includes(String(server.id)) ? 'selectedAsteriskServer' : ''}`} key={server.id} onClick={() => toggleServer(server.id)} role="button" tabIndex="0">
                <div className="asteriskServerCardMain">
                  <input type="checkbox" checked={selectedIds.includes(String(server.id))} onChange={() => toggleServer(server.id)} onClick={(event) => event.stopPropagation()} />
                  <div>
                    <strong>{server.server_name}</strong>
                    <span>{server.server_ip}</span>
                    <small>{server.cluster_name}</small>
                  </div>
                </div>
                <StatusPill value={server.status} />
                <div className="actions">
                  <button type="button" onClick={(event) => { event.stopPropagation(); testServer(server); }} disabled={busy === `test-${server.id}`}>{busy === `test-${server.id}` ? 'Testing...' : 'Test'}</button>
                  <button type="button" onClick={(event) => { event.stopPropagation(); viewFiles(server); }} disabled={busy === `files-${server.id}`}><FolderOpen size={15} /></button>
                  {canEdit && <button type="button" onClick={(event) => { event.stopPropagation(); editServer(server); }}><Edit3 size={15} /></button>}
                  {canDelete && <button type="button" className="danger" onClick={(event) => { event.stopPropagation(); deleteServer(server); }}><Trash2 size={15} /></button>}
                </div>
              </div>
            ))}
          </div>
        </aside>

        <div className="panel asteriskSoundWorkspace">
          <div className="sectionHeader">
            <div>
              <span className="eyebrow">WAV Deployment</span>
              <h2>{selectedServers.length ? `${selectedServers.length} server${selectedServers.length === 1 ? '' : 's'} selected` : 'Select Target Servers'}</h2>
              <p className="muted">{activeViewServer?.sounds_path || '/usr/share/asterisk/sounds/'}</p>
            </div>
            <div className="actions">
              <button type="button" onClick={() => activeViewServer && testServer(activeViewServer)} disabled={!activeViewServer || busy === `test-${activeViewServer?.id}`}>Test Connection</button>
              <button type="button" onClick={() => viewFiles()} disabled={!activeViewServer || busy === `files-${activeViewServer?.id}`}><FolderOpen size={16} /> View Files</button>
            </div>
          </div>

          <form className="asteriskUploadBox" onSubmit={uploadWav}>
            <div className="asteriskMultiSelect">
              <div className="asteriskMultiHeader">
                <span>Target Servers</span>
                <strong>{selectedServers.length} server{selectedServers.length === 1 ? '' : 's'} selected</strong>
              </div>
              <div className="search terminalSearch asteriskTargetSearch"><Search size={16} /><input placeholder="Search servers by name/IP/cluster" value={targetFilter} onChange={(event) => setTargetFilter(event.target.value)} /></div>
              <div className="actions">
                <button type="button" onClick={selectFilteredServers} disabled={filteredTargetServers.length === 0}>Select Filtered</button>
                <button type="button" onClick={clearFilteredServers} disabled={filteredTargetServers.length === 0}>Clear Filtered</button>
                <button type="button" onClick={selectAllServers}>Select All</button>
                <button type="button" onClick={clearSelection}>Clear Selection</button>
              </div>
              <div className="asteriskMultiOptions">
                {orderedTargetGroups.map(([groupName, groupServers]) => (
                  <div className="asteriskGroupBlock" key={groupName}>
                    <div className="asteriskGroupTitle">{groupName}</div>
                    {groupServers.map((server) => (
                      <label key={server.id}>
                        <input type="checkbox" checked={selectedIds.includes(String(server.id))} onChange={() => toggleServer(server.id)} />
                        <span>{server.server_name}</span>
                        <small>{server.server_ip}</small>
                      </label>
                    ))}
                  </div>
                ))}
                {orderedTargetGroups.length === 0 && <div className="asteriskEmptySelection muted">No servers match this filter.</div>}
              </div>
            </div>
            <label>
              <span>WAV File</span>
              <input type="file" accept=".wav,audio/wav,audio/x-wav" onChange={(event) => setUploadFile(event.target.files?.[0] || null)} />
            </label>
            <button className="primary" disabled={!uploadReady || busy === 'upload'}><Upload size={16} /> {busy === 'upload' ? 'Uploading...' : 'Upload WAV'}</button>
          </form>
          {selectedServers.length === 0 && <div className="asteriskValidation">Select at least one target server.</div>}
          {uploadFile && !uploadFile.name.toLowerCase().endsWith('.wav') && <div className="asteriskValidation">Only .wav files are allowed.</div>}

          <div className="asteriskSearchPanel">
            <div className="sectionHeader">
              <div><span className="eyebrow">Server Actions</span><h2>Server Actions</h2></div>
            </div>
            <form className="asteriskActionForm" onSubmit={runServerAction}>
              <label>
                <span>Server Filter / Search</span>
                <input value={targetFilter} onChange={(event) => setTargetFilter(event.target.value)} placeholder="Search servers by name/IP/cluster" />
              </label>
              <label>
                <span>Action</span>
                <select value={serverAction.action} onChange={(event) => setServerActionField('action', event.target.value)}>
                  <option value="reboot">Reboot</option>
                  <option value="restart_asterisk">Restart Asterisk</option>
                  {canRunCustomServerCommand && <option value="custom_safe_command">Custom Safe Command</option>}
                </select>
              </label>
              <label>
                <span>Execution Mode</span>
                <select value={serverAction.mode} onChange={(event) => setServerActionField('mode', event.target.value)}>
                  <option value="all_together">Run All Together</option>
                  <option value="sequentially">Run Sequentially</option>
                </select>
              </label>
              {serverAction.action === 'custom_safe_command' && canRunCustomServerCommand && (
                <label className="wide">
                  <span>Custom Safe Command</span>
                  <input value={serverAction.command} onChange={(event) => setServerActionField('command', event.target.value)} placeholder="systemctl status asterisk" />
                </label>
              )}
              {serverAction.mode === 'sequentially' && (
                <label>
                  <span>Delay Between Servers</span>
                  <input type="number" min="0" max="600" value={serverAction.delay_seconds} onChange={(event) => setServerActionField('delay_seconds', event.target.value)} />
                </label>
              )}
              <button className="primary" disabled={!bulkActionReady || busy === 'server-action'}><Play size={16} /> {busy === 'server-action' ? 'Running...' : actionLabel}</button>
            </form>
            {!canRunCustomServerCommand && <div className="asteriskValidation">Custom safe commands are available to admin only.</div>}
            {(actionResults.length > 0 || actionSummary.total > 0) && (
              <>
                <div className="asteriskDeploymentCounters asteriskSearchSummary">
                  <div><span>Total Selected</span><strong>{actionSummary.total}</strong></div>
                  <div><span>Pending</span><strong>{actionSummary.pending}</strong></div>
                  <div><span>Running</span><strong>{actionSummary.running}</strong></div>
                  <div><span>Success</span><strong>{actionSummary.success}</strong></div>
                  <div><span>Failed</span><strong>{actionSummary.failed}</strong></div>
                </div>
                <div className="asteriskResultTableWrap" ref={actionStatusRef}>
                  <table className="asteriskResultTable">
                    <thead>
                      <tr>
                        <th>Server Name</th>
                        <th>IP</th>
                        <th>Action</th>
                        <th>Status</th>
                        <th>Message</th>
                        <th>Timestamp</th>
                      </tr>
                    </thead>
                    <tbody>
                      {actionResults.map((row, index) => (
                        <tr className={`asteriskResultRow ${row.status || 'pending'}`} key={`${row.server_id}-${index}`}>
                          <td><strong>{row.server_name}</strong></td>
                          <td>{row.server_ip}</td>
                          <td>{row.action === 'reboot' ? 'Reboot' : row.action === 'restart_asterisk' ? 'Restart Asterisk' : 'Custom Safe Command'}</td>
                          <td><span className={`asteriskResultStatus ${row.status || 'pending'}`}>{actionStatusLabel(row.status)}</span></td>
                          <td>{row.message || '-'}</td>
                          <td>{formatDeploymentTime(row.finished_at || row.started_at || row.timestamp)}</td>
                        </tr>
                      ))}
                      {actionResults.length === 0 && <tr><td colSpan="6" className="muted">No server actions run yet.</td></tr>}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>

          {deploymentResults.length > 0 && (
            <div className="asteriskResultPanel">
              <div className="sectionHeader">
                <div><span className="eyebrow">Deployment Status</span><h2>Deployment Status</h2></div>
                <div className="actions">
                  {failedRows.length > 0 && <button type="button" onClick={retryFailedUploads} disabled={busy === 'upload' || !uploadFile}>Retry Failed</button>}
                  <button type="button" onClick={downloadDeploymentLog} disabled={!deploymentResults.length}>Download Upload Log</button>
                </div>
              </div>
              <div className="asteriskDeploymentCounters">
                <div><span>Total Selected</span><strong>{deploymentResults.length}</strong></div>
                <div><span>Uploading</span><strong>{uploadingCount}</strong></div>
                <div><span>Success</span><strong>{successCount}</strong></div>
                <div><span>Failed</span><strong>{failedCount}</strong></div>
                <div><span>Pending</span><strong>{pendingCount}</strong></div>
              </div>
              <div className="asteriskResultTableWrap" ref={deploymentStatusRef}>
                <table className="asteriskResultTable">
                  <thead>
                    <tr>
                      <th>Server Name</th>
                      <th>IP</th>
                      <th>Status</th>
                      <th>Message</th>
                      <th>Timestamp</th>
                    </tr>
                  </thead>
                  <tbody>
                    {deploymentResults.map((result) => (
                      <tr className={`asteriskResultRow ${result.status || 'pending'}`} key={`${result.server_id}-${result.started_at || result.timestamp || result.server_name}`}>
                        <td><strong>{result.server_name}</strong></td>
                        <td>{result.server_ip}</td>
                        <td><span className={`asteriskResultStatus ${result.status || 'pending'}`}>{deploymentStatusLabel(result.status)}</span></td>
                        <td>{result.message}</td>
                        <td>{formatDeploymentTime(result.finished_at || result.started_at || result.timestamp)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="asteriskDeploymentSummary">
                <div className="asteriskDeploymentSummaryCard">
                  <h3>Final Summary</h3>
                  <p>Total Servers: {deploymentResults.length}</p>
                  <p>Successful: {successCount}</p>
                  <p>Failed: {failedCount}</p>
                  {skippedCount > 0 && <p>Skipped: {skippedCount}</p>}
                </div>
                {failedRows.length > 0 && (
                  <div className="asteriskDeploymentSummaryCard failedList">
                    <h3>Failed Servers</h3>
                    {failedRows.map((item) => <p key={`failed-${item.server_id}`}>{item.server_name}{' -> '}{item.message}</p>)}
                  </div>
                )}
              </div>
            </div>
          )}

          <div className="asteriskSearchPanel">
            <div className="sectionHeader">
              <div><span className="eyebrow">Global File Search</span><h2>Global File Search</h2></div>
            </div>
            <form className="asteriskSearchForm" onSubmit={runGlobalFileSearch}>
              <label>
                <span>File Name Search</span>
                <input value={globalSearch.file_name} onChange={(event) => setGlobalSearchField('file_name', event.target.value)} placeholder="welcome" />
              </label>
              <label>
                <span>Search Type</span>
                <select value={globalSearch.search_type} onChange={(event) => setGlobalSearchField('search_type', event.target.value)}>
                  <option value="exact">Exact match</option>
                  <option value="contains">Contains</option>
                </select>
              </label>
              <label>
                <span>File Extension</span>
                <select value={globalSearch.extension_filter} onChange={(event) => setGlobalSearchField('extension_filter', event.target.value)}>
                  <option value=".wav">.wav</option>
                  <option value="all">All files</option>
                </select>
              </label>
              <button className="primary" disabled={!globalSearchReady || busy === 'global-search' || searchableServers.length === 0}><Search size={16} /> {busy === 'global-search' ? 'Searching...' : 'Search All Servers'}</button>
            </form>
            {(globalSearchResults.length > 0 || globalSearchSummary.total_servers > 0) && (
              <>
                <div className="asteriskDeploymentCounters asteriskSearchSummary">
                  <div><span>Total Servers</span><strong>{globalSearchSummary.total_servers}</strong></div>
                  <div><span>Completed</span><strong>{globalSearchSummary.completed}</strong></div>
                  <div><span>Found</span><strong>{globalSearchSummary.found}</strong></div>
                  <div><span>Failed</span><strong>{globalSearchSummary.failed}</strong></div>
                  <div><span>Timeout</span><strong>{globalSearchSummary.timeout}</strong></div>
                </div>
                <div className="tableWrap asteriskGlobalSearchTable" ref={globalSearchStatusRef}>
                  <table>
                    <thead>
                      <tr>
                        <th>Server</th>
                        <th>IP</th>
                        <th>Status</th>
                        <th>Message</th>
                        <th>Timestamp</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {globalSearchResults.map((row, index) => (
                        <tr className={`asteriskResultRow ${row.status || 'pending'}`} key={`${row.server_id}-${index}`}>
                          <td>{row.server_name}</td>
                          <td>{row.server_ip}</td>
                          <td><span className={`asteriskResultStatus ${row.status}`}>{globalStatusLabel(row.status)}</span></td>
                          <td>{row.message || '-'}</td>
                          <td>{formatDeploymentTime(row.finished_at || row.started_at || row.timestamp)}</td>
                          <td>{row.server_id ? <button type="button" onClick={() => {
                            const target = servers.find((server) => server.id === row.server_id);
                            if (target) {
                              setViewServerId(String(target.id));
                              setSelectedIds((current) => current.includes(String(target.id)) ? current : [...current, String(target.id)]);
                              viewFiles(target);
                            }
                          }}><FolderOpen size={15} /> View Server Files</button> : '-'}</td>
                        </tr>
                      ))}
                      {globalSearchResults.length === 0 && <tr><td colSpan="6" className="muted">No search results yet.</td></tr>}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>

          <div className="sectionHeader asteriskFilesHeader">
            <div><span className="eyebrow">Remote Files</span><h2>Sound Library</h2></div>
            <div className="asteriskFileTools">
              {selectedServers.length > 1 && (
                <select value={viewServerId} onChange={(event) => setViewServerId(event.target.value)}>
                  {selectedServers.map((server) => <option key={server.id} value={server.id}>{server.server_name}</option>)}
                </select>
              )}
              <div className="search terminalSearch"><Search size={16} /><input placeholder="Filter WAV files" value={fileSearch} onChange={(event) => setFileSearch(event.target.value)} /></div>
            </div>
          </div>
          <div className="tableWrap asteriskFilesTable">
            <table>
              <thead><tr><th>Filename</th><th>Size</th><th>Modified</th></tr></thead>
              <tbody>
                {filteredFiles.map((item) => (
                  <tr key={item.filename}>
                    <td><FileAudio size={15} /> {item.filename}</td>
                    <td>{formatBytes(item.size)}</td>
                    <td>{item.modified_at ? new Date(item.modified_at).toLocaleString() : '-'}</td>
                  </tr>
                ))}
                {filteredFiles.length === 0 && <tr><td colSpan="3" className="muted">No WAV files loaded. Select a server and use View Files.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
  );
}

const TERMINAL_TABS_STORAGE_KEY = 'noc360_terminal_tabs';
const TERMINAL_ACTIVE_TAB_STORAGE_KEY = 'noc360_terminal_active_tab';
const TERMINAL_TABS_MAX_BYTES = 50000;
const TERMINAL_TABS_MAX_COUNT = 12;

function clearStoredTerminalTabs() {
  try {
    localStorage.removeItem(TERMINAL_TABS_STORAGE_KEY);
    localStorage.removeItem(TERMINAL_ACTIVE_TAB_STORAGE_KEY);
  } catch {
    // Ignore browser storage access failures.
  }
}

function sanitizeStoredTerminalTab(tab) {
  if (!tab?.id || !tab?.connection?.id || !tab.connection.connection_name || !tab.connection.host_ip) return null;
  return {
    id: String(tab.id).slice(0, 80),
    name: String(tab.name || tab.connection.connection_name || 'SSH').slice(0, 80),
    connection: {
      id: tab.connection.id,
      connection_name: String(tab.connection.connection_name).slice(0, 100),
      host_ip: String(tab.connection.host_ip).slice(0, 100),
      ssh_port: Number(tab.connection.ssh_port || 22),
      username: String(tab.connection.username || '').slice(0, 80),
      status: tab.connection.status || 'Active',
    },
    status: tab.status === 'Connected' ? 'Reconnecting' : String(tab.status || 'Reconnecting').slice(0, 30),
    reconnectKey: Number(tab.reconnectKey || 0),
    clearKey: Number(tab.clearKey || 0),
    disconnectKey: 0,
    fullscreen: Boolean(tab.fullscreen),
  };
}

function loadStoredTerminalTabs() {
  try {
    const raw = localStorage.getItem(TERMINAL_TABS_STORAGE_KEY);
    if (!raw) return [];
    if (raw.length > TERMINAL_TABS_MAX_BYTES) {
      clearStoredTerminalTabs();
      return [];
    }
    const rows = JSON.parse(raw);
    if (!Array.isArray(rows)) {
      clearStoredTerminalTabs();
      return [];
    }
    return rows.map(sanitizeStoredTerminalTab).filter(Boolean).slice(-TERMINAL_TABS_MAX_COUNT);
  } catch {
    clearStoredTerminalTabs();
    return [];
  }
}

function loadStoredTerminalActiveTab(tabs) {
  try {
    const activeTabId = localStorage.getItem(TERMINAL_ACTIVE_TAB_STORAGE_KEY);
    if (activeTabId && tabs.some((tab) => tab.id === activeTabId)) return activeTabId;
    if (activeTabId) localStorage.removeItem(TERMINAL_ACTIVE_TAB_STORAGE_KEY);
    return tabs[tabs.length - 1]?.id || null;
  } catch {
    clearStoredTerminalTabs();
    return tabs[tabs.length - 1]?.id || null;
  }
}

function TerminalCenterPage({ user, visible = true }) {
  const canCreate = canDo(user, 'terminal', 'can_create');
  const canEdit = canDo(user, 'terminal', 'can_edit');
  const canDelete = canDo(user, 'terminal', 'can_delete');
  const isAdmin = user?.role === 'admin';
  const restoredTabsRef = useRef(null);
  const tabsSaveTimerRef = useRef(null);
  const [connections, setConnections] = useState([]);
  const [selectedConnectionIds, setSelectedConnectionIds] = useState([]);
  const [search, setSearch] = useState('');
  const [form, setForm] = useState({ connection_name: '', host_ip: '', ssh_port: 22, username: '', password: '', status: 'Active', notes: '' });
  const [editingId, setEditingId] = useState(null);
  const [vaultTab, setVaultTab] = useState('saved');
  const [tabs, setTabs] = useState(() => {
    const restored = loadStoredTerminalTabs();
    restoredTabsRef.current = restored;
    return restored;
  });
  const [activeTabId, setActiveTabId] = useState(() => loadStoredTerminalActiveTab(restoredTabsRef.current || []));
  const [revealed, setRevealed] = useState({});
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [commands, setCommands] = useState([]);
  const [history, setHistory] = useState([]);
  const [terminalActions, setTerminalActions] = useState({});
  const [commandForm, setCommandForm] = useState({ title: '', command: '', purpose: '', category: 'Custom', risk_level: 'Safe' });
  const activeTab = tabs.find((tab) => tab.id === activeTabId) || null;

  const loadConnections = async () => {
    setConnections(await request('/terminal/connections'));
  };
  const loadCommands = async () => setCommands(await request('/terminal/commands'));
  const loadHistory = async () => setHistory(await request('/terminal/command-history'));

  useEffect(() => {
    Promise.all([loadConnections(), loadCommands(), loadHistory()]).catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    setSelectedConnectionIds((current) => current.filter((id) => connections.some((connection) => String(connection.id) === String(id))));
  }, [connections]);

  useEffect(() => {
    if (tabsSaveTimerRef.current) window.clearTimeout(tabsSaveTimerRef.current);
    tabsSaveTimerRef.current = window.setTimeout(() => {
      try {
        const storedTabs = tabs
          .map(sanitizeStoredTerminalTab)
          .filter(Boolean)
          .slice(-TERMINAL_TABS_MAX_COUNT);
        localStorage.setItem(TERMINAL_TABS_STORAGE_KEY, JSON.stringify(storedTabs));
      } catch {
        clearStoredTerminalTabs();
      }
    }, 350);
    return () => {
      if (tabsSaveTimerRef.current) window.clearTimeout(tabsSaveTimerRef.current);
    };
  }, [tabs]);

  useEffect(() => {
    try {
      if (activeTabId) localStorage.setItem(TERMINAL_ACTIVE_TAB_STORAGE_KEY, activeTabId);
      else localStorage.removeItem(TERMINAL_ACTIVE_TAB_STORAGE_KEY);
    } catch {
      clearStoredTerminalTabs();
    }
  }, [activeTabId]);

  useEffect(() => {
    if (!activeTabId && tabs[0]) setActiveTabId(tabs[0].id);
    if (activeTabId && !tabs.some((tab) => tab.id === activeTabId)) setActiveTabId(tabs[tabs.length - 1]?.id || null);
  }, [tabs, activeTabId]);

  const setField = (field, value) => setForm((current) => ({ ...current, [field]: value }));
  const resetForm = () => {
    setEditingId(null);
    setForm({ connection_name: '', host_ip: '', ssh_port: 22, username: '', password: '', status: 'Active', notes: '' });
    setVaultTab('form');
  };

  const saveConnection = async (event) => {
    event.preventDefault();
    setError('');
    setMessage('');
    const isEditing = editingId !== null && editingId !== undefined;
    const payload = { ...form, ssh_port: Number(form.ssh_port || 22) };
    if (isEditing && !payload.password) delete payload.password;
    const saved = await request(isEditing ? `/terminal/connections/${editingId}` : '/terminal/connections', {
      method: isEditing ? 'PUT' : 'POST',
      body: JSON.stringify(payload),
    });
    setMessage(isEditing ? `SSH connection updated: ${saved.connection_name}` : `SSH connection added: ${saved.connection_name}`);
    setEditingId(null);
    setForm({ connection_name: '', host_ip: '', ssh_port: 22, username: '', password: '', status: 'Active', notes: '' });
    setVaultTab('saved');
    setSearch('');
    await loadConnections();
  };

  const editConnection = (connection) => {
    setEditingId(connection.id);
    setForm({
      connection_name: connection.connection_name || '',
      host_ip: connection.host_ip || '',
      ssh_port: connection.ssh_port || 22,
      username: connection.username || '',
      password: '',
      status: connection.status || 'Active',
      notes: connection.notes || '',
    });
    setVaultTab('form');
  };

  const deleteConnection = async (connection) => {
    if (!window.confirm(`Delete SSH connection ${connection.connection_name}?`)) return;
    await request(`/terminal/connections/${connection.id}`, { method: 'DELETE' });
    setTabs((rows) => rows.filter((tab) => tab.connection.id !== connection.id));
    setMessage('SSH connection deleted');
    await loadConnections();
  };

  const testConnection = async (connection) => {
    setError('');
    setMessage('');
    try {
      const result = await request(`/terminal/connections/${connection.id}/test`, { method: 'POST' });
      setMessage(result.message || 'SSH connection successful');
    } catch (err) {
      setError(err.message);
    }
  };

  const revealPassword = async (connection) => {
    if (revealed[connection.id]) {
      setRevealed((current) => ({ ...current, [connection.id]: null }));
      return;
    }
    try {
      const result = await request(`/terminal/connections/${connection.id}/password`);
      setRevealed((current) => ({ ...current, [connection.id]: result.password || '' }));
    } catch (err) {
      setError(err.message);
    }
  };

  const toggleConnectionSelection = (connectionId) => {
    const id = String(connectionId);
    setSelectedConnectionIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  };

  const selectAllConnections = () => {
    setSelectedConnectionIds(filteredConnections.map((connection) => String(connection.id)));
  };

  const clearConnectionSelection = () => {
    setSelectedConnectionIds([]);
  };

  const openConnectionSet = (connectionsToOpen, summaryLabel = 'terminal') => {
    const uniqueConnections = connectionsToOpen.filter((connection, index, list) => list.findIndex((item) => item.id === connection.id) === index);
    if (uniqueConnections.length === 0) {
      setMessage('No matching saved connections to open.');
      return;
    }
    let lastTabId = null;
    let openedCount = 0;
    setTabs((current) => {
      const next = [...current];
      const seed = Date.now();
      uniqueConnections.forEach((connection, index) => {
        const existing = next.find((tab) => String(tab.connection?.id) === String(connection.id));
        if (existing) {
          lastTabId = existing.id;
          return;
        }
        const tabId = `${connection.id}-${seed}-${index}`;
        next.push({ id: tabId, name: connection.connection_name, connection, status: 'Opening', reconnectKey: 0, clearKey: 0, disconnectKey: 0, fullscreen: false });
        lastTabId = tabId;
        openedCount += 1;
      });
      return next;
    });
    if (lastTabId) setActiveTabId(lastTabId);
    setMessage(openedCount > 0 ? `Opened ${openedCount} ${summaryLabel}${openedCount === 1 ? '' : 's'}` : 'All requested terminals are already open.');
  };

  const openTerminal = (connection) => {
    openConnectionSet([connection], 'terminal');
  };

  const openSelectedConnections = () => {
    openConnectionSet(
      connections.filter((connection) => selectedConnectionIds.includes(String(connection.id))),
      'terminal',
    );
  };

  const openAllActiveConnections = () => {
    openConnectionSet(
      connections.filter((connection) => String(connection.status || '').toLowerCase() === 'active'),
      'terminal',
    );
  };

  const updateTab = (tabId, patch) => {
    setTabs((current) => current.map((tab) => (tab.id === tabId ? { ...tab, ...patch } : tab)));
  };

  const closeTab = (tabId) => {
    updateTab(tabId, { disconnectKey: Date.now(), status: 'Disconnected' });
    window.setTimeout(() => {
      setTabs((current) => {
        const next = current.filter((tab) => tab.id !== tabId);
        if (activeTabId === tabId) setActiveTabId(next[next.length - 1]?.id || null);
        return next;
      });
    }, 80);
  };

  const disconnectTab = (tab) => {
    updateTab(tab.id, { disconnectKey: Date.now(), status: 'Disconnected' });
  };

  const renameTab = (tab) => {
    const name = window.prompt('Rename terminal tab', tab.name);
    if (name) updateTab(tab.id, { name });
  };

  const copyTerminalCommand = async (command) => {
    await copyPlainText(command);
    setMessage('Command copied');
  };

  const sendCommandToActiveTerminal = async (command, run = false) => {
    if (!activeTabId) {
      setError('Open a terminal tab first');
      return;
    }
    const risk = commandRisk(command);
    if (run && risk === 'Dangerous' && !window.confirm('This command is dangerous. Run it anyway?')) return;
    setTerminalActions((current) => ({
      ...current,
      [activeTabId]: { id: Date.now(), command, run },
    }));
    if (run && activeTab?.connection?.id) {
      await saveTerminalHistory(activeTab.connection.id, command);
      await loadHistory();
    }
  };

  const saveCommand = async (event) => {
    event.preventDefault();
    await request('/terminal/commands', { method: 'POST', body: JSON.stringify(commandForm) });
    setCommandForm({ title: '', command: '', purpose: '', category: 'Custom', risk_level: 'Safe' });
    setMessage('Command saved');
    await loadCommands();
  };

  const filteredConnections = connections.filter((connection) => {
    const haystack = `${connection.connection_name} ${connection.host_ip} ${connection.username} ${connection.notes || ''}`.toLowerCase();
    return haystack.includes(search.toLowerCase());
  });
  const selectedConnectionsCount = selectedConnectionIds.length;
  const activeConnectionCount = connections.filter((item) => String(item.status || '').toLowerCase() === 'active').length;
  const connectionStripClass = (status) => {
    const normalized = String(status || '').toLowerCase();
    if (normalized === 'active') return 'online';
    if (normalized === 'inactive') return 'offline';
    return 'unknown';
  };
  const duplicateNameCount = form.connection_name
    ? connections.filter((connection) => connection.connection_name?.trim().toLowerCase() === form.connection_name.trim().toLowerCase() && connection.id !== editingId).length
    : 0;
  return (
    <section className="terminalCenter">
      <div className="cards managementCards">
        <div className="metric"><span>Saved Connections</span><strong>{connections.length}</strong></div>
        <div className="metric payment"><span>Active Records</span><strong>{activeConnectionCount}</strong></div>
        <div className="metric revenue"><span>Open Tabs</span><strong>{tabs.length}</strong></div>
        <div className="metric"><span>Focused Host</span><strong>{activeTab?.connection?.host_ip || '-'}</strong></div>
      </div>

      <div className="terminalLayout">
        <aside className="panel terminalConnections">
          <div className="sectionHeader">
            <div><span className="eyebrow">SSH Vault</span><h2>Connections</h2></div>
            <div className="actions">
              {editingId && <button onClick={resetForm}><Plus size={16} /> New</button>}
              <button onClick={loadConnections}><RefreshCcw size={16} /></button>
            </div>
          </div>
          {message && <div className="toastSuccess">{message}</div>}
          {error && <div className="error"><AlertTriangle size={16} /> {error}</div>}
          <div className="terminalVaultTabs">
            <button type="button" className={vaultTab === 'saved' ? 'active' : ''} onClick={() => setVaultTab('saved')}>Saved Connections</button>
            {(canCreate || editingId) && (
              <button type="button" className={vaultTab === 'form' ? 'active' : ''} onClick={() => setVaultTab('form')}>
                {editingId ? 'Update Connection' : 'Add / Update Connection'}
              </button>
            )}
          </div>
          {vaultTab === 'saved' && (
            <>
              <div className="terminalConnectionTools">
                <div className="search terminalSearch"><Search size={16} /><input placeholder="Search servers" value={search} onChange={(event) => setSearch(event.target.value)} /></div>
                <div className="terminalConnectionBulkBar">
                  <strong>{selectedConnectionsCount} selected</strong>
                  <div className="actions">
                    <button type="button" onClick={selectAllConnections} disabled={filteredConnections.length === 0}>Select All</button>
                    <button type="button" onClick={clearConnectionSelection} disabled={selectedConnectionsCount === 0}>Clear Selection</button>
                    <button type="button" onClick={openSelectedConnections} disabled={selectedConnectionsCount === 0}><Play size={15} /> Open Selected</button>
                    <button type="button" className="primary" onClick={openAllActiveConnections} disabled={activeConnectionCount === 0}><Play size={15} /> Open All Active</button>
                  </div>
                </div>
              </div>
              <div className="terminalConnectionList">
                {filteredConnections.map((connection) => (
                  <div className="terminalConnectionCard" key={connection.id}>
                    <div className="terminalConnectionCardHeader">
                      <div className="terminalConnectionTopRow">
                        <label className="terminalConnectionSelect">
                          <input type="checkbox" checked={selectedConnectionIds.includes(String(connection.id))} onChange={() => toggleConnectionSelection(connection.id)} />
                        </label>
                        <div className="terminalConnectionIdentity">
                          <strong title={connection.connection_name}>{connection.connection_name}</strong>
                        </div>
                      </div>
                      <StatusPill value={connection.status} />
                    </div>
                    <div className="terminalConnectionInfoRow">
                      <div className="terminalConnectionInfoItem">
                        <small>Host/IP</small>
                        <span title={connection.host_ip}>{connection.host_ip}</span>
                      </div>
                      <div className="terminalConnectionInfoItem">
                        <small>Username</small>
                        <span title={connection.username || '-'}>{connection.username || '-'}</span>
                      </div>
                      <div className="terminalConnectionInfoItem">
                        <small>Port</small>
                        <span>{connection.ssh_port || 22}</span>
                      </div>
                    </div>
                    <div className="terminalConnectionAuxRow">
                      <small>{revealed[connection.id] ? `Password: ${revealed[connection.id]}` : connection.has_password ? 'Password: ********' : 'Password: not saved'}</small>
                      {connection.notes && <p title={connection.notes}>{connection.notes}</p>}
                    </div>
                    <div className="terminalConnectionActions">
                      <button className="primary" onClick={() => openTerminal(connection)}><Play size={15} /> Open</button>
                      <button onClick={() => testConnection(connection)}>Test</button>
                      {isAdmin && <button onClick={() => revealPassword(connection)}>{revealed[connection.id] ? <EyeOff size={15} /> : <Eye size={15} />} Reveal</button>}
                      {canEdit && <button onClick={() => editConnection(connection)}><Edit3 size={15} /> Edit</button>}
                      {canDelete && <button className="danger" onClick={() => deleteConnection(connection)}><Trash2 size={15} /> Delete</button>}
                    </div>
                  </div>
                ))}
                {filteredConnections.length === 0 && <div className="terminalConnectionEmpty muted">No saved connections match this search.</div>}
              </div>
            </>
          )}

          {vaultTab === 'form' && (canCreate || editingId) && (
            <form className="terminalForm" onSubmit={saveConnection}>
              <label><span>Connection Name</span><input value={form.connection_name} onChange={(event) => setField('connection_name', event.target.value)} placeholder="Asterisk PBX" /></label>
              <label><span>Host/IP</span><input value={form.host_ip} onChange={(event) => setField('host_ip', event.target.value)} placeholder="203.0.113.10" /></label>
              <label><span>Port</span><input type="number" min="1" max="65535" value={form.ssh_port} onChange={(event) => setField('ssh_port', event.target.value)} /></label>
              <label><span>Username</span><input value={form.username} onChange={(event) => setField('username', event.target.value)} placeholder="root" /></label>
              <label><span>Password</span><input type="password" value={form.password} onChange={(event) => setField('password', event.target.value)} placeholder={editingId ? 'Leave blank to keep saved password' : 'SSH password'} /></label>
              <label><span>Status</span><select value={form.status} onChange={(event) => setField('status', event.target.value)}>{statuses.map((status) => <option key={status}>{status}</option>)}</select></label>
              <label><span>Notes</span><textarea value={form.notes} onChange={(event) => setField('notes', event.target.value)} placeholder="Server role, provider, handover notes" /></label>
              {duplicateNameCount > 0 && <div className="terminalDuplicateNotice">Name already exists. It will still save as a separate SSH connection.</div>}
              <div className="formActions">
                <button className="primary"><Plus size={16} /> {editingId ? 'Update Connection' : 'Add Connection'}</button>
                {editingId && <button type="button" onClick={resetForm}>Cancel Edit</button>}
              </div>
            </form>
          )}
        </aside>

        <div className={`panel terminalWorkspace ${activeTab?.fullscreen ? 'terminalFullscreen' : ''}`}>
          <div className="terminalTabs">
            {tabs.length === 0 ? <span className="muted">Open a saved SSH connection to start a terminal session.</span> : tabs.map((tab) => (
              <button key={tab.id} className={tab.id === activeTabId ? 'active' : ''} onClick={() => setActiveTabId(tab.id)}>
                <TerminalIcon size={15} />
                <span>{tab.name}</span>
                <small>{tab.status}</small>
                <i onClick={(event) => { event.stopPropagation(); closeTab(tab.id); }}><X size={13} /></i>
              </button>
            ))}
          </div>

          {activeTab && (
            <div className="terminalToolbar">
              <strong>{activeTab.connection.username}@{activeTab.connection.host_ip}</strong>
              <button onClick={() => renameTab(activeTab)}>Rename</button>
              <button onClick={() => updateTab(activeTab.id, { reconnectKey: activeTab.reconnectKey + 1, status: 'Reconnecting' })}>Reconnect</button>
              <button onClick={() => disconnectTab(activeTab)}>Disconnect</button>
              <button onClick={() => updateTab(activeTab.id, { clearKey: activeTab.clearKey + 1 })}>Clear</button>
              <button onClick={() => updateTab(activeTab.id, { fullscreen: !activeTab.fullscreen })}>{activeTab.fullscreen ? 'Exit Fullscreen' : 'Fullscreen'}</button>
            </div>
          )}

          <div className="terminalPaneStack">
            {tabs.map((tab) => (
              <SSHTerminalPane
                key={tab.id}
                tab={tab}
                active={visible && tab.id === activeTabId}
                commandAction={terminalActions[tab.id]}
                onStatus={(status) => updateTab(tab.id, { status })}
                onHistorySaved={loadHistory}
              />
            ))}
          </div>
        </div>

        <CommandLibraryPanel
          commands={commands}
          history={history}
          canCreate={canCreate}
          canDelete={canDelete}
          isAdmin={isAdmin}
          commandForm={commandForm}
          setCommandForm={setCommandForm}
          onSaveCommand={saveCommand}
          onRefresh={() => Promise.all([loadCommands(), loadHistory()])}
          onCopy={copyTerminalCommand}
          onInsert={(command) => sendCommandToActiveTerminal(command, false)}
          onRun={(command) => sendCommandToActiveTerminal(command, true)}
          onDeleteCommand={async (command) => {
            await request(`/terminal/commands/${command.id}`, { method: 'DELETE' });
            await loadCommands();
          }}
        />
      </div>
    </section>
  );
}

const PersistentTerminalCenterPage = React.memo(TerminalCenterPage);

function SSHTerminalPane({ tab, active, commandAction, onStatus, onHistorySaved }) {
  const containerRef = useRef(null);
  const terminalRef = useRef(null);
  const fitRef = useRef(null);
  const socketRef = useRef(null);
  const inputBufferRef = useRef('');
  const lastActionIdRef = useRef(null);

  const rememberCommand = async (command) => {
    const cleaned = String(command || '').trim();
    if (!cleaned) return;
    await saveTerminalHistory(tab.connection.id, cleaned);
    onHistorySaved?.();
  };

  const trackInput = (data) => {
    if (!data || data.includes('\u001b')) return;
    for (const char of data) {
      if (char === '\r' || char === '\n') {
        const command = inputBufferRef.current.trim();
        inputBufferRef.current = '';
        if (command) rememberCommand(command).catch(() => {});
      } else if (char === '\u007f' || char === '\b') {
        inputBufferRef.current = inputBufferRef.current.slice(0, -1);
      } else if (char === '\u0003') {
        inputBufferRef.current = '';
      } else if (char >= ' ') {
        inputBufferRef.current += char;
      }
    }
  };

  useEffect(() => {
    if (!containerRef.current) return undefined;
    const terminal = new XTerm({
      cursorBlink: true,
      convertEol: true,
      fontFamily: 'JetBrains Mono, Consolas, "Cascadia Mono", monospace',
      fontSize: 14,
      theme: {
        background: '#020713',
        foreground: '#d7fff4',
        cursor: '#00e5ff',
        selectionBackground: '#164e63',
        black: '#020617',
        red: '#ff4d4d',
        green: '#00ff9c',
        yellow: '#ffc857',
        blue: '#38bdf8',
        magenta: '#a78bfa',
        cyan: '#00e5ff',
        white: '#f8fbff',
      },
    });
    const fitAddon = new FitAddon();
    terminal.loadAddon(fitAddon);
    terminal.open(containerRef.current);
    terminalRef.current = terminal;
    fitRef.current = fitAddon;
    terminal.writeln('NOC360 SSH Terminal Center');
    terminal.writeln(`Opening ${tab.connection.connection_name}...`);

    const socket = new WebSocket(websocketEndpoint(`/terminal/ws/${tab.connection.id}?tab_id=${encodeURIComponent(tab.id)}`));
    socketRef.current = socket;

    const fitAndResize = () => {
      try {
        fitAddon.fit();
        if (socket.readyState === WebSocket.OPEN) socket.send(`__resize__:${terminal.cols}:${terminal.rows}`);
      } catch (error) {
        // xterm fit can fail while the pane is hidden; it will retry when focused.
      }
    };

    socket.onopen = () => {
      onStatus('Connected');
      window.setTimeout(fitAndResize, 60);
      if (active) terminal.focus();
    };
    socket.onmessage = (event) => terminal.write(event.data);
    socket.onerror = () => {
      onStatus('Error');
      terminal.writeln('\r\n[connection error]');
    };
    socket.onclose = (event) => {
      const status = event.code === 4000 ? 'Disconnected' : event.code === 4001 ? 'Idle Timeout' : event.code === 4002 ? 'Reconnecting' : 'Disconnected';
      onStatus(status);
      terminal.writeln(`\r\n[${status.toLowerCase()}]`);
    };
    const disposable = terminal.onData((data) => {
      trackInput(data);
      if (socket.readyState === WebSocket.OPEN) socket.send(data);
    });
    window.addEventListener('resize', fitAndResize);
    window.setTimeout(fitAndResize, 120);

    return () => {
      window.removeEventListener('resize', fitAndResize);
      disposable.dispose();
      if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) socket.close(4002, 'Terminal pane detached');
      terminal.dispose();
    };
  }, [tab.connection.id, tab.reconnectKey]);

  useEffect(() => {
    if (!tab.disconnectKey) return;
    try {
      if (socketRef.current?.readyState === WebSocket.OPEN || socketRef.current?.readyState === WebSocket.CONNECTING) {
        socketRef.current.close(4000, 'User disconnected');
      }
    } catch (error) {
      // The socket may already be closed.
    }
  }, [tab.disconnectKey]);

  useEffect(() => {
    if (!active || !terminalRef.current || !fitRef.current) return;
    window.setTimeout(() => {
      try {
        fitRef.current.fit();
        terminalRef.current.focus();
        if (socketRef.current?.readyState === WebSocket.OPEN) {
          socketRef.current.send(`__resize__:${terminalRef.current.cols}:${terminalRef.current.rows}`);
        }
      } catch (error) {
        // Ignore transient fit failures while layout is settling.
      }
    }, 80);
  }, [active]);

  useEffect(() => {
    if (tab.clearKey && terminalRef.current) terminalRef.current.clear();
  }, [tab.clearKey]);

  useEffect(() => {
    if (!commandAction || commandAction.id === lastActionIdRef.current) return;
    lastActionIdRef.current = commandAction.id;
    const data = `${commandAction.command}${commandAction.run ? '\r' : ''}`;
    if (!commandAction.run) inputBufferRef.current += commandAction.command;
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(data);
      terminalRef.current?.focus();
    } else {
      terminalRef.current?.writeln('\r\n[terminal not connected]');
    }
  }, [commandAction]);

  return <div className={`sshTerminalPane ${active ? 'active' : ''}`} ref={containerRef} />;
}

const terminalDangerWords = ['rm -rf', 'reboot', 'shutdown', 'mkfs', 'dd ', 'iptables flush', 'ufw reset', 'systemctl stop'];
const terminalSecretWords = ['password', 'passwd', 'token', 'secret', 'key'];

function commandRisk(command, riskLevel = '') {
  const lowered = String(command || '').toLowerCase();
  if (terminalDangerWords.some((word) => lowered.includes(word))) return 'Dangerous';
  return riskLevel || 'Safe';
}

function commandHasSecret(command) {
  const lowered = String(command || '').toLowerCase();
  return terminalSecretWords.some((word) => lowered.includes(word));
}

async function saveTerminalHistory(connectionId, command) {
  const cleaned = String(command || '').trim();
  if (!cleaned || commandHasSecret(cleaned)) return null;
  return request('/terminal/command-history', {
    method: 'POST',
    body: JSON.stringify({ connection_id: connectionId, command: cleaned }),
  }).catch(() => null);
}

async function copyPlainText(text) {
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
}

function CommandLibraryPanel({ commands, history, canCreate, canDelete, isAdmin, commandForm, setCommandForm, onSaveCommand, onRefresh, onCopy, onInsert, onRun, onDeleteCommand }) {
  const [activeTab, setActiveTab] = useState('saved');
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [details, setDetails] = useState(null);
  const categories = useMemo(() => [...new Set(commands.map((command) => command.category).filter(Boolean))].sort(), [commands]);
  const filteredCommands = commands.filter((command) => {
    const haystack = `${command.title} ${command.command} ${command.purpose || ''} ${command.category || ''}`.toLowerCase();
    return (!search || haystack.includes(search.toLowerCase())) && (!category || command.category === category);
  });
  const filteredHistory = history.filter((item) => `${item.command} ${item.connection_name || ''} ${item.username || ''}`.toLowerCase().includes(search.toLowerCase()));
  const updateForm = (field, value) => setCommandForm((current) => ({ ...current, [field]: value }));

  const CommandActions = ({ command, riskLevel }) => (
    <div className="actions commandActions">
      <button onClick={() => onCopy(command)}><Copy size={14} /> Copy</button>
      <button onClick={() => onInsert(command)}><Send size={14} /> Insert</button>
      {isAdmin && <button className={commandRisk(command, riskLevel) === 'Dangerous' ? 'danger' : ''} onClick={() => onRun(command)}>Run</button>}
    </div>
  );

  return (
    <aside className="panel terminalCommands">
      <div className="sectionHeader">
        <div><span className="eyebrow">Command Library</span><h2>Commands</h2></div>
        <button onClick={onRefresh}><RefreshCcw size={16} /></button>
      </div>

      <div className="commandTabs">
        <button className={activeTab === 'saved' ? 'active' : ''} onClick={() => setActiveTab('saved')}>Saved Commands</button>
        <button className={activeTab === 'history' ? 'active' : ''} onClick={() => setActiveTab('history')}>History</button>
      </div>

      <div className="search terminalSearch"><Search size={16} /><input placeholder="Search commands" value={search} onChange={(event) => setSearch(event.target.value)} /></div>
      {activeTab === 'saved' && <select value={category} onChange={(event) => setCategory(event.target.value)}><option value="">All categories</option>{categories.map((item) => <option key={item}>{item}</option>)}</select>}

      {activeTab === 'saved' && canCreate && (
        <form className="commandForm" onSubmit={onSaveCommand}>
          <input placeholder="Command title" value={commandForm.title} onChange={(event) => updateForm('title', event.target.value)} />
          <textarea placeholder="Command" value={commandForm.command} onChange={(event) => updateForm('command', event.target.value)} />
          <input placeholder="Purpose" value={commandForm.purpose} onChange={(event) => updateForm('purpose', event.target.value)} />
          <div className="commandFormGrid">
            <input placeholder="Category" value={commandForm.category} onChange={(event) => updateForm('category', event.target.value)} />
            <select value={commandForm.risk_level} onChange={(event) => updateForm('risk_level', event.target.value)}><option>Safe</option><option>Medium</option><option>Dangerous</option></select>
          </div>
          <button className="primary"><Plus size={15} /> Save Command</button>
        </form>
      )}

      <div className="commandList">
        {activeTab === 'saved' && filteredCommands.map((item) => (
          <div className="commandCard" key={item.id}>
            <div className="commandCardHeader">
              <strong>{item.title}</strong>
              <span className={`riskBadge ${commandRisk(item.command, item.risk_level).toLowerCase()}`}>{commandRisk(item.command, item.risk_level)}</span>
            </div>
            <code>{item.command}</code>
            <p>{item.purpose || 'No purpose added.'}</p>
            <div className="commandMeta"><span>{item.category || 'General'}</span>{item.is_default && <span>Default</span>}</div>
            <CommandActions command={item.command} riskLevel={item.risk_level} />
            <div className="actions commandActions">
              <button onClick={() => setDetails(item)}><Eye size={14} /> Details</button>
              {canDelete && !item.is_default && <button className="danger" onClick={() => onDeleteCommand(item)}><Trash2 size={14} /> Delete</button>}
            </div>
          </div>
        ))}

        {activeTab === 'history' && filteredHistory.map((item) => (
          <div className="commandCard historyCard" key={item.id}>
            <div className="commandCardHeader">
              <strong>{item.connection_name || 'Terminal'}</strong>
              <small>{item.created_at ? new Date(item.created_at).toLocaleString() : '-'}</small>
            </div>
            <code>{item.command}</code>
            <div className="commandMeta"><span>{item.username || '-'}</span></div>
            <CommandActions command={item.command} riskLevel={commandRisk(item.command)} />
          </div>
        ))}

        {activeTab === 'saved' && filteredCommands.length === 0 && <p className="muted">No commands found.</p>}
        {activeTab === 'history' && filteredHistory.length === 0 && <p className="muted">No command history yet.</p>}
      </div>

      {details && (
        <div className="modalBackdrop modal-overlay">
          <div className="modal modal-box commandDetailModal">
            <div className="modalHeader"><h2>{details.title}</h2><button className="iconButton" onClick={() => setDetails(null)}><X size={18} /></button></div>
            <div className="commandDetailGrid">
              <label><span>Command</span><code>{details.command}</code></label>
              <label><span>Purpose</span><p>{details.purpose || 'No purpose added.'}</p></label>
              <label><span>When to use</span><p>Use during {details.category || 'general'} checks, incident handling, or routine NOC troubleshooting.</p></label>
              <label><span>Risk level</span><span className={`riskBadge ${commandRisk(details.command, details.risk_level).toLowerCase()}`}>{commandRisk(details.command, details.risk_level)}</span></label>
            </div>
            <CommandActions command={details.command} riskLevel={details.risk_level} />
          </div>
        </div>
      )}
    </aside>
  );
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

function ledgerBalanceText(value) {
  const amount = Number(value || 0);
  return amount < 0 ? `Advance ${inr(Math.abs(amount))}` : inr(amount);
}

function clientLedgerCsvRows(rows) {
  return rows.map((row) => ({
    Date: row.date,
    'Invoice No / Reference': row.reference,
    Description: row.description,
    'Debit (DR)': row.debit || '',
    'Credit (CR)': row.credit || '',
    Balance: row.balance,
    'Download PDF': row.invoice_id ? `weekly-invoice-${row.invoice_id}.pdf` : '',
  }));
}

function ClientInvoiceLedgerView({ user, pageKey = 'my_reports', title = 'Client Ledger' }) {
  const canExport = canDo(user, pageKey, 'can_export');
  const [filters, setFilters] = useState({ date_from: '', date_to: '', type: 'All' });
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const load = async (activeFilters = filters) => {
    setLoading(true);
    setError('');
    try {
      setRows(await request(`/reports/client-ledger${makeQuery(activeFilters)}`));
    } catch (err) {
      setError(err.message);
      setRows([]);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, []);
  const exportLedger = () => exportRows('client-invoice-ledger.csv', clientLedgerCsvRows(rows));
  return (
    <section>
      <div className="sectionTitle">
        <div>
          <span className="eyebrow">Client Portal</span>
          <h2>{title}</h2>
        </div>
      </div>
      <div className="reportFilters">
        <label className="fieldLabel">From Date<input type="date" value={filters.date_from} onChange={(event) => setFilters({ ...filters, date_from: event.target.value })} /></label>
        <label className="fieldLabel">To Date<input type="date" value={filters.date_to} onChange={(event) => setFilters({ ...filters, date_to: event.target.value })} /></label>
        <label className="fieldLabel">Type<select value={filters.type} onChange={(event) => setFilters({ ...filters, type: event.target.value })}>
          <option>All</option>
          <option>Invoice</option>
          <option>Payment</option>
          <option>Adjustment</option>
        </select></label>
        <button onClick={() => load(filters)}><RefreshCcw size={16} /> Run</button>
        {canExport && <button onClick={exportLedger} disabled={!rows.length}><Download size={16} /> Export CSV</button>}
      </div>
      {error && <div className="error"><AlertTriangle size={16} /> {error}</div>}
      <div className="tableWrap weeklyInvoiceTable">
        <table>
          <thead><tr><th>Date</th><th>Invoice No / Reference</th><th>Description</th><th>Debit (DR)</th><th>Credit (CR)</th><th>Balance</th><th>Download PDF</th></tr></thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${row.type}-${row.reference}-${row.date}`} className={row.credit ? 'creditRow' : 'debitRow'}>
                <td>{row.date}</td>
                <td>{row.reference}</td>
                <td>{row.description}</td>
                <td>{row.debit ? inr(row.debit) : '-'}</td>
                <td className="creditText">{row.credit ? inr(row.credit) : '-'}</td>
                <td className={row.balance > 0 ? 'outstandingText' : 'okText'}>{ledgerBalanceText(row.balance)}</td>
                <td>{row.invoice_id ? <button onClick={() => downloadWeeklyInvoicePdf({ id: row.invoice_id })}><Download size={15} /> PDF</button> : <span className="muted">-</span>}</td>
              </tr>
            ))}
            {!loading && rows.length === 0 && <tr><td colSpan="7" className="muted">No saved invoices, payments, or adjustments found.</td></tr>}
            {loading && <tr><td colSpan="7" className="muted">Loading ledger...</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  );
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

function RoutingMediaRow({ row, routingRows = [], mediaPortals, rtngs, saving, onSave, canEdit }) {
  const [form, setForm] = useState(row);
  useEffect(() => setForm(row), [row]);
  const key = `routing-${row.routing_gateway_id || row.rtng_vos_id || row.gateway_name}`;
  const usedMedia = buildUsedMediaMap(routingRows, form.gateway_name);

  const update = (field, value) => {
    const next = { ...form, [field]: value };
    if (field === 'gateway_name') {
      const gateway = rtngs.find((item) => item.portal_type === value || String(item.id) === String(value));
      next.gateway_ip = gateway?.server_ip || '';
      next.routing_gateway_id = gateway?.id || null;
      next.rtng_vos_id = gateway?.id || null;
      next.gateway_name = gateway?.portal_type || value;
    }
    if (field === 'media_1_name') {
      const media = mediaPortals.find((item) => item.portal_type === value || String(item.id) === String(value));
      next.media_1_ip = media?.server_ip || '';
      next.media1_ip = media?.server_ip || '';
      next.media_1_portal_id = media?.id || null;
      next.media1_vos_id = media?.id || null;
      next.media_1_name = media?.portal_type || value;
      next.media1_name = media?.portal_type || value;
    }
    if (field === 'media_2_name') {
      const media = mediaPortals.find((item) => item.portal_type === value || String(item.id) === String(value));
      next.media_2_ip = media?.server_ip || '';
      next.media2_ip = media?.server_ip || '';
      next.media_2_portal_id = media?.id || null;
      next.media2_vos_id = media?.id || null;
      next.media_2_name = media?.portal_type || value;
      next.media2_name = media?.portal_type || value;
    }
    setForm(next);
  };
  const alerts = form.validation_alerts || [];

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
      <td>{canEdit ? <MediaSelect value={form.media_1_name || form.media1_name || ''} mediaPortals={mediaPortals} usedBy={usedMedia} onChange={(value) => update('media_1_name', value)} /> : form.media_1_name || form.media1_name || '-'}</td>
      <td>{form.media_1_ip || form.media1_ip || <span className="missing">Missing</span>}</td>
      <td>{canEdit ? <MediaSelect value={form.media_2_name || form.media2_name || ''} mediaPortals={mediaPortals} usedBy={usedMedia} onChange={(value) => update('media_2_name', value)} /> : form.media_2_name || form.media2_name || '-'}</td>
      <td>{form.media_2_ip || form.media2_ip || <span className="missing">Missing</span>}</td>
      <td>{canEdit ? <input value={form.carrier_ip || ''} onChange={(event) => update('carrier_ip', event.target.value)} /> : form.carrier_ip || '-'}</td>
      <td>{canEdit ? <input value={form.ports || ''} onChange={(event) => update('ports', event.target.value)} /> : form.ports || '-'}</td>
      <td>{canEdit ? <input value={form.vendor || form.vendor_name || ''} onChange={(event) => update('vendor', event.target.value)} /> : form.vendor || form.vendor_name || '-'}</td>
      <td>
        {canEdit ? <select value={form.status || 'Active'} onChange={(event) => update('status', event.target.value)}>
          {statuses.map((status) => <option key={status}>{status}</option>)}
        </select> : <StatusPill value={form.status} />}
        {alerts.map((alert) => <div className="duplicateText" key={alert}>{alert}</div>)}
      </td>
      <td>
        {canEdit ? <button onClick={() => onSave(key, '/management/routing-media-assignments', {
          gateway_name: form.gateway_name,
          routing_gateway_id: form.routing_gateway_id || form.rtng_vos_id || null,
          rtng_vos_id: form.rtng_vos_id || null,
          media_1_name: form.media_1_name || form.media1_name || null,
          media_1_portal_id: form.media_1_portal_id || form.media1_vos_id || null,
          media1_name: form.media_1_name || form.media1_name || null,
          media1_vos_id: form.media_1_portal_id || form.media1_vos_id || null,
          media_2_name: form.media_2_name || form.media2_name || null,
          media_2_portal_id: form.media_2_portal_id || form.media2_vos_id || null,
          media2_name: form.media_2_name || form.media2_name || null,
          media2_vos_id: form.media_2_portal_id || form.media2_vos_id || null,
          carrier_ip: form.carrier_ip || null,
          ports: form.ports || null,
          vendor: form.vendor || form.vendor_name || null,
          vendor_name: form.vendor || form.vendor_name || null,
          status: form.status || 'Active',
        })}>{saving === key ? 'Saving...' : 'Save'}</button> : '-'}
      </td>
    </tr>
  );
}

function buildUsedMediaMap(routingRows = [], currentGateway = '') {
  return routingRows.reduce((used, row) => {
    if ((row.status || 'Active') !== 'Active') return used;
    if ((row.gateway_name || '') === currentGateway) return used;
    [row.media_1_name || row.media1_name, row.media_2_name || row.media2_name].filter(Boolean).forEach((name) => {
      used[name] = row.gateway_name || 'another gateway';
    });
    return used;
  }, {});
}

function MediaSelect({ value, mediaPortals, usedBy = {}, onChange }) {
  return (
    <select value={value} onChange={(event) => onChange(event.target.value)}>
      <option value="">Unassigned</option>
      {mediaPortals.map((portal) => {
        const assignedTo = usedBy[portal.portal_type];
        const disabled = Boolean(assignedTo) && portal.portal_type !== value;
        return <option key={portal.id} value={portal.portal_type} disabled={disabled}>{portal.portal_type} - {portal.server_ip}{disabled ? ` (Already Assigned to ${assignedTo})` : ''}</option>;
      })}
    </select>
  );
}

function ClientSelect({ value, clients, onChange, placeholder = 'Unassigned' }) {
  return (
    <select value={value || ''} onChange={(event) => onChange(event.target.value)}>
      <option value="">{placeholder}</option>
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
  request('/activity-logs/track', {
    method: 'POST',
    body: JSON.stringify({ action: 'export_report', module: 'reports', description: `Exported ${filename}` }),
  }).catch(() => {});
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
  return (
    <section>
      <div className="customerHeader">
        <h2>{user.username.toUpperCase()} Weekly Invoice Overview</h2>
        <span className="rolePill">customer scoped</span>
      </div>
      <WeeklyInvoicePanel user={user} clients={[]} canCreate={false} canExport={canDo(user, 'my_ledger', 'can_export')} />
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

const DEFAULT_DAILY_EXPECTED_BILLING_INR = 800000;

function weeklyInvoiceStatus(actual, expected) {
  const expectedValue = Number(expected || 0);
  const actualValue = Number(actual || 0);
  if (expectedValue <= 0) return actualValue >= 0 ? 'Green' : 'Red';
  const ratio = actualValue / expectedValue;
  if (ratio >= 1) return 'Green';
  if (ratio >= 0.8) return 'Yellow';
  return 'Red';
}

function weeklyStatusClass(status) {
  return `weeklyStatus ${String(status || '').toLowerCase()}`;
}

function currentWeekDates() {
  const today = new Date();
  const start = new Date(today);
  start.setDate(today.getDate() - ((today.getDay() + 6) % 7));
  const end = new Date(start);
  end.setDate(start.getDate() + 4);
  return { start: start.toISOString().slice(0, 10), end: end.toISOString().slice(0, 10) };
}

function weeklyInvoiceMath(form) {
  const activeDays = Number(form.active_billing_days || 0);
  const dailyExpected = Number(form.daily_expected_billing || DEFAULT_DAILY_EXPECTED_BILLING_INR);
  const billingCharges = Number(form.billing_charges || 0);
  const dataCharges = Number(form.data_charges || 0);
  const otherCharges = Number(form.other_charges || 0);
  const payments = Number(form.payment_amount || 0);
  const adjustments = Number(form.adjustment_amount || 0);
  const openingBalance = Number(form.opening_balance || 0);
  const paymentsAfterWeek = Number(form.payments_after_week || 0);
  const profitPercent = Number(form.profit_percent || 0);
  const profitAmount = billingCharges * profitPercent / 100;
  const actual = billingCharges + profitAmount;
  const expected = activeDays * dailyExpected;
  const currentWeekPayable = actual + dataCharges + otherCharges;
  const currentWeekBilling = currentWeekPayable;
  const totalPaymentsTillToday = Number(form.total_payments_till_today ?? payments + paymentsAfterWeek);
  const ledgerBalance = Number(form.ledger_balance ?? openingBalance + currentWeekPayable - payments + adjustments);
  const finalOutstanding = Number(form.final_outstanding ?? ledgerBalance);
  return {
    expected,
    billingCharges,
    dataCharges,
    otherCharges,
    payments,
    adjustments,
    openingBalance,
    currentWeekBilling,
    currentWeekPayable,
    paymentsThisWeek: payments,
    paymentsAfterWeek,
    totalPaymentsTillToday,
    ledgerBalance,
    finalOutstanding,
    advanceRemaining: Math.max(0, -finalOutstanding),
    profitPercent,
    profitAmount,
    difference: actual - expected,
    actualUsage: actual,
    finalPayable: finalOutstanding,
    status: weeklyInvoiceStatus(actual, expected),
  };
}

function weeklyLineCategory(line) {
  return String(line?.charge_type || line?.label || '').trim();
}

function isFinalAdjustmentLine(line) {
  return ['Payment', 'Adjustment'].includes(weeklyLineCategory(line));
}

function weeklyProfitHandlingLabel(line) {
  if (isFinalAdjustmentLine(line)) return 'Non-Profit Item';
  return line?.profit_eligible ? 'YES' : 'NO';
}

function balanceLabel(value) {
  return Number(value || 0) < 0 ? 'Advance Balance' : 'Ledger Balance / Outstanding';
}

function previousBalanceLabel(value) {
  return Number(value || 0) < 0 ? 'Previous Advance Balance' : 'Previous Outstanding';
}

function finalPayableLabel(value) {
  return Number(value || 0) < 0 ? 'Advance Balance' : 'Final Outstanding';
}

function balanceDisplay(value) {
  return inr(Math.abs(Number(value || 0)));
}

function invoicePaymentsThisWeek(invoice) {
  return Number(invoice?.payments_this_week ?? invoice?.payment_amount ?? 0);
}

function invoicePaymentsAfterWeek(invoice) {
  return Number(invoice?.payments_after_week ?? 0);
}

function invoiceTotalPaymentsTillToday(invoice) {
  return Number(invoice?.total_payments_till_today ?? invoicePaymentsThisWeek(invoice) + invoicePaymentsAfterWeek(invoice));
}

function invoiceFinalOutstanding(invoice) {
  return Number(invoice?.final_outstanding ?? invoice?.ledger_balance ?? invoice?.final_payable ?? 0);
}

function invoiceLedgerBalance(invoice) {
  return Number(invoice?.ledger_balance ?? invoiceFinalOutstanding(invoice));
}

function invoiceCurrentWeekPayable(invoice) {
  return Number(invoice?.actual_usage_billing || 0) + Number(invoice?.data_charges || 0) + Number(invoice?.other_charges || 0);
}

function invoiceCurrentWeekBilling(invoice) {
  return invoiceCurrentWeekPayable(invoice);
}

function invoicePreviousOutstanding(invoice) {
  return Number(invoice?.opening_balance || 0);
}

function invoiceAdjustmentAmount(invoice) {
  return Number(invoice?.adjustment_amount || 0);
}

function invoiceDisplayCurrentWeekPayable(invoice) {
  return Number(invoice?.actual_usage_billing || 0) + Number(invoice?.data_charges || 0) + Number(invoice?.other_charges || 0);
}

function invoiceDisplayLedgerBalance(invoice) {
  return invoicePreviousOutstanding(invoice) + invoiceDisplayCurrentWeekPayable(invoice);
}

async function downloadWeeklyInvoicePdf(invoice) {
  const blob = await requestBlob(`/billing/weekly-invoices/${invoice.id}/pdf`);
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `weekly-invoice-${invoice.id}.pdf`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function WeeklyInvoicePanel({ user, clients = [], canCreate = false, canExport = false, canDelete = false }) {
  const weekDates = useMemo(currentWeekDates, []);
  const [invoices, setInvoices] = useState([]);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingCharges, setLoadingCharges] = useState(false);
  const [chargePreview, setChargePreview] = useState(null);
  const [viewInvoice, setViewInvoice] = useState(null);
  const [form, setForm] = useState({
    client_id: '',
    week_start_date: weekDates.start,
    week_end_date: weekDates.end,
    active_billing_days: 5,
    daily_expected_billing: DEFAULT_DAILY_EXPECTED_BILLING_INR,
    profit_percent: 0,
    notes: '',
  });
  const isCustomer = user.role === 'customer';
  const isAdmin = user.role === 'admin';
  const math = weeklyInvoiceMath(chargePreview ? {
    active_billing_days: chargePreview.active_billing_days,
    daily_expected_billing: chargePreview.daily_expected_billing,
    billing_charges: chargePreview.billing_charges,
    data_charges: chargePreview.data_charges,
    other_charges: chargePreview.other_charges,
    payment_amount: chargePreview.payment_amount,
    adjustment_amount: chargePreview.adjustment_amount,
    opening_balance: chargePreview.opening_balance,
    payments_after_week: chargePreview.payments_after_week,
    total_payments_till_today: chargePreview.total_payments_till_today,
    ledger_balance: chargePreview.ledger_balance,
    final_outstanding: chargePreview.final_outstanding,
    profit_percent: form.profit_percent,
  } : form);
  const summary = {
    expected: math.expected_weekly_billing ?? math.expected ?? 0,
    billingCharges: math.billing_charges ?? math.billingCharges ?? 0,
    dataCharges: math.data_charges ?? math.dataCharges ?? 0,
    otherCharges: math.other_charges ?? math.otherCharges ?? 0,
    payments: math.payment_amount ?? math.payments ?? 0,
    adjustments: math.adjustment_amount ?? math.adjustments ?? 0,
    openingBalance: math.opening_balance ?? math.openingBalance ?? 0,
    currentWeekBilling: math.current_week_billing ?? math.currentWeekBilling ?? (math.current_week_payable ?? math.currentWeekPayable ?? 0),
    currentWeekPayable: math.current_week_payable ?? math.currentWeekPayable ?? 0,
    paymentsThisWeek: math.payments_this_week ?? math.paymentsThisWeek ?? math.payment_amount ?? math.payments ?? 0,
    paymentsAfterWeek: math.payments_after_week ?? math.paymentsAfterWeek ?? 0,
    totalPaymentsTillToday: math.total_payments_till_today ?? math.totalPaymentsTillToday ?? ((math.payments_this_week ?? math.paymentsThisWeek ?? math.payment_amount ?? math.payments ?? 0) + (math.payments_after_week ?? math.paymentsAfterWeek ?? 0)),
    ledgerBalance: math.ledger_balance ?? math.ledgerBalance ?? math.final_outstanding ?? math.finalOutstanding ?? math.final_payable ?? math.finalPayable ?? 0,
    finalOutstanding: math.final_outstanding ?? math.finalOutstanding ?? math.ledger_balance ?? math.ledgerBalance ?? math.final_payable ?? math.finalPayable ?? 0,
    advanceRemaining: math.advance_remaining ?? math.advanceRemaining ?? 0,
    profitPercent: math.profit_percent ?? math.profitPercent ?? Number(form.profit_percent || 0),
    profitAmount: math.profit_amount ?? math.profitAmount ?? 0,
    actualUsage: math.actual_usage_billing ?? math.actualUsage ?? 0,
    finalPayable: math.final_payable ?? math.finalPayable ?? 0,
    difference: math.difference ?? 0,
    status: math.status || 'Red',
  };
  const invoiceTotals = invoices.reduce((total, invoice) => ({
    expected: total.expected + Number(invoice.expected_weekly_billing || 0),
    actual: total.actual + Number(invoice.actual_usage_billing || 0),
    data: total.data + Number(invoice.data_charges || 0),
    other: total.other + Number(invoice.other_charges || 0),
    payments: total.payments + Number(invoice.payment_amount || 0),
    adjustments: total.adjustments + Number(invoice.adjustment_amount || 0),
    opening: total.opening + Number(invoice.opening_balance || 0),
    currentWeek: total.currentWeek + Number(invoice.current_week_payable || 0),
    final: total.final + invoiceFinalOutstanding(invoice),
  }), { expected: 0, actual: 0, data: 0, other: 0, payments: 0, adjustments: 0, opening: 0, currentWeek: 0, final: 0 });

  const loadInvoices = async () => {
    setLoading(true);
    setError('');
    try {
      setInvoices(await request('/billing/weekly-invoices'));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadInvoices();
  }, []);

  const setInvoiceField = (field, value) => {
    setError('');
    setMessage('');
    if (field !== 'notes' && field !== 'profit_percent') setChargePreview(null);
    setForm((current) => ({ ...current, [field]: value }));
  };

  const resetForm = () => {
    setForm({
      client_id: '',
      week_start_date: weekDates.start,
      week_end_date: weekDates.end,
      active_billing_days: 5,
      daily_expected_billing: DEFAULT_DAILY_EXPECTED_BILLING_INR,
      profit_percent: 0,
      notes: '',
    });
    setChargePreview(null);
  };

  const validateWeeklyInputs = () => {
    if (!form.client_id) return 'Select a client before loading charges.';
    if (!form.week_start_date || !form.week_end_date) return 'Select week start and end dates.';
    if (Number(form.active_billing_days || 0) < 1) return 'Active Billing Days must be at least 1.';
    if (Number(form.daily_expected_billing || 0) <= 0) return 'Daily Expected Billing must be greater than zero.';
    if (Number(form.profit_percent) < 0 || form.profit_percent === '') return 'Enter a valid Profit %.';
    return '';
  };

  const weeklyPayload = () => ({
    client_id: Number(form.client_id),
    week_start_date: form.week_start_date,
    week_end_date: form.week_end_date,
    active_billing_days: Number(form.active_billing_days),
    daily_expected_billing: Number(form.daily_expected_billing || DEFAULT_DAILY_EXPECTED_BILLING_INR),
    profit_percent: Number(form.profit_percent || 0),
    notes: form.notes,
  });

  const loadCharges = async () => {
    setError('');
    setMessage('');
    const validation = validateWeeklyInputs();
    if (validation) {
      setError(validation);
      return;
    }
    setLoadingCharges(true);
    try {
      const preview = await request('/billing/weekly-invoices/preview', { method: 'POST', body: JSON.stringify(weeklyPayload()) });
      setChargePreview(preview);
      setMessage(`Loaded ${preview.lines.length} Money Engine entries.`);
    } catch (err) {
      setChargePreview(null);
      setError(err.message);
    } finally {
      setLoadingCharges(false);
    }
  };

  const saveWeeklyInvoice = async (event) => {
    event.preventDefault();
    setError('');
    setMessage('');
    const validation = validateWeeklyInputs();
    if (validation) {
      setError(validation);
      return;
    }
    if (!chargePreview?.lines?.length) {
      setError('Click Load Charges before generating the weekly invoice.');
      return;
    }
    try {
      const saved = await request('/billing/weekly-invoices', {
        method: 'POST',
        body: JSON.stringify(weeklyPayload()),
      });
      setMessage(`Weekly invoice saved for ${saved.client_name || 'client'}.`);
      resetForm();
      await loadInvoices();
    } catch (err) {
      setError(err.message);
    }
  };

  const createDemoWeeklyData = async () => {
    setError('');
    setMessage('');
    const validation = validateWeeklyInputs();
    if (validation) {
      setError(validation);
      return;
    }
    setLoadingCharges(true);
    try {
      const result = await request('/billing/weekly-invoices/demo-data', { method: 'POST', body: JSON.stringify(weeklyPayload()) });
      setMessage(result.message || 'Demo weekly data ready.');
      const preview = await request('/billing/weekly-invoices/preview', { method: 'POST', body: JSON.stringify(weeklyPayload()) });
      setChargePreview(preview);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingCharges(false);
    }
  };

  const deleteWeeklyInvoice = async (invoice) => {
    if (!window.confirm('Delete this weekly invoice?')) return;
    setError('');
    setMessage('');
    try {
      await request(`/billing/weekly-invoices/${invoice.id}`, { method: 'DELETE' });
      setMessage('Weekly invoice deleted. Daily Money Engine entries were not changed.');
      setViewInvoice((current) => (current?.id === invoice.id ? null : current));
      await loadInvoices();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="weeklyInvoicePanel">
      <div className="sectionHeader">
        <div>
          <span className="eyebrow">{isCustomer ? 'Client Portal' : 'Weekly Invoice System'}</span>
          <h2>Weekly Invoices</h2>
        </div>
        <button onClick={loadInvoices}><RefreshCcw size={16} /> Refresh</button>
      </div>

      <div className="cards weeklyInvoiceCards">
        <div className="metric"><span>Saved Invoices</span><strong>{invoices.length}</strong></div>
        {isCustomer ? (
          <>
            <div className="metric payment"><span>Usage Billing</span><strong>{inr(invoiceTotals.actual)}</strong></div>
            <div className="metric"><span>Data Cost</span><strong>{inr(invoiceTotals.data)}</strong></div>
          </>
        ) : (
          <>
            <div className="metric revenue"><span>Expected Billing</span><strong>{inr(invoiceTotals.expected)}</strong></div>
            <div className="metric payment"><span>Actual Usage Billing</span><strong>{inr(invoiceTotals.actual)}</strong></div>
          </>
        )}
        <div className={`metric ${invoiceTotals.final > 0 ? 'metricAlert' : ''}`}><span>Final Payable</span><strong>{inr(invoiceTotals.final)}</strong></div>
      </div>

      {canCreate && !isCustomer && (
        <form className="weeklyInvoiceForm" onSubmit={saveWeeklyInvoice}>
          <ClientSelect value={form.client_id} clients={clients} onChange={(value) => setInvoiceField('client_id', value)} placeholder="Client / Group" />
          <label><span>Week Start Date</span><input type="date" value={form.week_start_date} onChange={(event) => setInvoiceField('week_start_date', event.target.value)} /></label>
          <label><span>Week End Date</span><input type="date" value={form.week_end_date} onChange={(event) => setInvoiceField('week_end_date', event.target.value)} /></label>
          <label><span>Active Billing Days</span><input type="number" min="1" max="7" value={form.active_billing_days} onChange={(event) => setInvoiceField('active_billing_days', event.target.value)} /></label>
          <label><span>Daily Expected Billing</span><input type="number" min="0" step="0.01" value={form.daily_expected_billing} onChange={(event) => setInvoiceField('daily_expected_billing', event.target.value)} /></label>
          <label><span>Profit %</span><input type="number" min="0" step="0.01" value={form.profit_percent} onChange={(event) => setInvoiceField('profit_percent', event.target.value)} /></label>
          <label className="weeklyNotes"><span>Notes</span><textarea value={form.notes} onChange={(event) => setInvoiceField('notes', event.target.value)} placeholder="Invoice note" /></label>
          <div className="weeklyInvoiceActions">
            <button type="button" onClick={loadCharges} disabled={loadingCharges}><RefreshCcw size={16} /> {loadingCharges ? 'Loading Charges' : 'Load Charges'}</button>
            {isAdmin && <button type="button" onClick={createDemoWeeklyData} disabled={loadingCharges}><Plus size={16} /> Create Demo Weekly Data</button>}
            <button className="primary" disabled={!chargePreview?.lines?.length}><Plus size={16} /> Generate Weekly Invoice</button>
          </div>
          <div className="weeklyInvoicePreview">
            <div className="weeklyCalcSection profitBase">
              <div className="weeklyCalcHeader">
                <span>Profit Base</span>
                <small>Profit NOT applied on Data, Other Charges, Payments, or Adjustments</small>
              </div>
              <div className="weeklyCalcRows">
                <span>Profit Eligible Billing</span><strong>{inr(summary.billingCharges)}</strong>
                <span>Profit %</span><strong>{Number(summary.profitPercent || 0).toFixed(2)}%</strong>
                <span>Profit Amount</span><strong>{inr(summary.profitAmount)}</strong>
              </div>
            </div>
            <div className="weeklyCalcSection nonProfitItems">
              <div className="weeklyCalcHeader">
                <span>Non-Profit Items</span>
                <small>Excluded from profit calculation</small>
              </div>
              <div className="weeklyCalcRows">
                <span>Data Cost</span><strong>{inr(summary.dataCharges)}</strong>
                <span>Other Charges</span><strong>{inr(summary.otherCharges)}</strong>
              </div>
            </div>
            <div className="weeklyCalcSection finalAdjustments">
              <div className="weeklyCalcHeader">
                <span>Final Adjustments</span>
                <small>Payments reduce payable; adjustments apply only at final total</small>
              </div>
              <div className="weeklyCalcRows">
                <span>Payments</span><strong className="creditText">- {inr(summary.payments)}</strong>
                <span>Adjustments</span><strong>{inr(summary.adjustments)}</strong>
              </div>
            </div>
            <div className="weeklyCalcSection finalTotals">
              <div className="weeklyCalcHeader">
                <span>Ledger Balance</span>
                <small>Week dates pull charges only; outstanding uses full ledger through today</small>
              </div>
              <div className="weeklyCalcRows">
                <span>{previousBalanceLabel(summary.openingBalance)}</span><strong className={summary.openingBalance < 0 ? 'okText' : summary.openingBalance > 0 ? 'outstandingText' : ''}>{balanceDisplay(summary.openingBalance)}</strong>
                <span>Current Week Payable</span><strong>{inr(summary.currentWeekPayable)}</strong>
                <span>Payments This Week</span><strong className="creditText">- {inr(summary.paymentsThisWeek)}</strong>
                <span>Payments After Week</span><strong className="creditText">- {inr(summary.paymentsAfterWeek)}</strong>
                <span>Total Payments Till Today</span><strong className="creditText">{inr(summary.totalPaymentsTillToday)}</strong>
                <span>{balanceLabel(summary.ledgerBalance)}</span><strong className={summary.ledgerBalance < 0 ? 'okText' : 'outstandingText'}>{balanceDisplay(summary.ledgerBalance)}</strong>
                <span>{finalPayableLabel(summary.finalOutstanding)}</span><strong className={summary.finalOutstanding < 0 ? 'okText' : 'outstandingText'}>{balanceDisplay(summary.finalOutstanding)}</strong>
              </div>
            </div>
          </div>
          {error && <span className="formError">{error}</span>}
          {chargePreview?.lines?.length > 0 && (
            <div className="weeklyPulledEntries">
              <h3>Charges Pulled From Daily Money Entries</h3>
              <div className="tableWrap weeklyChargeTable">
                <table>
                  <thead><tr><th>Date</th><th>Type</th><th>Description</th><th>Amount USD</th><th>Amount INR</th><th>Profit Handling</th></tr></thead>
                  <tbody>{chargePreview.lines.map((line) => (
                    <tr key={line.source_ledger_id || line.id} className={isFinalAdjustmentLine(line) ? 'finalAdjustmentRow' : ''}>
                      <td>{line.entry_date}</td>
                      <td>{line.charge_type || line.label}</td>
                      <td>{line.description || '-'}</td>
                      <td>{usd(line.amount_usd)}</td>
                      <td>{inr(line.amount_inr)}</td>
                      <td><span className={`profitEligibleFlag ${line.profit_eligible ? 'yes' : isFinalAdjustmentLine(line) ? 'adjustment' : 'no'}`}>{weeklyProfitHandlingLabel(line)}</span></td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
            </div>
          )}
        </form>
      )}

      {message && <div className="toastSuccess">{message}</div>}
      {error && (!canCreate || isCustomer) && <div className="error"><AlertTriangle size={16} /> {error}</div>}
      {isCustomer && <p className="muted">Only saved weekly invoices are visible in the client portal.</p>}

      <div className="tableWrap weeklyInvoiceTable">
        <table>
          {isCustomer ? (
            <>
              <thead><tr><th>Client / Group</th><th>Week</th><th>Active Days</th><th>Current Week Payable</th><th>Payments This Week</th><th>Payments After Week</th><th>Total Payments</th><th>Final Outstanding</th><th>Actions</th></tr></thead>
              <tbody>
                {invoices.map((invoice) => (
                  <tr key={invoice.id}>
                    <td>{invoice.client_name || '-'}</td>
                    <td>{invoice.week_start_date} to {invoice.week_end_date}</td>
                    <td>{invoice.active_billing_days}</td>
                    <td>{inr(invoiceCurrentWeekPayable(invoice))}</td>
                    <td className="creditText">{inr(invoicePaymentsThisWeek(invoice))}</td>
                    <td className="creditText">{inr(invoicePaymentsAfterWeek(invoice))}</td>
                    <td className="creditText">{inr(invoiceTotalPaymentsTillToday(invoice))}</td>
                    <td className={invoiceFinalOutstanding(invoice) > 0 ? 'outstandingText' : 'okText'}>{finalPayableLabel(invoiceFinalOutstanding(invoice))}: {balanceDisplay(invoiceFinalOutstanding(invoice))}</td>
                    <td className="actions"><button onClick={() => setViewInvoice(invoice)}><Eye size={15} /> View</button>{canExport && <button onClick={() => downloadWeeklyInvoicePdf(invoice)}><Download size={15} /> PDF</button>}</td>
                  </tr>
                ))}
                {!loading && invoices.length === 0 && <tr><td colSpan="9" className="muted">No saved weekly invoices yet.</td></tr>}
                {loading && <tr><td colSpan="9" className="muted">Loading weekly invoices...</td></tr>}
              </tbody>
            </>
          ) : (
            <>
              <thead><tr><th>Client / Group</th><th>Week</th><th>Active Days</th><th>Expected Billing</th><th>Profit Eligible</th><th>Data Cost</th><th>Other</th><th>Profit</th><th>Actual Usage</th><th>Current Week</th><th>Pay After Week</th><th>Total Payments</th><th>Final Outstanding</th><th>Status</th><th>Actions</th></tr></thead>
              <tbody>
                {invoices.map((invoice) => (
                  <tr key={invoice.id}>
                    <td>{invoice.client_name || '-'}</td>
                    <td>{invoice.week_start_date} to {invoice.week_end_date}</td>
                    <td>{invoice.active_billing_days}</td>
                    <td>{inr(invoice.expected_weekly_billing)}</td>
                    <td>{inr(invoice.billing_charges)}</td>
                    <td>{inr(invoice.data_charges)}</td>
                    <td>{inr(invoice.other_charges)}</td>
                    <td>{Number(invoice.profit_percent || 0).toFixed(2)}% / {inr(invoice.profit_amount)}</td>
                    <td>{inr(invoice.actual_usage_billing)}</td>
                    <td>{inr(invoiceCurrentWeekPayable(invoice))}</td>
                    <td className="creditText">{inr(invoicePaymentsAfterWeek(invoice))}</td>
                    <td className="creditText">{inr(invoiceTotalPaymentsTillToday(invoice))}</td>
                    <td className={invoiceFinalOutstanding(invoice) > 0 ? 'outstandingText' : 'okText'}>{finalPayableLabel(invoiceFinalOutstanding(invoice))}: {balanceDisplay(invoiceFinalOutstanding(invoice))}</td>
                    <td><span className={weeklyStatusClass(invoice.status)}>{invoice.status}</span></td>
                    <td className="actions"><button onClick={() => setViewInvoice(invoice)}><Eye size={15} /> View</button>{canExport && <button onClick={() => downloadWeeklyInvoicePdf(invoice)}><Download size={15} /> PDF</button>}{canDelete && <button className="danger" onClick={() => deleteWeeklyInvoice(invoice)}><Trash2 size={15} /> Delete</button>}</td>
                  </tr>
                ))}
                {!loading && invoices.length === 0 && <tr><td colSpan="15" className="muted">No saved weekly invoices yet.</td></tr>}
                {loading && <tr><td colSpan="15" className="muted">Loading weekly invoices...</td></tr>}
              </tbody>
            </>
          )}
        </table>
      </div>
      {viewInvoice && <WeeklyInvoiceViewModal invoice={viewInvoice} canExport={canExport} onDownload={downloadWeeklyInvoicePdf} onClose={() => setViewInvoice(null)} />}
    </div>
  );
}

function WeeklyInvoiceViewModal({ invoice, canExport, onDownload, onClose }) {
  const adjustmentAmount = invoiceAdjustmentAmount(invoice);
  const currentWeekPayable = invoiceDisplayCurrentWeekPayable(invoice);
  const ledgerBalance = invoiceDisplayLedgerBalance(invoice);
  const finalOutstanding = invoiceFinalOutstanding(invoice);
  return (
    <div className="modalBackdrop modal-overlay">
      <div className="modal modal-box weeklyInvoiceViewModal">
        <div className="modalHeader weeklyInvoiceViewHeader">
          <div>
            <span className="eyebrow">Saved Weekly Invoice</span>
            <h2>{invoice.client_name || 'Client'} | {invoice.week_start_date} to {invoice.week_end_date}</h2>
          </div>
          <div className="actions">
            {canExport && <button onClick={() => onDownload(invoice)}><Download size={16} /> PDF</button>}
            <button className="iconButton" onClick={onClose} title="Close"><X size={18} /></button>
          </div>
        </div>

        <div className="weeklyInvoiceSimple">
          <section className="weeklyInvoiceSection">
            <h3>Week Summary</h3>
            <div className="weeklyInvoiceViewGrid">
              <div><span>Client Name</span><strong>{invoice.client_name || 'Client'}</strong></div>
              <div><span>Week Date Range</span><strong>{invoice.week_start_date} to {invoice.week_end_date}</strong></div>
              <div><span>Active Billing Days</span><strong>{invoice.active_billing_days}</strong></div>
            </div>
          </section>

          <section className="weeklyInvoiceSection">
            <h3>Invoice Amount</h3>
            <div className="weeklyInvoiceViewGrid">
              <div><span>Usage Billing</span><strong>{inr(invoice.actual_usage_billing)}</strong></div>
              <div><span>Data Cost</span><strong>{inr(invoice.data_charges)}</strong></div>
              <div><span>Other Charges</span><strong>{inr(invoice.other_charges)}</strong></div>
              {adjustmentAmount !== 0 && <div><span>Adjustments</span><strong>{inr(adjustmentAmount)}</strong></div>}
              <div className="weeklyInvoiceTotal"><span>Current Week Payable</span><strong>{inr(currentWeekPayable)}</strong></div>
            </div>
          </section>

          <section className="weeklyInvoiceSection">
            <h3>Payment & Balance</h3>
            <div className="weeklyInvoiceViewGrid">
              <div><span>Previous Outstanding</span><strong>{inr(invoicePreviousOutstanding(invoice))}</strong></div>
              <div><span>Current Week Payable</span><strong>{inr(currentWeekPayable)}</strong></div>
              <div><span>Ledger Balance</span><strong>{inr(ledgerBalance)}</strong></div>
              <div className="weeklyInvoiceTotal"><span>{finalPayableLabel(finalOutstanding)}</span><strong className={finalOutstanding > 0 ? 'outstandingText' : 'okText'}>{balanceDisplay(finalOutstanding)}</strong></div>
            </div>
          </section>
        </div>

        {invoice.notes && <div className="panel weeklyInvoiceNotes"><h2>Notes</h2><p>{invoice.notes}</p></div>}
      </div>
    </div>
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
  if (user.role === 'customer') {
    return (
      <ClientInvoiceLedgerView user={user} pageKey="my_ledger" title="My Ledger" />
    );
  }
  return (
    <section>
      <BillingCards summary={billing.ledgerSummary || {}} />
      {Number(billing.ledgerSummary?.total_outstanding || 0) > 0 && <div className="alert billingAlert">Payment follow-up required for outstanding balance.</div>}
      {user.role === 'admin' && <BillingRateConfig settings={settings} reload={reload} />}
      <WeeklyInvoicePanel user={user} clients={data.clients} canCreate={canCreate} canExport={canExport} canDelete={canDelete} />
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
        <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value, client_id: e.target.value === 'admin' ? '' : form.client_id })}><option>admin</option><option>noc_user</option><option>customer</option><option>viewer</option></select>
        {form.role !== 'admin' && <ClientSelect value={form.client_id} clients={clients} onChange={(value) => setForm({ ...form, client_id: value })} placeholder="Assign client" />}
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
  const [viewInvoice, setViewInvoice] = useState(null);
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
        <h2>Weekly Invoices</h2>
        <div className="tableWrap weeklyInvoiceTable"><table><thead><tr><th>Week</th><th>Active Days</th><th>Current Week Payable</th><th>Payments This Week</th><th>Payments After Week</th><th>Total Payments</th><th>Final Outstanding</th><th>Actions</th></tr></thead><tbody>{(detail.weekly_invoices || []).map((row) => (
          <tr key={row.id}><td>{row.week_start_date} to {row.week_end_date}</td><td>{row.active_billing_days}</td><td>{inr(invoiceCurrentWeekPayable(row))}</td><td className="creditText">{inr(invoicePaymentsThisWeek(row))}</td><td className="creditText">{inr(invoicePaymentsAfterWeek(row))}</td><td className="creditText">{inr(invoiceTotalPaymentsTillToday(row))}</td><td className={invoiceFinalOutstanding(row) > 0 ? 'outstandingText' : 'okText'}>{finalPayableLabel(invoiceFinalOutstanding(row))}: {balanceDisplay(invoiceFinalOutstanding(row))}</td><td className="actions"><button onClick={() => setViewInvoice(row)}><Eye size={15} /> View</button>{canExport && <button onClick={() => downloadWeeklyInvoicePdf(row)}><Download size={15} /> PDF</button>}</td></tr>
        ))}
          {(detail.weekly_invoices || []).length === 0 && <tr><td colSpan="8" className="muted">No saved weekly invoices.</td></tr>}
        </tbody></table></div>
        {viewInvoice && <WeeklyInvoiceViewModal invoice={viewInvoice} canExport={canExport} onDownload={downloadWeeklyInvoicePdf} onClose={() => setViewInvoice(null)} />}
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

function Dashboard({ dashboard, data, user, onDashboardUpdate }) {
  const layoutKey = 'noc360_command_center_layout';
  const defaultLayout = ['kpis', 'rdp', 'routing', 'cluster', 'client', 'placement', 'alerts'];
  const normalizeLayout = (stored) => {
    const parsed = Array.isArray(stored) ? stored : defaultLayout;
    return [...parsed.filter((key, index) => defaultLayout.includes(key) && parsed.indexOf(key) === index), ...defaultLayout.filter((key) => !parsed.includes(key))];
  };
  const [layout, setLayout] = useState(() => {
    try {
      return normalizeLayout(JSON.parse(localStorage.getItem(layoutKey) || '[]'));
    } catch {
      return defaultLayout;
    }
  });
  const [draggingKey, setDraggingKey] = useState('');
  const [dragOverKey, setDragOverKey] = useState('');
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
  const canCustomizeLayout = ['admin', 'noc_user'].includes(user?.role);

  const moveSection = (fromKey, toKey) => {
    if (!fromKey || !toKey || fromKey === toKey) return;
    setLayout((current) => {
      const next = [...current];
      const fromIndex = next.indexOf(fromKey);
      const toIndex = next.indexOf(toKey);
      if (fromIndex < 0 || toIndex < 0) return current;
      next.splice(fromIndex, 1);
      next.splice(toIndex, 0, fromKey);
      return next;
    });
  };

  const saveLayout = () => localStorage.setItem(layoutKey, JSON.stringify(layout));
  const resetLayout = () => {
    localStorage.removeItem(layoutKey);
    setLayout(defaultLayout);
  };

  const sections = {
    kpis: {
      title: 'KPI Cards',
      content: (
        <div className="cards commandKpiCards">
          {cards.map(([label, value, Icon]) => (
            <button className={`metric ${label === 'Alerts' && value ? 'metricAlert' : ''}`} key={label}>
              <Icon size={24} />
              <span>{label}</span>
              <strong>{value ?? 0}</strong>
            </button>
          ))}
        </div>
      ),
    },
    rdp: {
      title: 'RDP Brief View',
      content: <RdpBriefTable rows={dashboard?.rdp_brief || []} user={user} onDashboardUpdate={onDashboardUpdate} hideTitle />,
    },
    routing: {
      title: 'Routing Brief View',
      content: <BriefTable title="Routing Brief View" rows={dashboard?.routing_brief || []} columns={[['gateway_name','RTNG'],['gateway_ip','Gateway IP'],['media_1_name','Media 1'],['media_2_name','Media 2'],['carrier_ip','Carrier IP'],['ports','Ports'],['vendor','Vendor']]} hideTitle />,
    },
    cluster: {
      title: 'Cluster Brief View',
      content: <BriefTable title="Cluster Brief View" rows={dashboard?.cluster_brief || []} columns={[['cluster_no','Cluster No'],['cluster_name','Cluster Name'],['inbound_ip','Inbound IP'],['client','Client'],['assigned_rdp','Assigned RDP'],['assigned_rdp_ip','RDP IP']]} hideTitle />,
    },
    client: {
      title: 'Client Brief View',
      content: <BriefTable title="Client Brief View" rows={dashboard?.client_brief || []} columns={[['client','Client'],['assigned_clusters','Assigned Clusters'],['used_rdp','Used RDP'],['outstanding','Outstanding']]} moneyKey="outstanding" moneyInrKey="outstanding_inr" hideTitle />,
    },
    placement: {
      title: 'System Routing Placement',
      content: <SystemRoutingPlacementTable data={data} user={user} hideTitle />,
    },
    alerts: {
      title: 'Alerts',
      content: <CommandCenterAlerts alerts={dashboard?.alerts || []} />,
    },
  };

  return (
    <section className="dashboard">
      <div className="commandCenterHeader">
        <h2>Command Center</h2>
        {canCustomizeLayout && (
          <div className="layoutActions">
            <button onClick={saveLayout}>Save Layout</button>
            <button onClick={resetLayout}>Reset Layout</button>
          </div>
        )}
      </div>
      <div className="commandCenterLayout">
        {layout.map((key) => (
          <DraggableDashboardSection
            key={key}
            sectionKey={key}
            title={sections[key].title}
            canDrag={canCustomizeLayout}
            draggingKey={draggingKey}
            dragOverKey={dragOverKey}
            onDragStart={setDraggingKey}
            onDragOver={setDragOverKey}
            onDragEnd={() => { setDraggingKey(''); setDragOverKey(''); }}
            onDrop={moveSection}
          >
            {sections[key].content}
          </DraggableDashboardSection>
        ))}
      </div>
    </section>
  );
}

function DraggableDashboardSection({ sectionKey, title, canDrag, draggingKey, dragOverKey, onDragStart, onDragOver, onDragEnd, onDrop, children }) {
  const isDragging = draggingKey === sectionKey;
  const isDragOver = dragOverKey === sectionKey && draggingKey !== sectionKey;
  return (
    <div
      className={`dashboardLayoutItem ${isDragging ? 'isDragging' : ''} ${isDragOver ? 'isDragOver' : ''}`}
      onDragOver={(event) => {
        if (!canDrag || !draggingKey) return;
        event.preventDefault();
        onDragOver(sectionKey);
      }}
      onDrop={(event) => {
        if (!canDrag) return;
        event.preventDefault();
        onDrop(draggingKey || event.dataTransfer.getData('text/plain'), sectionKey);
        onDragEnd();
      }}
    >
      <div className="dashboardSectionHeader">
        <h2>{title}</h2>
        {canDrag && (
          <button
            className="dragHandle"
            draggable
            onDragStart={(event) => {
              event.dataTransfer.effectAllowed = 'move';
              event.dataTransfer.setData('text/plain', sectionKey);
              onDragStart(sectionKey);
            }}
            onDragEnd={onDragEnd}
            title={`Drag ${title}`}
          >
            <span aria-hidden="true">⋮⋮</span> Drag
          </button>
        )}
      </div>
      {children}
    </div>
  );
}

function CommandCenterAlerts({ alerts }) {
  return (
    <div className="panel commandAlertsPanel">
      <div className="alertList">
        {alerts.length === 0 && <p className="muted">No duplicate or missing-IP alerts.</p>}
        {alerts.map((alert, index) => (
          <div className={`alert ${alert.type}`} key={`${alert.message}-${index}`}>
            <AlertTriangle size={17} />{cyberAlertMessage(alert)}
          </div>
        ))}
        </div>
    </div>
  );
}

function MissingValue({ value }) {
  return value ? value : <span className="missing">Missing</span>;
}

function RdpBriefTable({ rows, user, onDashboardUpdate, hideTitle = false }) {
  const columns = [
    ['rdp_name', 'RDP Name'],
    ['ip', 'IP'],
    ['status', 'Status'],
    ['assigned_cluster', 'Assigned Cluster'],
    ['client', 'Client'],
    ['used_in_routing', 'Used In Routing'],
    ['usage_status', 'Usage Status'],
  ];

  return (
    <div className="managementSection rdpBriefSection">
      {!hideTitle && <div className="sectionTitleRow">
        <h2>RDP Brief View</h2>
      </div>}
      <div className="tableWrap"><table className="rdpBriefTable"><thead><tr>{columns.map(([, label]) => <th key={label}>{label}</th>)}</tr></thead><tbody>{rows.map((row, index) => (
        <RdpBriefRow key={row.id || row.rdp_name || index} row={row} columns={columns} />
      ))}</tbody></table></div>
    </div>
  );
}

function RdpBriefRow({ row, columns }) {
  return (
    <tr>
      {columns.map(([key]) => {
        return <td key={key} className={key.includes('status') ? '' : undefined}>{key.includes('status') ? <StatusPill value={row[key]} /> : (row[key] || '-')}</td>;
      })}
    </tr>
  );
}

function SystemRoutingPlacementTable({ data, user, hideTitle = false }) {
  const [dateValue, setDateValue] = useState(todayDate());
  const [rows, setRows] = useState([]);
  const [filters, setFilters] = useState({ client_scope: '', cluster_id: '', status: '', assignment_status: '' });
  const [loadingRows, setLoadingRows] = useState(false);
  const [saving, setSaving] = useState('');
  const canEdit = user?.role !== 'customer' && canDo(user, 'dashboard', 'can_edit');

  const loadRows = async () => {
    setLoadingRows(true);
    try {
      setRows(await request(`/system-routing-placements?date=${dateValue}`));
    } catch (err) {
      window.alert(err.message);
    } finally {
      setLoadingRows(false);
    }
  };

  useEffect(() => {
    loadRows();
  }, [dateValue]);

  const filteredRows = rows.filter((row) => {
    const clientName = String(row.client_name || row.client || '').trim();
    const hasAssignedClient = Boolean(row.client_id) && Boolean(clientName) && clientName !== '-' && clientName !== 'Missing';
    if (filters.client_scope === 'assigned' && !hasAssignedClient) return false;
    if (filters.client_scope === 'unassigned' && hasAssignedClient) return false;
    if (filters.cluster_id && String(row.cluster_id || '') !== filters.cluster_id) return false;
    if (filters.status && String(row.status || '') !== filters.status) return false;
    const assigned = Boolean(row.routing_gateway_id) && (Boolean(row.media_1_id) || Boolean(row.media_2_id));
    if (filters.assignment_status === 'assigned' && !assigned) return false;
    if (filters.assignment_status === 'unassigned' && assigned) return false;
    return true;
  });

  const saveRow = async (row, form) => {
    const duplicate = rows.find((item) => (
      item.cluster_id !== row.cluster_id
      && String(item.status || 'Active') === 'Active'
      && String(row.status || 'Active') === 'Active'
      && form.did_patch
      && String(item.did_patch || '').trim().toLowerCase() === String(form.did_patch || '').trim().toLowerCase()
    ));
    if (duplicate && !window.confirm(`DID Patch ${form.did_patch} is already assigned to ${duplicate.cluster}. Save anyway?`)) return;
    setSaving(`placement-${row.cluster_id}`);
    try {
      const payload = {
        inbound_id: form.inbound_id || null,
        did_patch: form.did_patch || null,
        placement_date: dateValue,
      };
      await request(`/system-routing-placements/${row.cluster_id}/inbound-did`, {
        method: 'PUT',
        body: JSON.stringify(payload),
      });
      await loadRows();
    } catch (err) {
      window.alert(err.message);
    } finally {
      setSaving('');
    }
  };

  return (
    <div className="managementSection systemPlacementSection">
      {!hideTitle && <div className="sectionTitleRow">
        <h2>System Routing Placement</h2>
        {loadingRows && <span className="dailyEditable">Loading</span>}
      </div>}
      {hideTitle && loadingRows && <div className="sectionTitleRow"><span className="dailyEditable">Loading</span></div>}
      <div className="toolbar placementFilters">
        <label>Date<input type="date" value={dateValue} onChange={(event) => setDateValue(event.target.value || todayDate())} /></label>
        <label>Client<select value={filters.client_scope} onChange={(event) => setFilters({ ...filters, client_scope: event.target.value })}>
          <option value="">All</option>
          <option value="assigned">Assigned</option>
          <option value="unassigned">Unassigned</option>
        </select></label>
        <label>Cluster<select value={filters.cluster_id} onChange={(event) => setFilters({ ...filters, cluster_id: event.target.value })}>
          <option value="">All Clusters</option>
          {rows.map((row) => <option key={row.cluster_id} value={row.cluster_id}>{row.cluster}</option>)}
        </select></label>
        <label>Status<select value={filters.status} onChange={(event) => setFilters({ ...filters, status: event.target.value })}>
          <option value="">All Status</option>
          {['Active', 'Pending', 'Inactive', 'Missing'].map((status) => <option key={status}>{status}</option>)}
        </select></label>
        <label>Assignment Status<select value={filters.assignment_status} onChange={(event) => setFilters({ ...filters, assignment_status: event.target.value })}>
          <option value="">All</option>
          <option value="assigned">Assigned</option>
          <option value="unassigned">Unassigned</option>
        </select></label>
      </div>
      <div className="tableWrap">
        <table className="systemPlacementTable">
          <thead>
            <tr><th>Cluster</th><th>Client</th><th>Routing Gateway</th><th>Gateway IP</th><th>RDP / Media 1</th><th>Media 1 IP</th><th>RDP / Media 2</th><th>Media 2 IP</th><th>Inbound ID</th><th>DID Patch</th><th>Status</th><th>Actions</th></tr>
          </thead>
          <tbody>
            {filteredRows.map((row) => (
              <SystemRoutingPlacementRow key={row.cluster_id} row={row} canEdit={canEdit} saving={saving} onSave={saveRow} />
            ))}
            {!filteredRows.length && <tr><td colSpan="12" className="muted">No placement rows match the current filters.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SystemRoutingPlacementRow({ row, canEdit, saving, onSave }) {
  const [form, setForm] = useState({
    inbound_id: row.inbound_id || '',
    did_patch: row.did_patch || '',
  });

  useEffect(() => {
    setForm({
      inbound_id: row.inbound_id || '',
      did_patch: row.did_patch || '',
    });
  }, [row]);

  const displayStatus = row.missing && !row.id ? 'Missing' : row.status;
  const key = `placement-${row.cluster_id}`;

  const setField = (field, value) => setForm((current) => ({ ...current, [field]: value }));

  return (
    <tr className={row.missing ? 'needsAttention' : ''}>
      <td>{row.cluster || <span className="missing">Missing</span>}</td>
      <td>{row.client || <span className="missing">Missing</span>}</td>
      <td>{row.routing_gateway || <span className="missing">Missing</span>}</td>
      <td>{row.gateway_ip || <span className="missing">Missing</span>}</td>
      <td>{row.media_1 || <span className="missing">Missing</span>}</td>
      <td>{row.media_1_ip || <span className="missing">Missing</span>}</td>
      <td>{row.media_2 || <span className="missing">Missing</span>}</td>
      <td>{row.media_2_ip || <span className="missing">Missing</span>}</td>
      <td>{canEdit ? <input value={form.inbound_id} placeholder="Missing" onChange={(event) => setField('inbound_id', event.target.value)} /> : row.inbound_id || <span className="missing">Missing</span>}</td>
      <td>{canEdit ? <input value={form.did_patch} placeholder="Missing" onChange={(event) => setField('did_patch', event.target.value)} /> : row.did_patch || <span className="missing">Missing</span>}</td>
      <td><StatusPill value={displayStatus} /></td>
      <td>{canEdit ? <button onClick={() => onSave(row, form)}>{saving === key ? 'Saving...' : 'Save'}</button> : '-'}</td>
    </tr>
  );
}

function BriefTable({ title, rows, columns, moneyKey, moneyInrKey, hideTitle = false }) {
  return (
    <div className="managementSection">
      {!hideTitle && <h2>{title}</h2>}
      <div className="tableWrap"><table><thead><tr>{columns.map(([, label]) => <th key={label}>{label}</th>)}</tr></thead><tbody>{rows.map((row, index) => (
        <tr key={index}>{columns.map(([key]) => <td key={key} className={moneyKey === key && row[key] > 0 ? 'outstandingText' : ''}>{moneyKey === key ? (moneyInrKey ? dualMoney(row[key], row[moneyInrKey]) : money(row[key])) : (key.includes('status') ? <StatusPill value={row[key]} /> : row[key] || '-')}</td>)}</tr>
      ))}</tbody></table></div>
    </div>
  );
}

function CrudPage({ moduleKey, config, rows, rdps, mediaPortals = [], rtngs, clients = [], reload, user }) {
  const [query, setQuery] = useState('');
  const [editing, setEditing] = useState(null);
  const [saving, setSaving] = useState(false);
  const pageKey = modulePageKeys[moduleKey];
  const canCreate = canDo(user, pageKey, 'can_create');
  const canEdit = canDo(user, pageKey, 'can_edit');
  const canDelete = canDo(user, pageKey, 'can_delete');
  const canExport = canDo(user, pageKey, 'can_export');
  const tableFields = config.tableFields || config.fields.slice(0, 7);
  const exportFields = config.tableFields || config.fields;

  const valueFor = (row, key) => {
    const fallbacks = {
      media_1_name: 'media1_name',
      media_1_ip: 'media1_ip',
      media_2_name: 'media2_name',
      media_2_ip: 'media2_ip',
      vendor: 'vendor_name',
    };
    return row[key] ?? (fallbacks[key] ? row[fallbacks[key]] : undefined);
  };

  const renderCell = (row, [key, , type]) => {
    const value = valueFor(row, key);
    if (key === 'validation_alerts') {
      const alerts = Array.isArray(value) ? value : value ? [value] : [];
      return alerts.length ? alerts.map((alert) => <div className="duplicateText" key={alert}>{alert}</div>) : '-';
    }
    if (key === 'status' || type === 'readonlyStatus') return <StatusPill value={value} />;
    if (type === 'client') return row.client_name || <span className="missing">Unassigned</span>;
    if (Array.isArray(value)) return value.length ? value.join(', ') : '-';
    if (value === null || value === undefined || value === '') return config.readOnlyInventory ? '-' : <span className="missing">Missing</span>;
    return value;
  };

  const filtered = useMemo(() => {
    const needle = query.toLowerCase();
    return rows.filter((row) => Object.values(row).join(' ').toLowerCase().includes(needle));
  }, [rows, query]);

  const exportCsv = () => {
    const headers = ['id', ...exportFields.map(([key]) => key)];
    const csv = [
      headers.join(','),
      ...filtered.map((row) => headers.map((key) => `"${String(valueFor(row, key) ?? '').replaceAll('"', '""')}"`).join(',')),
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
      const numberOrNull = (value) => (value ? Number(value) : null);
      const body = Object.fromEntries(config.fields.map(([key, , type]) => {
        if (['number', 'client'].includes(type)) return [key, record[key] ? Number(record[key]) : null];
        if (type === 'boolean') return [key, Boolean(record[key])];
        return [key, record[key] || null];
      }));
      if (moduleKey === 'gateways') {
        const gatewayId = record.routing_gateway_id || record.rtng_vos_id || null;
        const media1Id = record.media_1_portal_id || record.media1_vos_id || null;
        const media2Id = record.media_2_portal_id || record.media2_vos_id || null;
        body.routing_gateway_id = numberOrNull(gatewayId);
        body.rtng_vos_id = numberOrNull(gatewayId);
        body.media_1_portal_id = numberOrNull(media1Id);
        body.media1_vos_id = numberOrNull(media1Id);
        body.media_1_name = record.media_1_name || record.media1_name || null;
        body.media1_name = record.media_1_name || record.media1_name || null;
        body.media_1_ip = record.media_1_ip || record.media1_ip || null;
        body.media1_ip = record.media_1_ip || record.media1_ip || null;
        body.media_2_portal_id = numberOrNull(media2Id);
        body.media2_vos_id = numberOrNull(media2Id);
        body.media_2_name = record.media_2_name || record.media2_name || null;
        body.media2_name = record.media_2_name || record.media2_name || null;
        body.media_2_ip = record.media_2_ip || record.media2_ip || null;
        body.media2_ip = record.media_2_ip || record.media2_ip || null;
        body.vendor = record.vendor || record.vendor_name || null;
        body.vendor_name = record.vendor || record.vendor_name || null;
      }
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
              {tableFields.map(([, label]) => <th key={label}>{label}</th>)}
              {!config.readOnlyInventory && (canEdit || canDelete) && <th>Actions</th>}
            </tr>
          </thead>
          <tbody>
            {filtered.map((row) => (
              <tr key={row.id} className={hasMissing(row) ? 'needsAttention' : ''}>
                {tableFields.map((field) => <td key={field[0]}>{renderCell(row, field)}</td>)}
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
          routingRows={rows}
          rdps={rdps}
          mediaPortals={mediaPortals}
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

function Editor({ config, record, routingRows = [], rdps, mediaPortals = [], rtngs = [], clients = [], saving, onClose, onSave }) {
  const [form, setForm] = useState(record);
  const usedMedia = buildUsedMediaMap(routingRows, form.gateway_name);

  const setField = (key, value) => {
    const next = { ...form, [key]: value };
    if (key === 'assigned_rdp') {
      const rdp = rdps.find((item) => item.name === value);
      next.assigned_rdp_ip = rdp?.ip || '';
    }
    if (key === 'gateway_name') {
      const gateway = rtngs.find((item) => item.portal_type === value);
      next.gateway_ip = gateway?.server_ip || '';
      next.routing_gateway_id = gateway?.id || null;
      next.rtng_vos_id = gateway?.id || null;
      next.gateway_name = gateway?.portal_type || value;
    }
    if (key === 'media_1_name' || key === 'media1_name') {
      const media = mediaPortals.find((item) => item.portal_type === value || String(item.id) === String(value));
      next.media_1_ip = media?.server_ip || '';
      next.media1_ip = media?.server_ip || '';
      next.media_1_portal_id = media?.id || null;
      next.media1_vos_id = media?.id || null;
      next.media_1_name = media?.portal_type || value;
      next.media1_name = media?.portal_type || value;
    }
    if (key === 'media_2_name' || key === 'media2_name') {
      const media = mediaPortals.find((item) => item.portal_type === value || String(item.id) === String(value));
      next.media_2_ip = media?.server_ip || '';
      next.media2_ip = media?.server_ip || '';
      next.media_2_portal_id = media?.id || null;
      next.media2_vos_id = media?.id || null;
      next.media_2_name = media?.portal_type || value;
      next.media2_name = media?.portal_type || value;
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
              {type === 'media' && (
                <select value={form[key] || ''} onChange={(event) => setField(key, event.target.value)}>
                  <option value="">Unassigned</option>
                  {mediaPortals.map((portal) => {
                    const assignedTo = usedMedia[portal.portal_type];
                    const disabled = Boolean(assignedTo) && portal.portal_type !== form[key];
                    return <option key={portal.id} value={portal.portal_type} disabled={disabled}>{portal.portal_type} - {portal.server_ip}{disabled ? ` (Already Assigned to ${assignedTo})` : ''}</option>;
                  })}
                </select>
              )}
              {type === 'client' && <ClientSelect value={form[key] || ''} clients={clients} onChange={(value) => setField(key, value)} />}
              {type === 'boolean' && <input type="checkbox" checked={Boolean(form[key])} onChange={(event) => setField(key, event.target.checked)} />}
              {type === 'textarea' && <textarea value={form[key] || ''} onChange={(event) => setField(key, event.target.value)} />}
              {type === 'readonly' && <input value={form[key] || ''} readOnly />}
              {!['status', 'readonlyStatus', 'rdp', 'rtng', 'media', 'client', 'boolean', 'textarea', 'readonly'].includes(type) && (
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
