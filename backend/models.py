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


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    username = Column(String, nullable=True, index=True)
    role = Column(String, nullable=True, index=True)
    action = Column(String, nullable=False, index=True)
    module = Column(String, nullable=False, index=True)
    record_type = Column(String, nullable=True, index=True)
    record_id = Column(Integer, nullable=True, index=True)
    description = Column(Text, nullable=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    ip_address = Column(String, nullable=True)
    country = Column(String, nullable=True)
    city = Column(String, nullable=True)
    isp = Column(String, nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    user = relationship("User")


class ChatRoom(Base):
    __tablename__ = "chat_rooms"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    client = relationship("Client")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("chat_rooms.id"), nullable=False, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    sender_role = Column(String, nullable=False, index=True)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    is_read = Column(Boolean, default=False, index=True)
    room = relationship("ChatRoom")
    sender = relationship("User")


class ChatGroup(Base):
    __tablename__ = "chat_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    creator = relationship("User")


class ChatGroupMember(Base):
    __tablename__ = "chat_group_members"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("chat_groups.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    group = relationship("ChatGroup")
    user = relationship("User")


class ChatGroupMessage(Base):
    __tablename__ = "chat_group_messages"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("chat_groups.id"), nullable=False, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    group = relationship("ChatGroup")
    sender = relationship("User")


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    ticket_no = Column(String, unique=True, nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    title = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    category = Column(String, default="Other", index=True)
    priority = Column(String, default="Medium", index=True)
    status = Column(String, default="Open", index=True)
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)
    client = relationship("Client")
    assignee = relationship("User", foreign_keys=[assigned_to])
    creator = relationship("User", foreign_keys=[created_by])


class TicketMessage(Base):
    __tablename__ = "ticket_messages"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    message = Column(Text, nullable=False)
    visibility = Column(String, default="client", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    ticket = relationship("Ticket")
    user = relationship("User")


class WebphoneProfile(Base):
    __tablename__ = "webphone_profiles"

    id = Column(Integer, primary_key=True, index=True)
    profile_name = Column(String, nullable=False, index=True)
    sip_username = Column(String, nullable=False, index=True)
    sip_password = Column(String, nullable=False)
    websocket_url = Column(String, nullable=False)
    sip_domain = Column(String, nullable=False, index=True)
    outbound_proxy = Column(String, nullable=True)
    cli = Column(String, nullable=True, index=True)
    status = Column(String, default="Active", index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)


class WebphoneCallLog(Base):
    __tablename__ = "webphone_call_logs"

    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey("webphone_profiles.id"), nullable=True, index=True)
    cli = Column(String, nullable=True, index=True)
    destination = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, index=True)
    duration = Column(Integer, default=0)
    notes = Column(Text, nullable=True)
    created_by = Column(String, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    profile = relationship("WebphoneProfile")

    @property
    def profile_name(self):
        return self.profile.profile_name if self.profile else None


class SSHConnection(Base):
    __tablename__ = "ssh_connections"

    id = Column(Integer, primary_key=True, index=True)
    connection_name = Column(String, nullable=False, index=True)
    host_ip = Column(String, nullable=False, index=True)
    ssh_port = Column(Integer, default=22, nullable=False)
    username = Column(String, nullable=False, index=True)
    password = Column(String, nullable=True)
    status = Column(String, default="Active", index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)


class AsteriskSoundServer(Base):
    __tablename__ = "asterisk_sound_servers"

    id = Column(Integer, primary_key=True, index=True)
    cluster_name = Column(String, nullable=False, index=True)
    server_name = Column(String, nullable=False, index=True)
    server_ip = Column(String, nullable=False, index=True)
    ssh_port = Column(Integer, default=22, nullable=False)
    root_username = Column(String, default="root", nullable=False, index=True)
    root_password = Column(String, nullable=True)
    sounds_path = Column(String, default="/usr/share/asterisk/sounds/", nullable=False)
    status = Column(String, default="Active", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)


class TerminalSession(Base):
    __tablename__ = "terminal_sessions"

    id = Column(Integer, primary_key=True, index=True)
    connection_id = Column(Integer, ForeignKey("ssh_connections.id"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    ended_at = Column(DateTime(timezone=True), nullable=True, index=True)
    status = Column(String, default="Open", index=True)
    connection = relationship("SSHConnection")
    user = relationship("User")


class TerminalCommand(Base):
    __tablename__ = "terminal_commands"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False, index=True)
    command = Column(Text, nullable=False)
    purpose = Column(Text, nullable=True)
    category = Column(String, default="General", index=True)
    risk_level = Column(String, default="Safe", index=True)
    created_by = Column(String, nullable=True, index=True)
    is_default = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class TerminalCommandHistory(Base):
    __tablename__ = "terminal_command_history"

    id = Column(Integer, primary_key=True, index=True)
    connection_id = Column(Integer, ForeignKey("ssh_connections.id"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    command = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    connection = relationship("SSHConnection")
    user = relationship("User")

    @property
    def connection_name(self):
        return self.connection.connection_name if self.connection else None

    @property
    def username(self):
        return self.user.username if self.user else None


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


class SystemRoutingPlacement(Base):
    __tablename__ = "system_routing_placements"

    id = Column(Integer, primary_key=True, index=True)
    cluster_id = Column(Integer, ForeignKey("dialer_clusters.id"), nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True)
    routing_gateway_id = Column(Integer, ForeignKey("vos_portals.id"), nullable=True, index=True)
    media_1_id = Column(Integer, ForeignKey("vos_portals.id"), nullable=True, index=True)
    media_2_id = Column(Integer, ForeignKey("vos_portals.id"), nullable=True, index=True)
    inbound_id = Column(String, nullable=True)
    did_patch = Column(String, nullable=True)
    placement_date = Column(Date, nullable=False, default=func.current_date(), index=True)
    status = Column(String, default="Active", index=True)
    notes = Column(Text, nullable=True)
    updated_by = Column(String, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    cluster = relationship("DialerCluster")
    client = relationship("Client")
    routing_gateway = relationship("VOSPortal", foreign_keys=[routing_gateway_id])
    media_1 = relationship("VOSPortal", foreign_keys=[media_1_id])
    media_2 = relationship("VOSPortal", foreign_keys=[media_2_id])


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
