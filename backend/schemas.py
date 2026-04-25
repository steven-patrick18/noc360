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
    rtng_vos_id: Optional[int] = None
    client_id: Optional[int] = None
    media1_name: Optional[str] = None
    media1_ip: Optional[str] = None
    media1_vos_id: Optional[int] = None
    media2_name: Optional[str] = None
    media2_ip: Optional[str] = None
    media2_vos_id: Optional[int] = None
    carrier_ip: Optional[str] = None
    ports: Optional[str] = None
    vendor_name: Optional[str] = None
    status: str = "Active"
    notes: Optional[str] = None


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
