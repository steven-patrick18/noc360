from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class VOSPortal(Base):
    __tablename__ = "vos_portals"

    id = Column(Integer, primary_key=True, index=True)
    vos_version = Column(String, nullable=False)
    portal_type = Column(String, nullable=False)
    server_ip = Column(String, nullable=False, index=True)
    status = Column(String, default="Active", index=True)
    username = Column(String, nullable=True)
    password = Column(String, nullable=True)
    anti_hack_url = Column(String, nullable=True)
    anti_hack_password = Column(String, nullable=True)
    uuid = Column(String, nullable=True)
    cdr_panel_url = Column(String, nullable=True)
    web_panel_url = Column(String, nullable=True)
    assigned_to = Column(String, nullable=True)
    assigned_cluster = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    vos_port = Column(Integer, default=80)
    vos_desktop_enabled = Column(Boolean, default=False)
    vos_notes = Column(Text, nullable=True)


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    status = Column(String, default="Active", index=True)
    notes = Column(Text, nullable=True)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    full_name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True)
    status = Column(String, default="Active", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    client = relationship("Client")


class PagePermission(Base):
    __tablename__ = "page_permissions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    page_key = Column(String, nullable=False, index=True)
    can_view = Column(Integer, default=0)
    can_create = Column(Integer, default=0)
    can_edit = Column(Integer, default=0)
    can_delete = Column(Integer, default=0)
    can_export = Column(Integer, default=0)
    user = relationship("User")


class ClientAccess(Base):
    __tablename__ = "client_access"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    user = relationship("User")
    client = relationship("Client")


class BillingSetting(Base):
    __tablename__ = "billing_settings"

    id = Column(Integer, primary_key=True, default=1)
    usd_to_inr_rate = Column(Float, default=83.0, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DialerCluster(Base):
    __tablename__ = "dialer_clusters"

    id = Column(Integer, primary_key=True, index=True)
    cluster_no = Column(Integer, nullable=False, unique=True, index=True)
    account_name = Column(String, nullable=False)
    db_ip = Column(String, nullable=True)
    web_ips = Column(Text, nullable=True)
    asterisk_ips = Column(Text, nullable=True)
    inbound_ip = Column(String, nullable=True)
    user = Column(String, nullable=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True)
    dids_patch = Column(String, nullable=True)
    in_id = Column(String, nullable=True)
    assigned_rdp = Column(String, nullable=True, index=True)
    assigned_rdp_ip = Column(String, nullable=True)
    rdp_vos_id = Column(Integer, ForeignKey("vos_portals.id"), nullable=True, index=True)
    status = Column(String, default="Pending", index=True)
    client = relationship("Client")
    rdp_vos = relationship("VOSPortal")

    @property
    def client_name(self):
        return self.client.name if self.client else None

    @property
    def cluster_name(self):
        return self.account_name

    @property
    def live_rdp_name(self):
        return self.rdp_vos.portal_type if self.rdp_vos else self.assigned_rdp

    @property
    def live_rdp_ip(self):
        return self.rdp_vos.server_ip if self.rdp_vos else self.assigned_rdp_ip


class RDP(Base):
    __tablename__ = "rdp"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    ip = Column(String, unique=True, nullable=False, index=True)
    status = Column(String, default="Active", index=True)
    assigned_to = Column(String, nullable=True)
    assigned_cluster = Column(String, nullable=True)
    notes = Column(Text, nullable=True)


class RoutingGateway(Base):
    __tablename__ = "routing_gateways"

    id = Column(Integer, primary_key=True, index=True)
    gateway_name = Column(String, nullable=False, index=True)
    gateway_ip = Column(String, nullable=True)
    routing_gateway_id = Column(Integer, ForeignKey("vos_portals.id"), nullable=True, index=True)
    rtng_vos_id = Column(Integer, ForeignKey("vos_portals.id"), nullable=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True)
    media1_name = Column(String, nullable=True)
    media1_ip = Column(String, nullable=True)
    media_1_portal_id = Column(Integer, ForeignKey("vos_portals.id"), nullable=True, index=True)
    media1_vos_id = Column(Integer, ForeignKey("vos_portals.id"), nullable=True, index=True)
    media2_name = Column(String, nullable=True)
    media2_ip = Column(String, nullable=True)
    media_2_portal_id = Column(Integer, ForeignKey("vos_portals.id"), nullable=True, index=True)
    media2_vos_id = Column(Integer, ForeignKey("vos_portals.id"), nullable=True, index=True)
    carrier_ip = Column(String, nullable=True)
    ports = Column(String, nullable=True)
    vendor_name = Column(String, nullable=True)
    status = Column(String, default="Active", index=True)
    notes = Column(Text, nullable=True)
    client = relationship("Client")
    routing_gateway_portal = relationship("VOSPortal", foreign_keys=[routing_gateway_id])
    rtng_vos = relationship("VOSPortal", foreign_keys=[rtng_vos_id])
    media_1_portal = relationship("VOSPortal", foreign_keys=[media_1_portal_id])
    media1_vos = relationship("VOSPortal", foreign_keys=[media1_vos_id])
    media_2_portal = relationship("VOSPortal", foreign_keys=[media_2_portal_id])
    media2_vos = relationship("VOSPortal", foreign_keys=[media2_vos_id])

    @property
    def live_gateway_name(self):
        portal = self.routing_gateway_portal or self.rtng_vos
        return portal.portal_type if portal else self.gateway_name

    @property
    def live_gateway_ip(self):
        portal = self.routing_gateway_portal or self.rtng_vos
        return portal.server_ip if portal else self.gateway_ip

    @property
    def live_media1_name(self):
        portal = self.media_1_portal or self.media1_vos
        return portal.portal_type if portal else self.media1_name

    @property
    def live_media1_ip(self):
        portal = self.media_1_portal or self.media1_vos
        return portal.server_ip if portal else self.media1_ip

    @property
    def live_media2_name(self):
        portal = self.media_2_portal or self.media2_vos
        return portal.portal_type if portal else self.media2_name

    @property
    def live_media2_ip(self):
        portal = self.media_2_portal or self.media2_vos
        return portal.server_ip if portal else self.media2_ip


class BillingCharge(Base):
    __tablename__ = "billing_charges"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    billing_date = Column(Date, nullable=False, index=True)
    cluster_id = Column(Integer, ForeignKey("dialer_clusters.id"), nullable=True, index=True)
    charge_type = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    amount = Column(Float, nullable=False, default=0)
    currency = Column(String, default="USD")
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    client = relationship("Client")
    cluster = relationship("DialerCluster")

    @property
    def client_name(self):
        return self.client.name if self.client else None

    @property
    def cluster_name(self):
        return self.cluster.cluster_name if self.cluster else None


class CDR(Base):
    __tablename__ = "cdr"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    cluster_id = Column(Integer, ForeignKey("dialer_clusters.id"), nullable=True, index=True)
    call_date = Column(DateTime, nullable=False, index=True)
    caller_id = Column(String, nullable=True, index=True)
    destination = Column(String, nullable=True, index=True)
    duration = Column(Integer, default=0)
    disposition = Column(String, nullable=True, index=True)
    cost = Column(Float, default=0)
    route = Column(String, nullable=True)
    gateway = Column(String, nullable=True)
    cdr_source = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    client = relationship("Client")
    cluster = relationship("DialerCluster")

    @property
    def client_name(self):
        return self.client.name if self.client else None

    @property
    def cluster_name(self):
        return self.cluster.cluster_name if self.cluster else None


class ClientLedger(Base):
    __tablename__ = "client_ledger"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    entry_date = Column(Date, nullable=False, index=True)
    entry_type = Column(String, nullable=False, index=True)
    category = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    debit_amount = Column(Float, default=0)
    credit_amount = Column(Float, default=0)
    balance_after_entry = Column(Float, default=0)
    amount_usd = Column(Float, default=0)
    exchange_rate = Column(Float, default=83.0)
    amount_inr = Column(Float, default=0)
    debit_usd = Column(Float, default=0)
    credit_usd = Column(Float, default=0)
    debit_inr = Column(Float, default=0)
    credit_inr = Column(Float, default=0)
    balance_usd = Column(Float, default=0)
    balance_inr = Column(Float, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(String, nullable=True)
    client = relationship("Client")

    @property
    def client_name(self):
        return self.client.name if self.client else None


class DataCost(Base):
    __tablename__ = "data_costs"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    entry_date = Column(Date, nullable=False, index=True)
    quantity = Column(Float, default=0)
    rate = Column(Float, default=0)
    rate_usd = Column(Float, default=0)
    total_cost = Column(Float, default=0)
    total_cost_usd = Column(Float, default=0)
    exchange_rate = Column(Float, default=83.0)
    total_cost_inr = Column(Float, default=0)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    client = relationship("Client")

    @property
    def client_name(self):
        return self.client.name if self.client else None
