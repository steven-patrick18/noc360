from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class VOSPortalBase(BaseModel):
    vos_version: str
    portal_type: str
    server_ip: str
    status: str = "Active"
    username: Optional[str] = None
    password: Optional[str] = None
    anti_hack_url: Optional[str] = None
    anti_hack_password: Optional[str] = None
    uuid: Optional[str] = None
    cdr_panel_url: Optional[str] = None
    web_panel_url: Optional[str] = None
    assigned_to: Optional[str] = None
    assigned_cluster: Optional[str] = None
    notes: Optional[str] = None
    vos_port: Optional[int] = 80
    vos_desktop_enabled: Optional[bool] = False
    vos_notes: Optional[str] = None


class VOSPortalCreate(VOSPortalBase):
    pass


class VOSPortalUpdate(VOSPortalBase):
    pass


class VOSPortalOut(VOSPortalBase, OrmModel):
    id: int


class DialerClusterBase(BaseModel):
    cluster_no: int
    account_name: str
    db_ip: Optional[str] = None
    web_ips: Optional[str] = None
    asterisk_ips: Optional[str] = None
    inbound_ip: Optional[str] = None
    client_id: Optional[int] = None
    dids_patch: Optional[str] = None
    in_id: Optional[str] = None
    assigned_rdp: Optional[str] = None
    assigned_rdp_ip: Optional[str] = None
    rdp_vos_id: Optional[int] = None
    status: str = "Pending"


class DialerClusterCreate(DialerClusterBase):
    pass


class DialerClusterUpdate(DialerClusterBase):
    pass


class DialerClusterOut(DialerClusterBase, OrmModel):
    id: int
    client_name: Optional[str] = None
    cluster_name: Optional[str] = None


class RDPBase(BaseModel):
    name: Optional[str] = None
    ip: Optional[str] = None
    status: Optional[str] = None
    assigned_to: Optional[str] = None
    assigned_cluster: Optional[str] = None
    used_in_routing: Optional[str] = None
    usage_status: Optional[str] = None
    notes: Optional[str] = None


class RDPCreate(RDPBase):
    pass


class RDPUpdate(RDPBase):
    pass


class RDPOut(RDPBase, OrmModel):
    id: int


class RoutingGatewayBase(BaseModel):
    gateway_name: str
    gateway_ip: Optional[str] = None
    routing_gateway_id: Optional[int] = None
    rtng_vos_id: Optional[int] = None
    client_id: Optional[int] = None
    media_1_name: Optional[str] = None
    media_1_ip: Optional[str] = None
    media_1_portal_id: Optional[int] = None
    media1_name: Optional[str] = None
    media1_ip: Optional[str] = None
    media1_vos_id: Optional[int] = None
    media_2_name: Optional[str] = None
    media_2_ip: Optional[str] = None
    media_2_portal_id: Optional[int] = None
    media2_name: Optional[str] = None
    media2_ip: Optional[str] = None
    media2_vos_id: Optional[int] = None
    carrier_ip: Optional[str] = None
    ports: Optional[str] = None
    vendor: Optional[str] = None
    vendor_name: Optional[str] = None
    status: str = "Active"
    notes: Optional[str] = None
    validation_alerts: list[str] = []


class RoutingGatewayCreate(RoutingGatewayBase):
    pass


class RoutingGatewayUpdate(RoutingGatewayBase):
    pass


class RoutingGatewayOut(RoutingGatewayBase, OrmModel):
    id: int


class ClientBase(BaseModel):
    name: str
    status: str = "Active"
    notes: Optional[str] = None


class ClientCreate(ClientBase):
    login_username: Optional[str] = None
    login_password: Optional[str] = None
    confirm_password: Optional[str] = None


class ClientOut(ClientBase, OrmModel):
    id: int
    username: Optional[str] = None
    outstanding_usd: float = 0
    outstanding_inr: float = 0


class LoginIn(BaseModel):
    username: str
    password: str


class UserOut(OrmModel):
    id: int
    username: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: str
    client_id: Optional[int] = None
    status: str
    client_name: Optional[str] = None
    client_ids: list[int] = []
    permissions: dict = {}


class UserCreate(BaseModel):
    username: str
    password: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: str = "viewer"
    client_id: Optional[int] = None
    status: str = "Active"


class UserUpdate(BaseModel):
    username: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: str = "viewer"
    client_id: Optional[int] = None
    status: str = "Active"


class PasswordResetIn(BaseModel):
    password: str


class PagePermissionIn(BaseModel):
    page_key: str
    can_view: bool = False
    can_create: bool = False
    can_edit: bool = False
    can_delete: bool = False
    can_export: bool = False


class PagePermissionOut(PagePermissionIn, OrmModel):
    id: int
    user_id: int


class ClientAccessIn(BaseModel):
    client_ids: list[int] = []


class ActivityLogOut(OrmModel):
    id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    role: Optional[str] = None
    action: str
    module: str
    record_type: Optional[str] = None
    record_id: Optional[int] = None
    description: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    ip_address: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    isp: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: Optional[datetime] = None


class ChatRoomOut(BaseModel):
    id: int
    client_id: int
    client_name: Optional[str] = None
    unread_count: int = 0
    last_message: Optional[str] = None
    last_message_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class ChatMessageCreate(BaseModel):
    message: str


class ChatMessageOut(BaseModel):
    id: int
    room_id: int
    sender_id: int
    sender_name: Optional[str] = None
    sender_role: str
    message: str
    created_at: Optional[datetime] = None
    is_read: bool = False


class ChatGroupCreate(BaseModel):
    name: str
    member_ids: list[int] = []


class ChatGroupOut(BaseModel):
    id: int
    name: str
    created_by: int
    created_by_name: Optional[str] = None
    member_ids: list[int] = []
    member_names: list[str] = []
    unread_count: int = 0
    created_at: Optional[datetime] = None


class ChatGroupMessageCreate(BaseModel):
    message: str


class ChatGroupMessageOut(BaseModel):
    id: int
    group_id: int
    sender_id: int
    sender_name: Optional[str] = None
    message: str
    created_at: Optional[datetime] = None


class TicketCreate(BaseModel):
    client_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    category: str = "Other"
    priority: str = "Medium"


class TicketUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    assigned_to: Optional[int] = None


class TicketOut(BaseModel):
    id: int
    ticket_no: str
    client_id: int
    client_name: Optional[str] = None
    title: str
    description: Optional[str] = None
    category: str
    priority: str
    status: str
    assigned_to: Optional[int] = None
    assigned_to_name: Optional[str] = None
    created_by: Optional[int] = None
    created_by_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    message_count: int = 0
    last_message_at: Optional[datetime] = None


class TicketMessageCreate(BaseModel):
    message: str
    visibility: str = "client"


class TicketMessageOut(BaseModel):
    id: int
    ticket_id: int
    user_id: int
    user_name: Optional[str] = None
    user_role: Optional[str] = None
    message: str
    visibility: str
    created_at: Optional[datetime] = None


class WebphoneProfileBase(BaseModel):
    profile_name: str
    sip_username: str
    sip_password: str
    websocket_url: str
    sip_domain: str
    outbound_proxy: Optional[str] = None
    cli: Optional[str] = None
    status: str = "Active"
    notes: Optional[str] = None


class WebphoneProfileCreate(WebphoneProfileBase):
    pass


class WebphoneProfileUpdate(WebphoneProfileBase):
    pass


class WebphoneProfileOut(WebphoneProfileBase, OrmModel):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class WebphoneCallLogCreate(BaseModel):
    profile_id: Optional[int] = None
    cli: Optional[str] = None
    destination: str
    status: str
    duration: int = 0
    notes: Optional[str] = None


class WebphoneCallLogOut(WebphoneCallLogCreate, OrmModel):
    id: int
    profile_name: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None


class SSHConnectionBase(BaseModel):
    connection_name: str
    host_ip: str
    ssh_port: int = 22
    username: str
    status: str = "Active"
    notes: Optional[str] = None


class SSHConnectionCreate(SSHConnectionBase):
    password: str


class SSHConnectionUpdate(SSHConnectionBase):
    password: Optional[str] = None


class SSHConnectionOut(SSHConnectionBase, OrmModel):
    id: int
    has_password: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SSHConnectionPasswordOut(BaseModel):
    password: str


class AsteriskSoundServerBase(BaseModel):
    cluster_name: str
    server_name: str
    server_ip: str
    ssh_port: int = 22
    root_username: str = "root"
    sounds_path: str = "/usr/share/asterisk/sounds/"
    status: str = "Active"


class AsteriskSoundServerCreate(AsteriskSoundServerBase):
    root_password: str


class AsteriskSoundServerUpdate(AsteriskSoundServerBase):
    root_password: Optional[str] = None


class AsteriskSoundServerOut(AsteriskSoundServerBase, OrmModel):
    id: int
    has_password: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AsteriskSoundFileOut(BaseModel):
    filename: str
    size: int
    modified_at: Optional[datetime] = None


class AsteriskSoundGlobalSearchIn(BaseModel):
    file_name: str
    search_type: str = "contains"
    extension_filter: str = ".wav"
    server_ids: Optional[list[int]] = None


class AsteriskSoundBulkActionIn(BaseModel):
    server_ids: list[int]
    action: str
    mode: str = "all_together"
    command: Optional[str] = None
    delay_seconds: Optional[int] = 10
    confirm_dangerous: bool = False


class TerminalSessionOut(OrmModel):
    id: int
    connection_id: Optional[int] = None
    user_id: int
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    status: str


class TerminalCommandBase(BaseModel):
    title: str
    command: str
    purpose: Optional[str] = None
    category: str = "General"
    risk_level: str = "Safe"


class TerminalCommandCreate(TerminalCommandBase):
    pass


class TerminalCommandUpdate(TerminalCommandBase):
    pass


class TerminalCommandOut(TerminalCommandBase, OrmModel):
    id: int
    created_by: Optional[str] = None
    is_default: bool = False
    created_at: Optional[datetime] = None


class TerminalCommandHistoryCreate(BaseModel):
    connection_id: Optional[int] = None
    command: str


class TerminalCommandHistoryOut(OrmModel):
    id: int
    connection_id: Optional[int] = None
    connection_name: Optional[str] = None
    user_id: int
    username: Optional[str] = None
    command: str
    created_at: Optional[datetime] = None


class BillingSettingOut(OrmModel):
    id: int
    usd_to_inr_rate: float = 83.0


class BillingSettingUpdate(BaseModel):
    usd_to_inr_rate: float


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    client_id: Optional[int] = None
    user: UserOut


class BillingChargeBase(BaseModel):
    client_id: int
    billing_date: date
    cluster_id: Optional[int] = None
    charge_type: str
    description: Optional[str] = None
    amount: float
    currency: str = "USD"


class BillingChargeCreate(BillingChargeBase):
    pass


class BillingChargeUpdate(BillingChargeBase):
    pass


class BillingChargeOut(BillingChargeBase, OrmModel):
    id: int
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    client_name: Optional[str] = None
    cluster_name: Optional[str] = None


class CDRBase(BaseModel):
    client_id: int
    cluster_id: Optional[int] = None
    call_date: datetime
    caller_id: Optional[str] = None
    destination: Optional[str] = None
    duration: int = 0
    disposition: Optional[str] = None
    cost: float = 0
    route: Optional[str] = None
    gateway: Optional[str] = None
    cdr_source: Optional[str] = None


class CDRCreate(CDRBase):
    pass


class CDRUpdate(CDRBase):
    pass


class CDROut(CDRBase, OrmModel):
    id: int
    created_at: Optional[datetime] = None
    client_name: Optional[str] = None
    cluster_name: Optional[str] = None


class ClientLedgerBase(BaseModel):
    client_id: int
    entry_date: date
    entry_type: str
    category: str
    description: Optional[str] = None
    debit_amount: float = 0
    credit_amount: float = 0
    amount_usd: Optional[float] = None
    amount_inr: Optional[float] = None
    exchange_rate: Optional[float] = None


class ClientLedgerCreate(ClientLedgerBase):
    pass


class ClientLedgerOut(ClientLedgerBase, OrmModel):
    id: int
    balance_after_entry: float
    debit_usd: float = 0
    credit_usd: float = 0
    debit_inr: float = 0
    credit_inr: float = 0
    balance_usd: float = 0
    balance_inr: float = 0
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None
    client_name: Optional[str] = None


class ClientLedgerMutationOut(BaseModel):
    success: bool
    entry: ClientLedgerOut


class ClientLedgerPageOut(BaseModel):
    items: list[ClientLedgerOut]
    total: int
    page: int
    page_size: int
    total_pages: int


class WeeklyInvoiceItemOut(OrmModel):
    id: int
    item_type: str
    label: str
    amount: float
    source_ledger_id: Optional[int] = None
    entry_date: Optional[date] = None
    charge_type: Optional[str] = None
    description: Optional[str] = None
    amount_usd: float = 0
    amount_inr: float = 0
    profit_eligible: bool = False
    sort_order: int = 0


class WeeklyInvoiceBase(BaseModel):
    client_id: int
    week_start_date: date
    week_end_date: date
    active_billing_days: int
    daily_expected_billing: float = 800000
    profit_percent: float = 0
    notes: Optional[str] = None


class WeeklyInvoiceCreate(WeeklyInvoiceBase):
    pass


class WeeklyInvoiceOut(WeeklyInvoiceBase, OrmModel):
    id: int
    expected_weekly_billing: float
    billing_charges: float = 0
    profit_amount: float = 0
    actual_usage_billing: float
    data_charges: float = 0
    other_charges: float = 0
    payment_adjustment: float = 0
    payment_amount: float = 0
    adjustment_amount: float = 0
    opening_balance: float = 0
    current_week_payable: float = 0
    payments_this_week: float = 0
    payments_after_week: float = 0
    total_payments_till_today: float = 0
    ledger_balance: float = 0
    final_outstanding: float = 0
    advance_remaining: float = 0
    difference: float
    final_payable: float
    status: str
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    client_name: Optional[str] = None
    items: list[WeeklyInvoiceItemOut] = []


class WeeklyInvoicePreviewOut(BaseModel):
    client_id: int
    client_name: Optional[str] = None
    week_start_date: date
    week_end_date: date
    active_billing_days: int
    daily_expected_billing: float
    profit_percent: float
    billing_charges: float
    data_charges: float
    other_charges: float
    payment_amount: float
    adjustment_amount: float
    opening_balance: float
    current_week_payable: float
    payments_this_week: float
    payments_after_week: float
    total_payments_till_today: float
    ledger_balance: float
    final_outstanding: float
    advance_remaining: float
    profit_amount: float
    actual_usage_billing: float
    final_payable: float
    expected_weekly_billing: float
    difference: float
    status: str
    lines: list[WeeklyInvoiceItemOut]


class DataCostBase(BaseModel):
    client_id: int
    entry_date: date
    quantity: float
    rate: float
    rate_usd: Optional[float] = None
    description: Optional[str] = None


class DataCostCreate(DataCostBase):
    pass


class DataCostOut(DataCostBase, OrmModel):
    id: int
    total_cost: float
    total_cost_usd: float = 0
    exchange_rate: float = 83
    total_cost_inr: float = 0
    created_at: Optional[datetime] = None
    client_name: Optional[str] = None
