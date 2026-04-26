import base64
import asyncio
import hashlib
import hmac
import ipaddress
import json
import logging
import os
import re
import secrets
import shutil
import sqlite3
import subprocess
import threading
import time
import urllib.request
import zipfile
from collections import Counter
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path

try:
    import bcrypt
except ImportError:  # Keep local/dev imports working until requirements are installed.
    bcrypt = None

try:
    import paramiko
except ImportError:  # Terminal APIs return a clear setup error until requirements are installed.
    paramiko = None

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import inspect, or_, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import Base, DATABASE_PATH, SessionLocal, engine, get_db
from models import ActivityLog, BillingCharge, BillingSetting, CDR, ChatGroup, ChatGroupMember, ChatGroupMessage, ChatMessage, ChatRoom, Client, ClientAccess, ClientLedger, DataCost, DialerCluster, PagePermission, RDP, RoutingGateway, SSHConnection, TerminalSession, Ticket, TicketMessage, User, VOSPortal, WebphoneCallLog, WebphoneProfile
from schemas import (
    ActivityLogOut,
    BillingChargeCreate,
    BillingChargeOut,
    BillingChargeUpdate,
    BillingSettingOut,
    BillingSettingUpdate,
    CDRCreate,
    CDROut,
    CDRUpdate,
    ChatGroupCreate,
    ChatGroupMessageCreate,
    ChatGroupMessageOut,
    ChatGroupOut,
    ChatMessageCreate,
    ChatMessageOut,
    ChatRoomOut,
    ClientAccessIn,
    ClientLedgerCreate,
    ClientLedgerMutationOut,
    ClientLedgerPageOut,
    ClientLedgerOut,
    DataCostCreate,
    DataCostOut,
    ClientCreate,
    ClientOut,
    DialerClusterCreate,
    DialerClusterOut,
    DialerClusterUpdate,
    RDPOut,
    RDPUpdate,
    RoutingGatewayCreate,
    RoutingGatewayOut,
    RoutingGatewayUpdate,
    SSHConnectionCreate,
    SSHConnectionOut,
    SSHConnectionPasswordOut,
    SSHConnectionUpdate,
    LoginIn,
    PagePermissionIn,
    PagePermissionOut,
    PasswordResetIn,
    TokenOut,
    TicketCreate,
    TicketMessageCreate,
    TicketMessageOut,
    TicketOut,
    TicketUpdate,
    UserCreate,
    UserUpdate,
    UserOut,
    VOSPortalCreate,
    VOSPortalOut,
    VOSPortalUpdate,
    WebphoneCallLogCreate,
    WebphoneCallLogOut,
    WebphoneProfileCreate,
    WebphoneProfileOut,
    WebphoneProfileUpdate,
)

logger = logging.getLogger("noc360")

app = FastAPI(title="NOC360 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = os.getenv("SECRET_KEY", "noc360-local-dev-secret")
TOKEN_HOURS = int(os.getenv("TOKEN_HOURS", "12"))
CHARGE_TYPES = {
    "Usage Charges",
    "DID Charges",
    "Data Charges",
    "Server Charges",
    "Port Charges",
    "Setup Charges",
    "Other Charges",
}
LEDGER_CATEGORIES = CHARGE_TYPES | {"Payment", "Adjustment"}
TICKET_CATEGORIES = {"Billing", "Routing", "VOS", "RDP", "DID", "Other"}
TICKET_PRIORITIES = {"Low", "Medium", "High", "Critical"}
TICKET_STATUSES = {"Open", "In Progress", "Waiting Client", "Resolved", "Closed"}
DEFAULT_USD_TO_INR = 83.0
PAGE_KEYS = [
    "dashboard",
    "my_dashboard",
    "business_ai",
    "reports",
    "my_reports",
    "management_portal",
    "billing",
    "my_ledger",
    "clients",
    "cdr",
    "my_cdr",
    "vos_portals",
    "vos_desktop_launcher",
    "dialer_clusters",
    "rdp_media",
    "routing_gateways",
    "user_access",
    "activity_logs",
    "chat_center",
    "my_chat",
    "group_chat",
    "tickets",
    "my_tickets",
    "webphone",
    "terminal",
]
PAGE_KEY_ALIASES = {
    "command_center": "dashboard",
    "intelligence_core": "business_ai",
    "data_intelligence": "reports",
    "money_engine": "billing",
    "vos_desktop": "vos_desktop_launcher",
    "media_nodes": "rdp_media",
    "traffic_control": "routing_gateways",
}
DEFAULT_PERMISSION_KEYS = list(dict.fromkeys([
    "dashboard",
    "command_center",
    "intelligence_core",
    "data_intelligence",
    "management_portal",
    "money_engine",
    "clients",
    "user_access",
    "vos_portals",
    "vos_desktop",
    "dialer_clusters",
    "media_nodes",
    "traffic_control",
    "reports",
    "billing",
    "activity_logs",
    "chat_center",
    "my_chat",
    "group_chat",
    "tickets",
    "my_tickets",
    "webphone",
    "terminal",
    *PAGE_KEYS,
]))
ALLOWED_PERMISSION_KEYS = sorted(set(PAGE_KEYS) | set(DEFAULT_PERMISSION_KEYS) | set(PAGE_KEY_ALIASES))
MODULE_PAGE_MAP = {
    "dashboard": "dashboard",
    "businessAi": "business_ai",
    "reports": "reports",
    "management": "management_portal",
    "billing": "billing",
    "clients": "clients",
    "vos": "vos_portals",
    "clusters": "dialer_clusters",
    "rdps": "rdp_media",
    "gateways": "routing_gateways",
    "userAccess": "user_access",
    "activityLogs": "activity_logs",
    "chatCenter": "chat_center",
    "tickets": "tickets",
    "myChat": "my_chat",
    "myTickets": "my_tickets",
    "webphone": "webphone",
    "terminal": "terminal",
}
ROLE_DEFAULT_PAGES = {
    "admin": PAGE_KEYS,
    "noc_user": ["dashboard", "management_portal", "billing", "reports", "vos_portals", "vos_desktop_launcher", "dialer_clusters", "rdp_media", "routing_gateways", "chat_center", "group_chat", "tickets", "webphone"],
    "viewer": ["dashboard", "reports"],
    "customer": ["my_dashboard", "my_ledger", "my_cdr", "my_reports", "my_chat", "my_tickets"],
}


class ClusterAccountAssignmentIn(BaseModel):
    cluster_id: int
    client_id: int | None = None


class RDPClusterAssignmentIn(BaseModel):
    cluster_id: int
    assigned_rdp: str | None = None
    rdp_vos_id: int | None = None


class RoutingMediaAssignmentIn(BaseModel):
    gateway_name: str
    routing_gateway_id: int | None = None
    rtng_vos_id: int | None = None
    media_1_name: str | None = None
    media_1_portal_id: int | None = None
    media1_name: str | None = None
    media1_vos_id: int | None = None
    media_2_name: str | None = None
    media_2_portal_id: int | None = None
    media2_name: str | None = None
    media2_vos_id: int | None = None
    carrier_ip: str | None = None
    ports: str | None = None
    vendor: str | None = None
    vendor_name: str | None = None
    status: str = "Active"


class ProfileUpdateIn(BaseModel):
    email: str | None = None
    current_password: str
    new_password: str | None = None


class VOSDesktopOut(BaseModel):
    id: int
    vos_name: str
    portal_type: str
    vos_type: str
    server_ip: str | None = None
    status: str | None = None
    username: str | None = None
    anti_hack_url: str | None = None
    web_panel_url: str | None = None
    vos_port: int | None = 80
    vos_desktop_enabled: bool = False
    vos_notes: str | None = None
    has_password: bool = False


class VOSDesktopLoginOut(BaseModel):
    server: str | None = None
    username: str | None = None
    password: str | None = None
    anti_hack_url: str | None = None
    anti_hack_password: str | None = None


class VOSDesktopDetailsOut(BaseModel):
    id: int
    vos_name: str | None = None
    vos_version: str | None = None
    portal_type: str | None = None
    server_ip: str | None = None
    web_panel_url: str | None = None
    username: str | None = None
    password: str | None = None
    anti_hack_url: str | None = None
    anti_hack_password: str | None = None
    uuid: str | None = None
    notes: str | None = None
    vos_notes: str | None = None
    status: str | None = None


class VOSLaunchIn(BaseModel):
    launcher_path: str | None = None
    shortcut_path: str | None = None
    vos_path: str | None = None


class VOSLaunchOut(BaseModel):
    launcher_path: str
    shortcut_path: str
    anti_hack_url: str | None = None
    command: str


class VOSDesktopUpdateIn(BaseModel):
    server_ip: str | None = None
    status: str | None = None
    username: str | None = None
    password: str | None = None
    anti_hack_url: str | None = None
    anti_hack_password: str | None = None
    web_panel_url: str | None = None
    vos_port: int | None = None
    vos_desktop_enabled: bool | None = None
    vos_notes: str | None = None


class ActivityLogTrackIn(BaseModel):
    action: str
    module: str
    record_type: str | None = None
    record_id: int | None = None
    description: str | None = None
    old_value: dict | str | None = None
    new_value: dict | str | None = None


class WebphonePbxConfigIn(BaseModel):
    pbx_domain: str = "pbx.voipzap.com"
    wss_port: int = 8089
    http_port: int = 8088
    rtp_start: int = 10000
    rtp_end: int = 20000
    stun_server: str = "stun.l.google.com:19302"
    sip_username: str = "1001"
    sip_password: str
    cli: str | None = None
    trunk_name: str = "your_trunk"
    trunk_host: str
    trunk_username: str | None = None
    trunk_password: str | None = None
    from_domain: str | None = None
    prefix: str | None = None


class WebphonePbxConnectIn(BaseModel):
    ip: str
    username: str
    password: str


class DangerZoneOptionsIn(BaseModel):
    billing: bool = False
    clients: bool = False
    vos: bool = False
    chat_tickets: bool = False
    webphone: bool = False
    activity_logs: bool = False
    full_factory_reset: bool = False


class DangerZoneClearIn(BaseModel):
    confirm_text: str
    admin_password: str
    options: DangerZoneOptionsIn


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def b64url_decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def hash_password(password: str, salt: str | None = None) -> str:
    if salt is None and bcrypt is not None:
        return f"bcrypt${bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()}"
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    if stored_hash.startswith("bcrypt$"):
        if bcrypt is None:
            return False
        return bcrypt.checkpw(password.encode(), stored_hash.removeprefix("bcrypt$").encode())
    try:
        _, salt, digest = stored_hash.split("$", 2)
    except ValueError:
        return False
    return hmac.compare_digest(hash_password(password, salt), stored_hash)


def canonical_page_key(page_key: str | None):
    return PAGE_KEY_ALIASES.get(page_key or "", page_key)


def permission_values(row: PagePermission):
    return {
        "can_view": bool(row.can_view),
        "can_create": bool(row.can_create),
        "can_edit": bool(row.can_edit),
        "can_delete": bool(row.can_delete),
        "can_export": bool(row.can_export),
    }


def merge_permission(existing: dict | None, incoming: dict):
    if not existing:
        return incoming
    return {
        key: bool(existing.get(key)) or bool(incoming.get(key))
        for key in ["can_view", "can_create", "can_edit", "can_delete", "can_export"]
    }


def permission_dict(db: Session, user: User):
    if user.role == "admin":
        rights = {"can_view": True, "can_create": True, "can_edit": True, "can_delete": True, "can_export": True}
        return {key: rights.copy() for key in ALLOWED_PERMISSION_KEYS}
    rows = db.query(PagePermission).filter(PagePermission.user_id == user.id).all()
    if user.role == "customer":
        customer_pages = set(ROLE_DEFAULT_PAGES["customer"])
        rows = [row for row in rows if canonical_page_key(row.page_key) in customer_pages]
    permissions = {}
    for row in rows:
        values = permission_values(row)
        permissions[row.page_key] = merge_permission(permissions.get(row.page_key), values)
        canonical = canonical_page_key(row.page_key)
        permissions[canonical] = merge_permission(permissions.get(canonical), values)
    if not permissions and user.role in ROLE_DEFAULT_PAGES:
        readonly = user.role in {"viewer", "customer"}
        export_allowed = user.role == "customer"
        permissions = {
            key: {"can_view": True, "can_create": not readonly, "can_edit": not readonly, "can_delete": False, "can_export": export_allowed if readonly else True}
            for key in ROLE_DEFAULT_PAGES[user.role]
        }
    return permissions


def user_client_ids(db: Session, user: User):
    ids = [row.client_id for row in db.query(ClientAccess).filter(ClientAccess.user_id == user.id).all()]
    if user.client_id and user.client_id not in ids:
        ids.append(user.client_id)
    return ids


def user_out(db: Session, user: User):
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role,
        "client_id": user.client_id,
        "client_name": user.client.name if user.client else None,
        "status": user.status,
        "client_ids": user_client_ids(db, user),
        "permissions": permission_dict(db, user),
    }


def create_token(user: User) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "client_id": user.client_id,
        "user_id": user.id,
        "exp": int((datetime.utcnow() + timedelta(hours=TOKEN_HOURS)).timestamp()),
    }
    signing_input = f"{b64url(json.dumps(header, separators=(',', ':')).encode())}.{b64url(json.dumps(payload, separators=(',', ':')).encode())}"
    signature = hmac.new(SECRET_KEY.encode(), signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{b64url(signature)}"


def decode_token(token: str) -> dict:
    try:
        header_payload, signature = token.rsplit(".", 1)
        expected = b64url(hmac.new(SECRET_KEY.encode(), header_payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        payload = json.loads(b64url_decode(header_payload.split(".", 1)[1]))
        if payload.get("exp", 0) < int(datetime.utcnow().timestamp()):
            raise ValueError
        return payload
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc


def current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    payload = decode_token(authorization.split(" ", 1)[1])
    user = db.get(User, int(payload["sub"]))
    if not user or user.status != "Active":
        raise HTTPException(status_code=401, detail="User inactive or missing")
    return user


def require_roles(*roles):
    def checker(user: User = Depends(current_user)):
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return checker


def require_super_admin(user: User = Depends(current_user)):
    super_admin_username = os.getenv("NOC360_SUPER_ADMIN_USERNAME", "admin")
    if user.role != "admin" or user.username != super_admin_username:
        raise HTTPException(status_code=403, detail="Super Admin access required")
    return user


def require_page(page_key: str, action: str = "can_view"):
    def checker(user: User = Depends(current_user), db: Session = Depends(get_db)):
        if user.role == "admin":
            return user
        permission = permission_dict(db, user).get(page_key)
        if not permission or not permission.get(action):
            raise HTTPException(status_code=403, detail="Page permission denied")
        return user
    return checker


def require_vos_desktop(action: str = "can_view"):
    def checker(user: User = Depends(current_user), db: Session = Depends(get_db)):
        if user.role not in {"admin", "noc_user"}:
            raise HTTPException(status_code=403, detail="VOS Desktop access is restricted to admin and NOC users")
        if user.role == "admin":
            return user
        permission = permission_dict(db, user).get("vos_desktop_launcher")
        if not permission or not permission.get(action):
            raise HTTPException(status_code=403, detail="VOS Desktop permission denied")
        return user
    return checker


def require_webphone(action: str = "can_view"):
    def checker(user: User = Depends(current_user), db: Session = Depends(get_db)):
        if user.role not in {"admin", "noc_user"}:
            raise HTTPException(status_code=403, detail="Webphone is restricted to admin and NOC users")
        if user.role == "admin":
            return user
        permission = permission_dict(db, user).get("webphone")
        if not permission or not permission.get(action):
            raise HTTPException(status_code=403, detail="Webphone permission denied")
        return user
    return checker


def require_terminal(action: str = "can_view"):
    def checker(user: User = Depends(current_user), db: Session = Depends(get_db)):
        if user.role not in {"admin", "noc_user"}:
            raise HTTPException(status_code=403, detail="Terminal is restricted to admin and NOC users")
        if user.role == "admin":
            return user
        permission = permission_dict(db, user).get("terminal")
        if not permission or not permission.get(action):
            raise HTTPException(status_code=403, detail="Terminal permission denied")
        return user
    return checker


def has_page_permission(db: Session, user: User, page_key: str, action: str = "can_view"):
    if user.role == "admin":
        return True
    return bool(permission_dict(db, user).get(page_key, {}).get(action))


def ensure_page_permission(db: Session, user: User, page_key: str, action: str = "can_view"):
    if not has_page_permission(db, user, page_key, action):
        raise HTTPException(status_code=403, detail="Forbidden")
    return user


def require_any_page(*checks):
    def checker(user: User = Depends(current_user), db: Session = Depends(get_db)):
        for page_key, action in checks:
            if has_page_permission(db, user, page_key, action):
                return user
        raise HTTPException(status_code=403, detail="Forbidden")
    return checker


def normalize(value):
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


SENSITIVE_LOG_KEYS = {"password", "password_hash", "login_password", "confirm_password", "new_password", "current_password", "anti_hack_password", "sip_password", "trunk_password", "trunk_pass"}
GEO_IP_CACHE: dict[str, dict[str, str | None]] = {}
GEO_IP_PENDING: set[str] = set()
LOCAL_GEO = {"country": "Local", "city": "Internal", "isp": "Local / Internal"}


def get_client_ip(request: Request | None):
    if not request:
        return None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        for part in forwarded.split(","):
            candidate = part.strip()
            if candidate and candidate.lower() != "unknown":
                return candidate
    real_ip = request.headers.get("x-real-ip")
    if real_ip and real_ip.strip().lower() != "unknown":
        return real_ip.strip()
    return request.client.host if request.client else None


def is_local_ip(ip_value: str | None):
    if not ip_value:
        return False
    lowered = ip_value.strip().lower()
    if lowered in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        parsed = ipaddress.ip_address(lowered)
        return parsed.is_private or parsed.is_loopback or parsed.is_link_local or parsed.is_reserved
    except ValueError:
        return False


def empty_geo():
    return {"country": None, "city": None, "isp": None}


def fetch_ip_location(ip_value: str):
    geo = {"country": None, "city": None, "isp": None}
    try:
        with urllib.request.urlopen(f"http://ip-api.com/json/{ip_value}?fields=status,country,city,isp,message", timeout=1.5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("status") == "success":
            geo = {
                "country": normalize(payload.get("country")),
                "city": normalize(payload.get("city")),
                "isp": normalize(payload.get("isp")),
            }
    except Exception:
        logger.debug("IP geo lookup failed for %s", ip_value, exc_info=True)
    return geo


def resolve_ip_location_async(ip_value: str):
    try:
        time.sleep(0.8)
        geo = fetch_ip_location(ip_value)
        GEO_IP_CACHE[ip_value] = geo
        if any(geo.values()):
            with SessionLocal() as geo_db:
                geo_db.query(ActivityLog).filter(ActivityLog.ip_address == ip_value).update(
                    {"country": geo.get("country"), "city": geo.get("city"), "isp": geo.get("isp")},
                    synchronize_session=False,
                )
                geo_db.commit()
    finally:
        GEO_IP_PENDING.discard(ip_value)


def schedule_ip_location_lookup(ip_value: str):
    if not ip_value or ip_value in GEO_IP_PENDING:
        return
    GEO_IP_PENDING.add(ip_value)
    thread = threading.Thread(target=resolve_ip_location_async, args=(ip_value,), daemon=True)
    thread.start()


def lookup_ip_location(ip_value: str | None):
    if not ip_value:
        return empty_geo()
    if is_local_ip(ip_value):
        return LOCAL_GEO.copy()
    if ip_value in GEO_IP_CACHE:
        return GEO_IP_CACHE[ip_value]
    schedule_ip_location_lookup(ip_value)
    return empty_geo()


def sanitize_activity_value(value):
    if value is None:
        return None
    if hasattr(value, "__table__"):
        value = {column.name: getattr(value, column.name) for column in value.__table__.columns}
    if isinstance(value, BaseModel):
        value = value.model_dump()
    if isinstance(value, dict):
        return {
            key: ("[redacted]" if key.lower() in SENSITIVE_LOG_KEYS else sanitize_activity_value(item))
            for key, item in value.items()
            if key.lower() not in {"password_hash"}
        }
    if isinstance(value, list):
        return [sanitize_activity_value(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def activity_json(value):
    cleaned = sanitize_activity_value(value)
    if cleaned is None:
        return None
    if isinstance(cleaned, str):
        return cleaned
    return json.dumps(cleaned, default=str, separators=(",", ":"))


def log_activity(
    db: Session,
    user: User | None,
    action: str,
    module: str,
    record_type: str | None = None,
    record_id: int | None = None,
    description: str | None = None,
    old_value=None,
    new_value=None,
    request: Request | None = None,
    commit: bool = False,
    username: str | None = None,
    role: str | None = None,
):
    try:
        ip_address = get_client_ip(request)
        geo = lookup_ip_location(ip_address)
        db.add(ActivityLog(
            user_id=user.id if user else None,
            username=user.username if user else username,
            role=user.role if user else role,
            action=action,
            module=module,
            record_type=record_type,
            record_id=record_id,
            description=description,
            old_value=activity_json(old_value),
            new_value=activity_json(new_value),
            ip_address=ip_address,
            country=geo.get("country"),
            city=geo.get("city"),
            isp=geo.get("isp"),
            user_agent=request.headers.get("user-agent") if request else None,
        ))
        if commit:
            db.commit()
    except Exception:
        if commit:
            db.rollback()
        logger.exception("Unable to write activity log")


def is_missing(value):
    stripped = normalize(value)
    return stripped is None or stripped.upper() == "#N/A"


def column_default_sql(column):
    default = column.default
    if default is None or not default.is_scalar:
        return ""
    value = default.arg
    if value is None:
        return ""
    if isinstance(value, bool):
        return " DEFAULT TRUE" if value else " DEFAULT FALSE"
    if isinstance(value, (int, float)):
        return f" DEFAULT {value}"
    escaped = str(value).replace("'", "''")
    return f" DEFAULT '{escaped}'"


def ensure_database_schema():
    """Create missing tables and add missing columns without touching live rows."""
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    preparer = engine.dialect.identifier_preparer
    with engine.begin() as connection:
        for table in Base.metadata.sorted_tables:
            if table.name not in table_names:
                continue
            existing_columns = {column["name"] for column in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing_columns:
                    continue
                column_type = column.type.compile(dialect=engine.dialect)
                table_name = preparer.quote(table.name)
                column_name = preparer.quote(column.name)
                ddl = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}{column_default_sql(column)}"
                logger.info("Adding missing database column: %s.%s", table.name, column.name)
                connection.execute(text(ddl))


def create_database():
    ensure_database_schema()


def insert_permission_if_missing(db: Session, user_id: int, page_key: str, rights: dict):
    # INSERT OR IGNORE-style behavior for SQLite/PostgreSQL without overwriting live permissions.
    exists = db.query(PagePermission).filter(PagePermission.user_id == user_id, PagePermission.page_key == page_key).first()
    if exists:
        return False
    db.add(PagePermission(user_id=user_id, page_key=page_key, **rights))
    return True


def default_pages_for_role(role: str):
    if role == "admin":
        return DEFAULT_PERMISSION_KEYS
    return ROLE_DEFAULT_PAGES.get(role, [])


def default_rights_for_role(role: str, page: str | None = None):
    if role == "admin":
        return {"can_view": 1, "can_create": 1, "can_edit": 1, "can_delete": 1, "can_export": 1}
    readonly = role in {"viewer", "customer"}
    export_allowed = role != "viewer"
    rights = {"can_view": 1, "can_create": 0 if readonly else 1, "can_edit": 0 if readonly else 1, "can_delete": 0, "can_export": 1 if export_allowed else 0}
    if role == "customer" and page in {"my_chat", "my_tickets"}:
        rights = {"can_view": 1, "can_create": 1, "can_edit": 0, "can_delete": 0, "can_export": 0}
    if role == "noc_user" and page in {"vos_desktop_launcher", "vos_desktop"}:
        rights = {"can_view": 1, "can_create": 0, "can_edit": 0, "can_delete": 0, "can_export": 1}
    return rights


def seed_user_access_defaults(db: Session):
    clients_by_name = {client.name: client for client in db.query(Client).all()}
    existing_user_count = db.query(User).count()
    bootstrap_users = [
        ("admin", "admin123", "admin", None, "System Admin", "admin@noc360.local"),
        ("noc", "noc123", "noc_user", None, "NOC Operator", "noc@noc360.local"),
        ("viewer", "viewer123", "viewer", None, "Read Only Viewer", "viewer@noc360.local"),
    ]
    if existing_user_count == 0:
        for username, password, role, client_name, full_name, email in bootstrap_users:
            client = clients_by_name.get(client_name) if client_name else None
            db.add(User(username=username, password_hash=hash_password(password), role=role, client_id=client.id if client else None, status="Active", full_name=full_name, email=email))
        db.flush()
    permissions_empty = db.query(PagePermission).count() == 0
    for user in db.query(User).all():
        pages = default_pages_for_role(user.role)
        if permissions_empty and user.role != "admin":
            pages = sorted(set(pages) | {page for page in ROLE_DEFAULT_PAGES.get(user.role, [])})
        existing = {row.page_key for row in db.query(PagePermission).filter(PagePermission.user_id == user.id).all()}
        for page in pages:
            if page not in existing:
                insert_permission_if_missing(db, user.id, page, default_rights_for_role(user.role, page))
        if user.role == "admin":
            for page in DEFAULT_PERMISSION_KEYS:
                insert_permission_if_missing(db, user.id, page, default_rights_for_role(user.role, page))
        if user.client_id and not db.query(ClientAccess).filter(ClientAccess.user_id == user.id, ClientAccess.client_id == user.client_id).first():
            db.add(ClientAccess(user_id=user.id, client_id=user.client_id))
    db.commit()


def get_billing_setting(db: Session):
    setting = db.get(BillingSetting, 1)
    if not setting:
        setting = BillingSetting(id=1, usd_to_inr_rate=DEFAULT_USD_TO_INR)
        db.add(setting)
        db.commit()
        db.refresh(setting)
    return setting


def backfill_reference_ids(db: Session):
    rdp_by_name = {portal.portal_type: portal for portal in get_rdp_portals(db)}
    rtng_by_name = {portal.portal_type: portal for portal in get_rtng_portals(db)}
    media_by_name = {portal.portal_type: portal for portal in get_media_portals(db)}
    changed = False
    for cluster in db.query(DialerCluster).all():
        if cluster.rdp_vos_id is None and normalize(cluster.assigned_rdp) in rdp_by_name:
            cluster.rdp_vos_id = rdp_by_name[normalize(cluster.assigned_rdp)].id
            changed = True
        if cluster.rdp_vos_id and cluster.rdp_vos:
            cluster.assigned_rdp = cluster.rdp_vos.portal_type
            cluster.assigned_rdp_ip = cluster.rdp_vos.server_ip
            changed = True
    for gateway in db.query(RoutingGateway).all():
        if not gateway.routing_gateway_id and gateway.rtng_vos_id:
            gateway.routing_gateway_id = gateway.rtng_vos_id
            changed = True
        if not gateway.rtng_vos_id and gateway.routing_gateway_id:
            gateway.rtng_vos_id = gateway.routing_gateway_id
            changed = True
        if gateway.rtng_vos_id is None and normalize(gateway.gateway_name) in rtng_by_name:
            gateway.rtng_vos_id = gateway.routing_gateway_id = rtng_by_name[normalize(gateway.gateway_name)].id
            changed = True
        if not gateway.media_1_portal_id and gateway.media1_vos_id:
            gateway.media_1_portal_id = gateway.media1_vos_id
            changed = True
        if not gateway.media1_vos_id and gateway.media_1_portal_id:
            gateway.media1_vos_id = gateway.media_1_portal_id
            changed = True
        if gateway.media1_vos_id is None and normalize(gateway.media1_name) in media_by_name:
            gateway.media1_vos_id = gateway.media_1_portal_id = media_by_name[normalize(gateway.media1_name)].id
            changed = True
        if not gateway.media_2_portal_id and gateway.media2_vos_id:
            gateway.media_2_portal_id = gateway.media2_vos_id
            changed = True
        if not gateway.media2_vos_id and gateway.media_2_portal_id:
            gateway.media2_vos_id = gateway.media_2_portal_id
            changed = True
        if gateway.media2_vos_id is None and normalize(gateway.media2_name) in media_by_name:
            gateway.media2_vos_id = gateway.media_2_portal_id = media_by_name[normalize(gateway.media2_name)].id
            changed = True
        rtng = get_gateway_portal(db, gateway)
        media1 = get_media_portal(db, gateway, 1)
        media2 = get_media_portal(db, gateway, 2)
        if rtng:
            if gateway.gateway_name != rtng.portal_type or gateway.gateway_ip != rtng.server_ip:
                gateway.gateway_name, gateway.gateway_ip = rtng.portal_type, rtng.server_ip
                changed = True
        if media1:
            if gateway.media1_name != media1.portal_type or gateway.media1_ip != media1.server_ip:
                gateway.media1_name, gateway.media1_ip = media1.portal_type, media1.server_ip
                changed = True
        if media2:
            if gateway.media2_name != media2.portal_type or gateway.media2_ip != media2.server_ip:
                gateway.media2_name, gateway.media2_ip = media2.portal_type, media2.server_ip
                changed = True
    if changed:
        db.commit()


def normalize_ledger_currency(db: Session):
    changed = False
    for row in db.query(ClientLedger).all():
        rate = float(row.exchange_rate or DEFAULT_USD_TO_INR)
        debit_usd = float(row.debit_usd if row.debit_usd is not None else (row.debit_amount or 0))
        credit_usd = float(row.credit_usd if row.credit_usd is not None else (row.credit_amount or 0))
        if not debit_usd and row.entry_type == "Debit":
            debit_usd = float(row.debit_amount or row.amount_usd or 0)
        if not credit_usd and row.entry_type == "Credit":
            credit_usd = float(row.credit_amount or row.amount_usd or 0)
        amount_usd = debit_usd or credit_usd or float(row.amount_usd or 0)
        existing_debit_inr = float(row.debit_inr or 0)
        existing_credit_inr = float(row.credit_inr or 0)
        existing_amount_inr = float(row.amount_inr or 0)
        debit_inr = existing_debit_inr if existing_debit_inr else debit_usd * rate
        credit_inr = existing_credit_inr if existing_credit_inr else credit_usd * rate
        amount_inr = existing_amount_inr if existing_amount_inr else debit_inr or credit_inr or amount_usd * rate
        row.exchange_rate = rate
        row.amount_usd = round(amount_usd, 2)
        row.amount_inr = round(amount_inr, 2)
        row.debit_usd = round(debit_usd, 2)
        row.credit_usd = round(credit_usd, 2)
        row.debit_inr = round(debit_inr, 2)
        row.credit_inr = round(credit_inr, 2)
        row.debit_amount = row.debit_usd
        row.credit_amount = row.credit_usd
        changed = True
    for client_id in {row.client_id for row in db.query(ClientLedger.client_id).all()}:
        recalc_client_ledger(db, client_id)
        changed = True
    if changed:
        db.commit()


@app.on_event("startup")
def startup():
    create_database()
    with SessionLocal() as db:
        backfill_reference_ids(db)
        get_billing_setting(db)
        normalize_ledger_currency(db)
        normalize_data_cost_currency(db)
        seed_user_access_defaults(db)
        ensure_chat_rooms_for_clients(db)


@app.get("/")
def home():
    return {"message": "NOC360 Backend Running"}

@app.get("/health")
@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/auth/login", response_model=TokenOut)
@app.post("/auth/login", response_model=TokenOut)
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        log_activity(db, None, "login_failed", "auth", "User", user.id if user else None, f"Failed login for {payload.username}", request=request, commit=True, username=payload.username, role=user.role if user else None)
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if user.status != "Active":
        log_activity(db, user, "login_failed", "auth", "User", user.id, "Login blocked because user is inactive", request=request, commit=True)
        raise HTTPException(status_code=403, detail="User is inactive")
    log_activity(db, user, "login_success", "auth", "User", user.id, "Login success", request=request, commit=True)
    return {"access_token": create_token(user), "role": user.role, "client_id": user.client_id, "user": user_out(db, user)}


@app.get("/api/auth/me")
@app.get("/auth/me")
def me(user: User = Depends(current_user)):
    with SessionLocal() as db:
        return user_out(db, db.get(User, user.id))


@app.put("/api/auth/update-profile")
@app.put("/auth/update-profile")
def update_profile(payload: ProfileUpdateIn, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    record = db.get(User, user.id)
    if not record:
        raise HTTPException(status_code=404, detail="User not found")
    if not payload.current_password or not verify_password(payload.current_password, record.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    old_value = {"email": record.email}
    new_password = (payload.new_password or "").strip()
    password_changed = bool(new_password)
    if new_password:
        if len(new_password) < 6:
            raise HTTPException(status_code=400, detail="New password must be at least 6 characters")
        record.password_hash = hash_password(new_password)
    record.email = (payload.email or "").strip() or None
    db.commit()
    db.refresh(record)
    log_activity(db, record, "update_profile", "auth", "User", record.id, "Profile updated; password changed" if password_changed else "Profile updated", old_value=old_value, new_value={"email": record.email, "password_changed": password_changed}, request=request, commit=True)
    return user_out(db, record)


@app.get("/api/activity-logs", response_model=list[ActivityLogOut])
@app.get("/activity-logs", response_model=list[ActivityLogOut])
def get_activity_logs(
    date_from: date | None = None,
    date_to: date | None = None,
    username: str | None = None,
    role: str | None = None,
    module: str | None = None,
    action: str | None = None,
    search: str | None = None,
    limit: int = Query(default=500, ge=1, le=5000),
    db: Session = Depends(get_db),
    user: User = Depends(require_page("activity_logs")),
):
    if user.role == "customer":
        raise HTTPException(status_code=403, detail="Activity logs are restricted")
    query = db.query(ActivityLog)
    if date_from:
        query = query.filter(ActivityLog.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        query = query.filter(ActivityLog.created_at <= datetime.combine(date_to, datetime.max.time()))
    if username:
        query = query.filter(ActivityLog.username.ilike(f"%{username}%"))
    if role:
        query = query.filter(ActivityLog.role == role)
    if module:
        query = query.filter(ActivityLog.module == module)
    if action:
        query = query.filter(ActivityLog.action == action)
    if search:
        query = query.filter(ActivityLog.description.ilike(f"%{search}%"))
    return query.order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc()).limit(limit).all()


@app.get("/api/activity-logs/summary")
@app.get("/activity-logs/summary")
def get_activity_logs_summary(db: Session = Depends(get_db), user: User = Depends(require_page("activity_logs"))):
    if user.role == "customer":
        raise HTTPException(status_code=403, detail="Activity logs are restricted")
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())
    logs = db.query(ActivityLog).filter(ActivityLog.created_at >= today_start).all()
    return {
        "total_today": len(logs),
        "login_attempts": len([row for row in logs if row.action in {"login_success", "login_failed"}]),
        "billing_changes": len([row for row in logs if row.module == "billing"]),
        "user_access_changes": len([row for row in logs if row.module == "user_access"]),
        "vos_credential_actions": len([row for row in logs if row.module == "vos_desktop" and row.action in {"copy_credentials", "launch_desktop", "open_anti_hack"}]),
    }


@app.post("/api/activity-logs/track")
@app.post("/activity-logs/track")
def track_activity(payload: ActivityLogTrackIn, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    allowed_actions = {"logout", "export_report", "copy_credentials", "open_anti_hack", "launch_desktop", "open_web_panel"}
    if payload.action not in allowed_actions:
        raise HTTPException(status_code=400, detail="Unsupported activity action")
    log_activity(db, user, payload.action, payload.module, payload.record_type, payload.record_id, payload.description, payload.old_value, payload.new_value, request=request, commit=True)
    return {"logged": True}


def create_factory_reset_backup():
    backup_dir = Path(__file__).resolve().parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M")
    backup_path = backup_dir / f"factory_reset_before_{timestamp}.db"
    if backup_path.exists():
        backup_path = backup_dir / f"factory_reset_before_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.db"
    try:
        with sqlite3.connect(str(DATABASE_PATH)) as source, sqlite3.connect(str(backup_path)) as target:
            source.backup(target)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Backup failed. Clear operation cancelled: {exc}") from exc
    return backup_path


def delete_all(db: Session, model):
    count = db.query(model).count()
    if count:
        db.query(model).delete(synchronize_session=False)
    return count


def clear_factory_data(db: Session, options: DangerZoneOptionsIn):
    selected = options.model_dump()
    if options.full_factory_reset:
        selected.update({
            "billing": True,
            "clients": True,
            "vos": True,
            "chat_tickets": True,
            "webphone": True,
        })
    selected.pop("full_factory_reset", None)
    if not any(selected.values()):
        raise HTTPException(status_code=400, detail="Select at least one data area to clear")

    counts: dict[str, int] = {}

    def add_count(label: str, value: int):
        counts[label] = counts.get(label, 0) + int(value or 0)

    def clear_billing():
        add_count("client_ledger", delete_all(db, ClientLedger))
        add_count("billing_charges", delete_all(db, BillingCharge))
        add_count("data_costs", delete_all(db, DataCost))

    def clear_chat_tickets():
        add_count("chat_messages", delete_all(db, ChatMessage))
        add_count("chat_group_messages", delete_all(db, ChatGroupMessage))
        add_count("chat_group_members", delete_all(db, ChatGroupMember))
        add_count("chat_groups", delete_all(db, ChatGroup))
        add_count("chat_rooms", delete_all(db, ChatRoom))
        add_count("ticket_messages", delete_all(db, TicketMessage))
        add_count("tickets", delete_all(db, Ticket))

    if selected.get("billing"):
        clear_billing()
    if selected.get("chat_tickets"):
        clear_chat_tickets()
    if selected.get("webphone"):
        add_count("webphone_call_logs", delete_all(db, WebphoneCallLog))
        add_count("webphone_profiles", delete_all(db, WebphoneProfile))
    if selected.get("vos"):
        add_count("routing_gateways", delete_all(db, RoutingGateway))
        add_count("dialer_clusters", delete_all(db, DialerCluster))
        add_count("rdp", delete_all(db, RDP))
        add_count("vos_portals", delete_all(db, VOSPortal))
    if selected.get("clients"):
        # Client deletion must also remove client-owned data to avoid orphaned records.
        if not selected.get("billing"):
            clear_billing()
        if not selected.get("chat_tickets"):
            clear_chat_tickets()
        customer_ids = [row.id for row in db.query(User.id).filter(User.role == "customer").all()]
        if customer_ids:
            db.query(ActivityLog).filter(ActivityLog.user_id.in_(customer_ids)).update({"user_id": None}, synchronize_session=False)
            add_count("client_access", db.query(ClientAccess).filter(ClientAccess.user_id.in_(customer_ids)).delete(synchronize_session=False))
            add_count("customer_page_permissions", db.query(PagePermission).filter(PagePermission.user_id.in_(customer_ids)).delete(synchronize_session=False))
            add_count("customer_users", db.query(User).filter(User.id.in_(customer_ids)).delete(synchronize_session=False))
        add_count("client_access", delete_all(db, ClientAccess))
        db.query(User).filter(User.client_id.isnot(None)).update({"client_id": None}, synchronize_session=False)
        db.query(DialerCluster).update({"client_id": None}, synchronize_session=False)
        db.query(RoutingGateway).update({"client_id": None}, synchronize_session=False)
        add_count("clients", delete_all(db, Client))
    if selected.get("activity_logs"):
        add_count("activity_logs", delete_all(db, ActivityLog))

    return selected, counts


@app.post("/api/admin/danger-zone/clear-data")
@app.post("/admin/danger-zone/clear-data")
def clear_danger_zone_data(payload: DangerZoneClearIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_super_admin)):
    if payload.confirm_text != "CLEAR NOC360 DATA":
        raise HTTPException(status_code=400, detail="Confirmation text does not match")
    if not verify_password(payload.admin_password or "", user.password_hash):
        raise HTTPException(status_code=403, detail="Admin password is incorrect")
    backup_path = create_factory_reset_backup()
    try:
        selected, counts = clear_factory_data(db, payload.options)
        log_activity(
            db,
            user,
            "factory_reset_clear",
            "danger_zone",
            "Database",
            None,
            "Danger Zone data clear completed",
            new_value={"options": selected, "backup_file": str(backup_path), "deleted_counts": counts},
            request=request,
        )
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Clear operation failed after backup. No commit was made: {exc}") from exc
    return {"cleared": True, "backup_file": str(backup_path), "deleted_counts": counts}


def internal_user_ids(db: Session):
    return [row.id for row in db.query(User.id).filter(User.role.in_(["admin", "noc_user"]), User.status == "Active").all()]


def ensure_chat_room(db: Session, client_id: int):
    room = db.query(ChatRoom).filter(ChatRoom.client_id == client_id).first()
    if room:
        return room
    if not db.get(Client, client_id):
        raise HTTPException(status_code=400, detail="Client does not exist")
    room = ChatRoom(client_id=client_id)
    db.add(room)
    db.flush()
    return room


def ensure_chat_rooms_for_clients(db: Session, clients: list[Client] | None = None):
    client_rows = clients if clients is not None else db.query(Client).order_by(Client.name.asc()).all()
    if not client_rows:
        return []
    existing = {room.client_id: room for room in db.query(ChatRoom).filter(ChatRoom.client_id.in_([client.id for client in client_rows])).all()}
    rooms = []
    changed = False
    for client in client_rows:
        room = existing.get(client.id)
        if not room:
            room = ChatRoom(client_id=client.id)
            db.add(room)
            db.flush()
            existing[client.id] = room
            changed = True
        rooms.append(room)
    if changed:
        db.commit()
    return rooms


def can_access_chat_room(db: Session, user: User, room: ChatRoom):
    if user.role in {"admin", "noc_user"} and has_page_permission(db, user, "chat_center"):
        return True
    if user.role == "customer" and has_page_permission(db, user, "my_chat"):
        return room.client_id in user_client_ids(db, user)
    return False


def require_chat_room_access(db: Session, user: User, room_id: int):
    room = db.get(ChatRoom, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Chat room not found")
    if not can_access_chat_room(db, user, room):
        raise HTTPException(status_code=403, detail="Chat access denied")
    return room


def chat_message_out(message: ChatMessage):
    return {
        "id": message.id,
        "room_id": message.room_id,
        "sender_id": message.sender_id,
        "sender_name": message.sender.full_name or message.sender.username if message.sender else None,
        "sender_role": message.sender_role,
        "message": message.message,
        "created_at": message.created_at,
        "is_read": bool(message.is_read),
    }


def chat_room_out(db: Session, room: ChatRoom, user: User):
    last = db.query(ChatMessage).filter(ChatMessage.room_id == room.id).order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc()).first()
    unread = db.query(ChatMessage).filter(ChatMessage.room_id == room.id, ChatMessage.sender_id != user.id, ChatMessage.is_read == False).count()
    return {
        "id": room.id,
        "client_id": room.client_id,
        "client_name": room.client.name if room.client else None,
        "unread_count": unread,
        "last_message": last.message if last else None,
        "last_message_at": last.created_at if last else None,
        "created_at": room.created_at,
    }


def group_out(db: Session, group: ChatGroup, user: User):
    members = db.query(ChatGroupMember).filter(ChatGroupMember.group_id == group.id).all()
    member_users = [member.user for member in members if member.user]
    unread = db.query(ChatGroupMessage).filter(ChatGroupMessage.group_id == group.id, ChatGroupMessage.sender_id != user.id).count()
    return {
        "id": group.id,
        "name": group.name,
        "created_by": group.created_by,
        "created_by_name": group.creator.full_name or group.creator.username if group.creator else None,
        "member_ids": [member.user_id for member in members],
        "member_names": [member.full_name or member.username for member in member_users],
        "unread_count": unread,
        "created_at": group.created_at,
    }


def group_message_out(message: ChatGroupMessage):
    return {
        "id": message.id,
        "group_id": message.group_id,
        "sender_id": message.sender_id,
        "sender_name": message.sender.full_name or message.sender.username if message.sender else None,
        "message": message.message,
        "created_at": message.created_at,
    }


def require_group_access(db: Session, user: User, group_id: int):
    group = db.get(ChatGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if user.role != "admin":
        is_member = db.query(ChatGroupMember).filter(ChatGroupMember.group_id == group_id, ChatGroupMember.user_id == user.id).first()
        if not is_member:
            raise HTTPException(status_code=403, detail="Group access denied")
    return group


def next_ticket_no(db: Session):
    prefix = f"NOC-{date.today().strftime('%Y%m%d')}-"
    count = db.query(Ticket).filter(Ticket.ticket_no.like(f"{prefix}%")).count()
    while True:
        count += 1
        ticket_no = f"{prefix}{count:04d}"
        if not db.query(Ticket).filter(Ticket.ticket_no == ticket_no).first():
            return ticket_no


def ticket_query_for_user(db: Session, user: User):
    query = db.query(Ticket)
    if user.role == "customer":
        query = query.filter(Ticket.client_id.in_(user_client_ids(db, user) or [-1]))
    return query


def can_access_ticket(db: Session, user: User, ticket: Ticket):
    if user.role in {"admin", "noc_user"} and has_page_permission(db, user, "tickets"):
        return True
    if user.role == "customer" and has_page_permission(db, user, "my_tickets"):
        return ticket.client_id in user_client_ids(db, user)
    return False


def require_ticket_access(db: Session, user: User, ticket_id: int):
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if not can_access_ticket(db, user, ticket):
        raise HTTPException(status_code=403, detail="Ticket access denied")
    return ticket


def ticket_out(db: Session, ticket: Ticket, user: User):
    message_query = db.query(TicketMessage).filter(TicketMessage.ticket_id == ticket.id)
    if user.role == "customer":
        message_query = message_query.filter(TicketMessage.visibility == "client")
    last = message_query.order_by(TicketMessage.created_at.desc(), TicketMessage.id.desc()).first()
    return {
        "id": ticket.id,
        "ticket_no": ticket.ticket_no,
        "client_id": ticket.client_id,
        "client_name": ticket.client.name if ticket.client else None,
        "title": ticket.title,
        "description": ticket.description,
        "category": ticket.category,
        "priority": ticket.priority,
        "status": ticket.status,
        "assigned_to": ticket.assigned_to,
        "assigned_to_name": ticket.assignee.full_name or ticket.assignee.username if ticket.assignee else None,
        "created_by": ticket.created_by,
        "created_by_name": ticket.creator.full_name or ticket.creator.username if ticket.creator else None,
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
        "message_count": message_query.count(),
        "last_message_at": last.created_at if last else None,
    }


def ticket_message_out(message: TicketMessage):
    return {
        "id": message.id,
        "ticket_id": message.ticket_id,
        "user_id": message.user_id,
        "user_name": message.user.full_name or message.user.username if message.user else None,
        "user_role": message.user.role if message.user else None,
        "message": message.message,
        "visibility": message.visibility,
        "created_at": message.created_at,
    }


@app.get("/api/communication/summary")
@app.get("/communication/summary")
def communication_summary(db: Session = Depends(get_db), user: User = Depends(current_user)):
    direct_unread = 0
    group_unread = 0
    open_tickets = 0
    if has_page_permission(db, user, "chat_center") or has_page_permission(db, user, "my_chat"):
        rooms = db.query(ChatRoom).all()
        if user.role == "customer":
            allowed = set(user_client_ids(db, user))
            rooms = [room for room in rooms if room.client_id in allowed]
        direct_unread = sum(db.query(ChatMessage).filter(ChatMessage.room_id == room.id, ChatMessage.sender_id != user.id, ChatMessage.is_read == False).count() for room in rooms)
    if has_page_permission(db, user, "group_chat") and user.role != "customer":
        group_ids = [row.group_id for row in db.query(ChatGroupMember).filter(ChatGroupMember.user_id == user.id).all()]
        query = db.query(ChatGroupMessage).filter(ChatGroupMessage.sender_id != user.id)
        if user.role != "admin":
            query = query.filter(ChatGroupMessage.group_id.in_(group_ids or [-1]))
        group_unread = query.count()
    if has_page_permission(db, user, "tickets") or has_page_permission(db, user, "my_tickets"):
        query = ticket_query_for_user(db, user).filter(Ticket.status.notin_(["Resolved", "Closed"]))
        open_tickets = query.count()
    return {"direct_unread": direct_unread, "group_unread": group_unread, "chat_unread": direct_unread + group_unread, "open_tickets": open_tickets}


@app.get("/api/chat/users", response_model=list[UserOut])
@app.get("/chat/users", response_model=list[UserOut])
def get_chat_users(db: Session = Depends(get_db), user: User = Depends(require_page("group_chat"))):
    if user.role == "customer":
        raise HTTPException(status_code=403, detail="Group chat is internal only")
    return [user_out(db, row) for row in db.query(User).filter(User.role.in_(["admin", "noc_user"]), User.status == "Active").order_by(User.username.asc()).all()]


@app.get("/api/chat/rooms", response_model=list[ChatRoomOut])
@app.get("/chat/rooms", response_model=list[ChatRoomOut])
def get_chat_rooms(db: Session = Depends(get_db), user: User = Depends(require_any_page(("chat_center", "can_view"), ("my_chat", "can_view")))):
    client_query = db.query(Client)
    if user.role == "customer":
        client_query = client_query.filter(Client.id.in_(user_client_ids(db, user) or [-1]))
    clients = client_query.order_by(Client.name.asc()).all()
    rooms = ensure_chat_rooms_for_clients(db, clients)
    return [chat_room_out(db, room, user) for room in rooms]


@app.get("/api/chat/rooms/{room_id}/messages", response_model=list[ChatMessageOut])
@app.get("/chat/rooms/{room_id}/messages", response_model=list[ChatMessageOut])
def get_chat_messages(room_id: int, db: Session = Depends(get_db), user: User = Depends(require_any_page(("chat_center", "can_view"), ("my_chat", "can_view")))):
    require_chat_room_access(db, user, room_id)
    messages = db.query(ChatMessage).filter(ChatMessage.room_id == room_id).order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc()).all()
    for message in messages:
        if message.sender_id != user.id and not message.is_read:
            message.is_read = True
    db.commit()
    return [chat_message_out(message) for message in messages]


@app.post("/api/chat/rooms/{room_id}/messages", response_model=ChatMessageOut)
@app.post("/chat/rooms/{room_id}/messages", response_model=ChatMessageOut)
def send_chat_message(room_id: int, payload: ChatMessageCreate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_any_page(("chat_center", "can_create"), ("my_chat", "can_create")))):
    room = require_chat_room_access(db, user, room_id)
    text_value = normalize(payload.message)
    if not text_value:
        raise HTTPException(status_code=400, detail="Message is required")
    record = ChatMessage(room_id=room.id, sender_id=user.id, sender_role=user.role, message=text_value, is_read=False)
    db.add(record)
    db.flush()
    log_activity(db, user, "chat_sent", "chat", "ChatRoom", room.id, f"Chat message sent for {room.client.name if room.client else 'client'}", request=request)
    db.commit()
    db.refresh(record)
    return chat_message_out(record)


@app.put("/api/chat/messages/{message_id}/read", response_model=ChatMessageOut)
@app.put("/chat/messages/{message_id}/read", response_model=ChatMessageOut)
def mark_chat_message_read(message_id: int, db: Session = Depends(get_db), user: User = Depends(require_any_page(("chat_center", "can_view"), ("my_chat", "can_view")))):
    record = get_record(db, ChatMessage, message_id)
    require_chat_room_access(db, user, record.room_id)
    record.is_read = True
    db.commit()
    db.refresh(record)
    return chat_message_out(record)


@app.get("/api/chat/groups", response_model=list[ChatGroupOut])
@app.get("/chat/groups", response_model=list[ChatGroupOut])
def get_chat_groups(db: Session = Depends(get_db), user: User = Depends(require_page("group_chat"))):
    if user.role == "customer":
        raise HTTPException(status_code=403, detail="Group chat is internal only")
    query = db.query(ChatGroup)
    if user.role != "admin":
        group_ids = [row.group_id for row in db.query(ChatGroupMember).filter(ChatGroupMember.user_id == user.id).all()]
        query = query.filter(ChatGroup.id.in_(group_ids or [-1]))
    return [group_out(db, group, user) for group in query.order_by(ChatGroup.created_at.desc(), ChatGroup.id.desc()).all()]


@app.post("/api/chat/groups", response_model=ChatGroupOut)
@app.post("/chat/groups", response_model=ChatGroupOut)
def create_chat_group(payload: ChatGroupCreate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_page("group_chat", "can_create"))):
    if user.role == "customer":
        raise HTTPException(status_code=403, detail="Group chat is internal only")
    name = normalize(payload.name)
    if not name:
        raise HTTPException(status_code=400, detail="Group name is required")
    valid_ids = set(internal_user_ids(db))
    member_ids = sorted(set(payload.member_ids + [user.id]))
    if any(member_id not in valid_ids for member_id in member_ids):
        raise HTTPException(status_code=400, detail="Group members must be active admin/NOC users")
    group = ChatGroup(name=name, created_by=user.id)
    db.add(group)
    db.flush()
    for member_id in member_ids:
        db.add(ChatGroupMember(group_id=group.id, user_id=member_id))
    log_activity(db, user, "group_created", "group_chat", "ChatGroup", group.id, f"Created group chat {group.name}", new_value={"name": name, "member_ids": member_ids}, request=request)
    db.commit()
    db.refresh(group)
    return group_out(db, group, user)


@app.get("/api/chat/groups/{group_id}/messages", response_model=list[ChatGroupMessageOut])
@app.get("/chat/groups/{group_id}/messages", response_model=list[ChatGroupMessageOut])
def get_group_messages(group_id: int, db: Session = Depends(get_db), user: User = Depends(require_page("group_chat"))):
    require_group_access(db, user, group_id)
    return [group_message_out(row) for row in db.query(ChatGroupMessage).filter(ChatGroupMessage.group_id == group_id).order_by(ChatGroupMessage.created_at.asc(), ChatGroupMessage.id.asc()).all()]


@app.post("/api/chat/groups/{group_id}/messages", response_model=ChatGroupMessageOut)
@app.post("/chat/groups/{group_id}/messages", response_model=ChatGroupMessageOut)
def send_group_message(group_id: int, payload: ChatGroupMessageCreate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_page("group_chat", "can_create"))):
    group = require_group_access(db, user, group_id)
    text_value = normalize(payload.message)
    if not text_value:
        raise HTTPException(status_code=400, detail="Message is required")
    record = ChatGroupMessage(group_id=group.id, sender_id=user.id, message=text_value)
    db.add(record)
    db.flush()
    log_activity(db, user, "group_message_sent", "group_chat", "ChatGroup", group.id, f"Group message sent in {group.name}", request=request)
    db.commit()
    db.refresh(record)
    return group_message_out(record)


@app.get("/api/tickets", response_model=list[TicketOut])
@app.get("/tickets", response_model=list[TicketOut])
def get_tickets(
    status: str | None = None,
    client_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_any_page(("tickets", "can_view"), ("my_tickets", "can_view"))),
):
    query = ticket_query_for_user(db, user)
    if status:
        query = query.filter(Ticket.status == status)
    if client_id:
        if user.role == "customer" and client_id not in user_client_ids(db, user):
            raise HTTPException(status_code=403, detail="Cannot view another customer's tickets")
        query = query.filter(Ticket.client_id == client_id)
    return [ticket_out(db, row, user) for row in query.order_by(Ticket.updated_at.desc(), Ticket.id.desc()).all()]


@app.post("/api/tickets", response_model=TicketOut)
@app.post("/tickets", response_model=TicketOut)
def create_ticket(payload: TicketCreate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_any_page(("tickets", "can_create"), ("my_tickets", "can_create")))):
    client_id = payload.client_id
    if user.role == "customer":
        allowed = user_client_ids(db, user)
        client_id = allowed[0] if allowed else user.client_id
    if not client_id or not db.get(Client, client_id):
        raise HTTPException(status_code=400, detail="Valid client is required")
    if user.role == "customer" and client_id not in user_client_ids(db, user):
        raise HTTPException(status_code=403, detail="Cannot create ticket for another customer")
    title = normalize(payload.title)
    if not title:
        raise HTTPException(status_code=400, detail="Ticket title is required")
    if payload.category not in TICKET_CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid ticket category")
    if payload.priority not in TICKET_PRIORITIES:
        raise HTTPException(status_code=400, detail="Invalid ticket priority")
    record = Ticket(ticket_no=next_ticket_no(db), client_id=client_id, title=title, description=payload.description, category=payload.category, priority=payload.priority, status="Open", created_by=user.id)
    db.add(record)
    db.flush()
    log_activity(db, user, "ticket_created", "tickets", "Ticket", record.id, f"Created ticket {record.ticket_no}", new_value=record, request=request)
    db.commit()
    db.refresh(record)
    return ticket_out(db, record, user)


@app.put("/api/tickets/{ticket_id}", response_model=TicketOut)
@app.put("/tickets/{ticket_id}", response_model=TicketOut)
def update_ticket(ticket_id: int, payload: TicketUpdate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_page("tickets", "can_edit"))):
    record = require_ticket_access(db, user, ticket_id)
    old_value = ticket_out(db, record, user)
    if payload.title is not None:
        record.title = normalize(payload.title) or record.title
    if payload.description is not None:
        record.description = payload.description
    if payload.category is not None:
        if payload.category not in TICKET_CATEGORIES:
            raise HTTPException(status_code=400, detail="Invalid ticket category")
        record.category = payload.category
    if payload.priority is not None:
        if payload.priority not in TICKET_PRIORITIES:
            raise HTTPException(status_code=400, detail="Invalid ticket priority")
        record.priority = payload.priority
    status_changed = False
    if payload.status is not None:
        if payload.status not in TICKET_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid ticket status")
        status_changed = record.status != payload.status
        record.status = payload.status
    if payload.assigned_to is not None:
        if payload.assigned_to and payload.assigned_to not in internal_user_ids(db):
            raise HTTPException(status_code=400, detail="Ticket assignee must be an active admin/NOC user")
        record.assigned_to = payload.assigned_to or None
    db.commit()
    db.refresh(record)
    log_activity(db, user, "ticket_status_changed" if status_changed else "ticket_updated", "tickets", "Ticket", record.id, f"Updated ticket {record.ticket_no}", old_value=old_value, new_value=ticket_out(db, record, user), request=request, commit=True)
    return ticket_out(db, record, user)


@app.get("/api/tickets/{ticket_id}/messages", response_model=list[TicketMessageOut])
@app.get("/tickets/{ticket_id}/messages", response_model=list[TicketMessageOut])
def get_ticket_messages(ticket_id: int, db: Session = Depends(get_db), user: User = Depends(require_any_page(("tickets", "can_view"), ("my_tickets", "can_view")))):
    require_ticket_access(db, user, ticket_id)
    query = db.query(TicketMessage).filter(TicketMessage.ticket_id == ticket_id)
    if user.role == "customer":
        query = query.filter(TicketMessage.visibility == "client")
    return [ticket_message_out(row) for row in query.order_by(TicketMessage.created_at.asc(), TicketMessage.id.asc()).all()]


@app.post("/api/tickets/{ticket_id}/messages", response_model=TicketMessageOut)
@app.post("/tickets/{ticket_id}/messages", response_model=TicketMessageOut)
def send_ticket_message(ticket_id: int, payload: TicketMessageCreate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_any_page(("tickets", "can_create"), ("my_tickets", "can_create")))):
    ticket = require_ticket_access(db, user, ticket_id)
    text_value = normalize(payload.message)
    if not text_value:
        raise HTTPException(status_code=400, detail="Message is required")
    visibility = "client" if user.role == "customer" else payload.visibility
    if visibility not in {"client", "internal"}:
        raise HTTPException(status_code=400, detail="Visibility must be client or internal")
    record = TicketMessage(ticket_id=ticket.id, user_id=user.id, message=text_value, visibility=visibility)
    ticket.updated_at = datetime.utcnow()
    db.add(record)
    db.flush()
    log_activity(db, user, "ticket_message_sent", "tickets", "Ticket", ticket.id, f"Ticket message added to {ticket.ticket_no}", new_value={"visibility": visibility}, request=request)
    db.commit()
    db.refresh(record)
    return ticket_message_out(record)


ASTERISK_DIR = Path("/etc/asterisk")
CONFIG_VALUE_PATTERN = re.compile(r"^[A-Za-z0-9_.:/@+\- ]+$")
SECTION_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


def run_safe_command(args: list[str], timeout: int = 10):
    try:
        completed = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
        return {
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "output": (completed.stdout or completed.stderr or "").strip(),
        }
    except FileNotFoundError:
        return {"ok": False, "returncode": 127, "output": f"{args[0]} not found"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "returncode": 124, "output": f"{args[0]} timed out"}


def clean_config_value(name: str, value: str | None, required: bool = True):
    normalized = normalize(value)
    if not normalized:
        if required:
            raise HTTPException(status_code=400, detail=f"{name} is required")
        return ""
    if "\n" in normalized or "\r" in normalized or "[" in normalized or "]" in normalized:
        raise HTTPException(status_code=400, detail=f"{name} contains invalid characters")
    if not CONFIG_VALUE_PATTERN.match(normalized):
        raise HTTPException(status_code=400, detail=f"{name} contains unsupported characters")
    return normalized


def clean_section_name(name: str, value: str | None):
    normalized = clean_config_value(name, value)
    if not SECTION_NAME_PATTERN.match(normalized):
        raise HTTPException(status_code=400, detail=f"{name} must contain only letters, numbers, dots, dashes, or underscores")
    return normalized


def validate_pbx_config(payload: WebphonePbxConfigIn):
    if payload.http_port < 1 or payload.http_port > 65535:
        raise HTTPException(status_code=400, detail="HTTP port is invalid")
    if payload.wss_port < 1 or payload.wss_port > 65535:
        raise HTTPException(status_code=400, detail="WSS port is invalid")
    if payload.rtp_start < 1 or payload.rtp_end > 65535 or payload.rtp_start >= payload.rtp_end:
        raise HTTPException(status_code=400, detail="RTP port range is invalid")
    return {
        "pbx_domain": clean_config_value("PBX domain", payload.pbx_domain),
        "stun_server": clean_config_value("STUN server", payload.stun_server, required=False) or "stun.l.google.com:19302",
        "sip_username": clean_section_name("SIP username", payload.sip_username),
        "sip_password": clean_config_value("SIP password", payload.sip_password),
        "cli": clean_config_value("CLI", payload.cli, required=False),
        "trunk_name": clean_section_name("Trunk name", payload.trunk_name),
        "trunk_host": clean_config_value("Trunk host", payload.trunk_host),
        "trunk_username": clean_config_value("Trunk username", payload.trunk_username, required=False),
        "trunk_password": clean_config_value("Trunk password", payload.trunk_password, required=False),
        "from_domain": clean_config_value("From domain", payload.from_domain, required=False),
        "prefix": clean_config_value("Prefix", payload.prefix, required=False),
        "http_port": payload.http_port,
        "wss_port": payload.wss_port,
        "rtp_start": payload.rtp_start,
        "rtp_end": payload.rtp_end,
    }


def generated_webphone_password():
    return secrets.token_urlsafe(18).replace("-", "A").replace("_", "B")[:18]


def default_pbx_config_for_enable():
    domain = os.getenv("NOC360_PBX_DOMAIN", "pbx.voipzap.com")
    return {
        "pbx_domain": clean_config_value("PBX domain", domain),
        "stun_server": clean_config_value("STUN server", os.getenv("NOC360_PBX_STUN_SERVER", "stun.l.google.com:19302"), required=False) or "stun.l.google.com:19302",
        "sip_username": clean_section_name("SIP username", os.getenv("NOC360_WEBPHONE_SIP_USER", "1001")),
        "sip_password": generated_webphone_password(),
        "cli": clean_config_value("CLI", os.getenv("NOC360_WEBPHONE_CLI", ""), required=False),
        "trunk_name": clean_section_name("Trunk name", os.getenv("NOC360_PBX_TRUNK_NAME", "your_trunk")),
        "trunk_host": clean_config_value("Trunk host", os.getenv("NOC360_PBX_TRUNK_HOST", ""), required=False),
        "trunk_username": clean_config_value("Trunk username", os.getenv("NOC360_PBX_TRUNK_USER", ""), required=False),
        "trunk_password": clean_config_value("Trunk password", os.getenv("NOC360_PBX_TRUNK_PASS", ""), required=False),
        "from_domain": clean_config_value("From domain", os.getenv("NOC360_PBX_FROM_DOMAIN", domain), required=False),
        "prefix": clean_config_value("Prefix", os.getenv("NOC360_PBX_PREFIX", ""), required=False),
        "http_port": int(os.getenv("NOC360_PBX_HTTP_PORT", "8088")),
        "wss_port": int(os.getenv("NOC360_PBX_WSS_PORT", "8089")),
        "rtp_start": int(os.getenv("NOC360_PBX_RTP_START", "10000")),
        "rtp_end": int(os.getenv("NOC360_PBX_RTP_END", "20000")),
    }


def pbx_cert_paths(domain: str):
    root = Path("/etc/letsencrypt/live") / domain
    return root / "fullchain.pem", root / "privkey.pem"


def pbx_status_payload():
    asterisk_binary = shutil.which("asterisk")
    installed = bool(asterisk_binary)
    running_check = run_safe_command(["systemctl", "is-active", "asterisk"], timeout=5)
    running = running_check["ok"] and running_check["output"].strip() == "active"
    version = run_safe_command(["asterisk", "-rx", "core show version"], timeout=8) if installed else {"ok": False, "output": ""}
    transports = run_safe_command(["asterisk", "-rx", "pjsip show transports"], timeout=8) if installed else {"ok": False, "output": ""}
    config_files = {
        "http_conf": (ASTERISK_DIR / "http.conf").exists(),
        "rtp_conf": (ASTERISK_DIR / "rtp.conf").exists(),
        "pjsip_conf": (ASTERISK_DIR / "pjsip.conf").exists(),
        "extensions_conf": (ASTERISK_DIR / "extensions.conf").exists(),
    }
    pjsip_text = ""
    extensions_text = ""
    try:
        pjsip_text = (ASTERISK_DIR / "pjsip.conf").read_text(errors="ignore")
        extensions_text = (ASTERISK_DIR / "extensions.conf").read_text(errors="ignore")
        pjsip_text += "\n" + (ASTERISK_DIR / "pjsip_noc360_webrtc.conf").read_text(errors="ignore")
        extensions_text += "\n" + (ASTERISK_DIR / "extensions_noc360_webrtc.conf").read_text(errors="ignore")
    except OSError:
        pass
    config_ready = "noc360-transport-wss" in pjsip_text and "[webphone-test]" in extensions_text
    wss_ready = "wss" in (transports.get("output") or "").lower() or "noc360-transport-wss" in pjsip_text
    default_fullchain, default_privkey = pbx_cert_paths("pbx.voipzap.com")
    return {
        "installed": installed,
        "running": running,
        "websocket_status": "Configured" if wss_ready else "Not Configured",
        "config_status": "Configured" if config_ready else "Not Configured",
        "ssl_status": "Present" if default_fullchain.exists() and default_privkey.exists() else "Missing",
        "version": version.get("output") or "",
        "transports": transports.get("output") or "",
        "systemctl": running_check.get("output") or "",
        "config_files": config_files,
        "message": "" if installed else "Asterisk is not installed. Please install it manually on the VPS first.",
    }


def backup_asterisk_configs():
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_dir = ASTERISK_DIR / f"noc360_backup_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for file_name in ["http.conf", "rtp.conf", "pjsip.conf", "extensions.conf", "pjsip_noc360_webrtc.conf", "extensions_noc360_webrtc.conf"]:
        source = ASTERISK_DIR / file_name
        if source.exists():
            shutil.copy2(source, backup_dir / file_name)
    return backup_dir


def ensure_asterisk_include(file_name: str, include_name: str):
    path = ASTERISK_DIR / file_name
    existing = path.read_text(errors="ignore") if path.exists() else ""
    include_line = f'#include "{include_name}"'
    if include_line not in existing:
        separator = "\n" if existing and not existing.endswith("\n") else ""
        path.write_text(f"{existing}{separator}{include_line}\n")


def write_pbx_config_files(config: dict):
    fullchain, privkey = pbx_cert_paths(config["pbx_domain"])
    if not fullchain.exists() or not privkey.exists():
        raise HTTPException(status_code=400, detail=f"SSL certificate missing. Run certbot manually for {config['pbx_domain']}.")
    ASTERISK_DIR.mkdir(parents=True, exist_ok=True)
    backup_dir = backup_asterisk_configs()
    trunk_auth_line = f"outbound_auth={config['trunk_name']}-auth" if config["trunk_username"] and config["trunk_password"] else ""
    trunk_auth_block = ""
    if trunk_auth_line:
        trunk_auth_block = f"""
[{config['trunk_name']}-auth]
type=auth
auth_type=userpass
username={config['trunk_username']}
password={config['trunk_password']}
"""
    dial_prefix = config["prefix"] or ""
    from_domain = config["from_domain"] or config["pbx_domain"]
    trunk_block = ""
    if config.get("trunk_host"):
        trunk_block = f"""
[{config['trunk_name']}]
type=endpoint
transport=noc360-transport-udp
context=from-trunk
disallow=all
allow=ulaw,alaw
aors={config['trunk_name']}-aor
direct_media=no
force_rport=yes
rewrite_contact=yes
from_domain={from_domain}
{trunk_auth_line}

[{config['trunk_name']}-aor]
type=aor
contact=sip:{config['trunk_host']}:5060
{trunk_auth_block}
"""
    (ASTERISK_DIR / "http.conf").write_text(f"""[general]
enabled=yes
bindaddr=0.0.0.0
bindport={config['http_port']}
tlsenable=yes
tlsbindaddr=0.0.0.0:{config['wss_port']}
tlscertfile={fullchain}
tlsprivatekey={privkey}
""")
    (ASTERISK_DIR / "rtp.conf").write_text(f"""[general]
rtpstart={config['rtp_start']}
rtpend={config['rtp_end']}
icesupport=yes
stunaddr={config['stun_server']}
""")
    ensure_asterisk_include("pjsip.conf", "pjsip_noc360_webrtc.conf")
    ensure_asterisk_include("extensions.conf", "extensions_noc360_webrtc.conf")
    (ASTERISK_DIR / "pjsip_noc360_webrtc.conf").write_text(f"""; Managed by NOC360 PBX Setup

[noc360-transport-wss]
type=transport
protocol=wss
bind=0.0.0.0

[noc360-transport-udp]
type=transport
protocol=udp
bind=0.0.0.0:5060

[{config['sip_username']}]
type=endpoint
transport=noc360-transport-wss
context=webphone-test
disallow=all
allow=opus,ulaw,alaw
auth={config['sip_username']}-auth
aors={config['sip_username']}-aor
webrtc=yes
use_avpf=yes
media_encryption=dtls
dtls_verify=fingerprint
dtls_setup=actpass
ice_support=yes
rtcp_mux=yes
direct_media=no
force_rport=yes
rewrite_contact=yes
media_use_received_transport=yes
rtp_symmetric=yes

[{config['sip_username']}-aor]
type=aor
max_contacts=5
remove_existing=yes

[{config['sip_username']}-auth]
type=auth
auth_type=userpass
username={config['sip_username']}
password={config['sip_password']}
{trunk_block}
""")
    (ASTERISK_DIR / "extensions_noc360_webrtc.conf").write_text(f"""; Managed by NOC360 PBX Setup

[webphone-test]
exten => _X.,1,NoOp(NOC360 Webphone DID Test)
 same => n,Dial(PJSIP/{dial_prefix}${{EXTEN}}@{config['trunk_name']},60)
 same => n,Hangup()
""")
    return backup_dir


def validate_webphone_profile(payload: WebphoneProfileCreate | WebphoneProfileUpdate):
    if not normalize(payload.profile_name):
        raise HTTPException(status_code=400, detail="Profile name is required")
    if not normalize(payload.sip_username):
        raise HTTPException(status_code=400, detail="SIP username is required")
    if not normalize(payload.sip_password):
        raise HTTPException(status_code=400, detail="SIP password is required")
    websocket_url = normalize(payload.websocket_url)
    if not websocket_url or not websocket_url.lower().startswith("wss://"):
        raise HTTPException(status_code=400, detail="Secure WSS required")
    if not normalize(payload.sip_domain):
        raise HTTPException(status_code=400, detail="SIP domain is required")


def webphone_profile_out(record: WebphoneProfile):
    return {
        "id": record.id,
        "profile_name": record.profile_name,
        "sip_username": record.sip_username,
        "sip_password": record.sip_password,
        "websocket_url": record.websocket_url,
        "sip_domain": record.sip_domain,
        "outbound_proxy": record.outbound_proxy,
        "cli": record.cli,
        "status": record.status,
        "notes": record.notes,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def webphone_call_log_out(record: WebphoneCallLog):
    return {
        "id": record.id,
        "profile_id": record.profile_id,
        "profile_name": record.profile.profile_name if record.profile else None,
        "cli": record.cli,
        "destination": record.destination,
        "status": record.status,
        "duration": record.duration or 0,
        "notes": record.notes,
        "created_by": record.created_by,
        "created_at": record.created_at,
    }


@app.get("/api/webphone/profiles", response_model=list[WebphoneProfileOut])
@app.get("/webphone/profiles", response_model=list[WebphoneProfileOut])
def get_webphone_profiles(db: Session = Depends(get_db), user: User = Depends(require_webphone())):
    return [webphone_profile_out(row) for row in db.query(WebphoneProfile).order_by(WebphoneProfile.profile_name.asc(), WebphoneProfile.id.asc()).all()]


@app.post("/api/webphone/profiles", response_model=WebphoneProfileOut)
@app.post("/webphone/profiles", response_model=WebphoneProfileOut)
def create_webphone_profile(payload: WebphoneProfileCreate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_webphone("can_create"))):
    validate_webphone_profile(payload)
    record = WebphoneProfile(
        profile_name=normalize(payload.profile_name),
        sip_username=normalize(payload.sip_username),
        sip_password=normalize(payload.sip_password),
        websocket_url=normalize(payload.websocket_url),
        sip_domain=normalize(payload.sip_domain),
        outbound_proxy=normalize(payload.outbound_proxy),
        cli=normalize(payload.cli),
        status=payload.status or "Active",
        notes=payload.notes,
    )
    db.add(record)
    db.flush()
    log_activity(db, user, "create", "webphone", "WebphoneProfile", record.id, f"Created Webphone profile {record.profile_name}", new_value=record, request=request)
    db.commit()
    db.refresh(record)
    return webphone_profile_out(record)


@app.put("/api/webphone/profiles/{record_id}", response_model=WebphoneProfileOut)
@app.put("/webphone/profiles/{record_id}", response_model=WebphoneProfileOut)
def update_webphone_profile(record_id: int, payload: WebphoneProfileUpdate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_webphone("can_edit"))):
    validate_webphone_profile(payload)
    record = get_record(db, WebphoneProfile, record_id)
    old_value = sanitize_activity_value(record)
    record.profile_name = normalize(payload.profile_name)
    record.sip_username = normalize(payload.sip_username)
    record.sip_password = normalize(payload.sip_password)
    record.websocket_url = normalize(payload.websocket_url)
    record.sip_domain = normalize(payload.sip_domain)
    record.outbound_proxy = normalize(payload.outbound_proxy)
    record.cli = normalize(payload.cli)
    record.status = payload.status or "Active"
    record.notes = payload.notes
    record.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(record)
    log_activity(db, user, "update", "webphone", "WebphoneProfile", record.id, f"Updated Webphone profile {record.profile_name}", old_value=old_value, new_value=record, request=request, commit=True)
    return webphone_profile_out(record)


@app.delete("/api/webphone/profiles/{record_id}")
@app.delete("/webphone/profiles/{record_id}")
def delete_webphone_profile(record_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(require_webphone("can_delete"))):
    record = get_record(db, WebphoneProfile, record_id)
    old_value = sanitize_activity_value(record)
    db.query(WebphoneCallLog).filter(WebphoneCallLog.profile_id == record.id).update({"profile_id": None})
    db.delete(record)
    log_activity(db, user, "delete", "webphone", "WebphoneProfile", record_id, f"Deleted Webphone profile {record.profile_name}", old_value=old_value, request=request)
    db.commit()
    return {"deleted": True}


@app.get("/api/webphone/call-logs", response_model=list[WebphoneCallLogOut])
@app.get("/webphone/call-logs", response_model=list[WebphoneCallLogOut])
def get_webphone_call_logs(
    profile_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=500, ge=1, le=5000),
    db: Session = Depends(get_db),
    user: User = Depends(require_webphone()),
):
    query = db.query(WebphoneCallLog)
    if profile_id:
        query = query.filter(WebphoneCallLog.profile_id == profile_id)
    if date_from:
        query = query.filter(WebphoneCallLog.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        query = query.filter(WebphoneCallLog.created_at <= datetime.combine(date_to, datetime.max.time()))
    return [webphone_call_log_out(row) for row in query.order_by(WebphoneCallLog.created_at.desc(), WebphoneCallLog.id.desc()).limit(limit).all()]


@app.post("/api/webphone/call-logs", response_model=WebphoneCallLogOut)
@app.post("/webphone/call-logs", response_model=WebphoneCallLogOut)
def create_webphone_call_log(payload: WebphoneCallLogCreate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_webphone("can_create"))):
    if payload.profile_id and not db.get(WebphoneProfile, payload.profile_id):
        raise HTTPException(status_code=400, detail="Webphone profile does not exist")
    destination = normalize(payload.destination)
    if not destination:
        raise HTTPException(status_code=400, detail="Destination is required")
    record = WebphoneCallLog(
        profile_id=payload.profile_id,
        cli=normalize(payload.cli),
        destination=destination,
        status=normalize(payload.status) or "Unknown",
        duration=max(int(payload.duration or 0), 0),
        notes=payload.notes,
        created_by=user.username,
    )
    db.add(record)
    db.flush()
    log_activity(db, user, "webphone_call_test", "webphone", "WebphoneCallLog", record.id, f"Webphone DID test to {destination} ended with {record.status}", new_value={"profile_id": payload.profile_id, "cli": record.cli, "destination": destination, "status": record.status, "duration": record.duration}, request=request)
    db.commit()
    db.refresh(record)
    return webphone_call_log_out(record)


def validate_ssh_connection_payload(payload: SSHConnectionCreate | SSHConnectionUpdate, require_password: bool = False):
    if not normalize(payload.connection_name):
        raise HTTPException(status_code=400, detail="Connection name is required")
    if not normalize(payload.host_ip):
        raise HTTPException(status_code=400, detail="Host/IP is required")
    if not normalize(payload.username):
        raise HTTPException(status_code=400, detail="SSH username is required")
    if require_password and not normalize(getattr(payload, "password", None)):
        raise HTTPException(status_code=400, detail="SSH password is required")
    port = int(payload.ssh_port or 22)
    if port < 1 or port > 65535:
        raise HTTPException(status_code=400, detail="SSH port must be between 1 and 65535")


def terminal_connection_out(record: SSHConnection):
    return {
        "id": record.id,
        "connection_name": record.connection_name,
        "host_ip": record.host_ip,
        "ssh_port": record.ssh_port or 22,
        "username": record.username,
        "status": record.status,
        "notes": record.notes,
        "has_password": bool(record.password),
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def require_paramiko():
    if paramiko is None:
        raise HTTPException(status_code=500, detail="Paramiko is not installed. Run pip install -r requirements.txt")


def open_ssh_client(connection: dict):
    if paramiko is None:
        raise RuntimeError("Paramiko is not installed. Run pip install -r requirements.txt")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=connection["host_ip"],
        port=int(connection.get("ssh_port") or 22),
        username=connection["username"],
        password=connection.get("password") or "",
        timeout=12,
        banner_timeout=12,
        auth_timeout=12,
        look_for_keys=False,
        allow_agent=False,
    )
    return client


def read_ssh_channel(channel):
    while True:
        if channel.recv_ready():
            return channel.recv(4096).decode("utf-8", errors="replace")
        if channel.recv_stderr_ready():
            return channel.recv_stderr(4096).decode("utf-8", errors="replace")
        if channel.closed or channel.exit_status_ready():
            return None
        time.sleep(0.05)


def user_from_ws_token(db: Session, token: str | None):
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    payload = decode_token(token)
    user = db.get(User, int(payload["sub"]))
    if not user or user.status != "Active":
        raise HTTPException(status_code=401, detail="User inactive or missing")
    return user


def assert_terminal_user(db: Session, user: User, action: str = "can_view"):
    if user.role not in {"admin", "noc_user"}:
        raise HTTPException(status_code=403, detail="Terminal is restricted to admin and NOC users")
    if user.role == "admin":
        return
    permission = permission_dict(db, user).get("terminal")
    if not permission or not permission.get(action):
        raise HTTPException(status_code=403, detail="Terminal permission denied")


@app.get("/api/terminal/connections", response_model=list[SSHConnectionOut])
@app.get("/terminal/connections", response_model=list[SSHConnectionOut])
def get_terminal_connections(
    search: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_terminal()),
):
    query = db.query(SSHConnection)
    if search:
        like = f"%{search}%"
        query = query.filter(or_(SSHConnection.connection_name.ilike(like), SSHConnection.host_ip.ilike(like), SSHConnection.username.ilike(like), SSHConnection.notes.ilike(like)))
    return [terminal_connection_out(row) for row in query.order_by(SSHConnection.connection_name.asc(), SSHConnection.id.asc()).all()]


@app.post("/api/terminal/connections", response_model=SSHConnectionOut)
@app.post("/terminal/connections", response_model=SSHConnectionOut)
def create_terminal_connection(payload: SSHConnectionCreate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_terminal("can_create"))):
    validate_ssh_connection_payload(payload, require_password=True)
    record = SSHConnection(
        connection_name=normalize(payload.connection_name),
        host_ip=normalize(payload.host_ip),
        ssh_port=int(payload.ssh_port or 22),
        username=normalize(payload.username),
        password=normalize(payload.password),
        status=payload.status or "Active",
        notes=payload.notes,
    )
    db.add(record)
    db.flush()
    log_activity(db, user, "create_ssh_connection", "terminal", "SSHConnection", record.id, f"Created SSH connection {record.connection_name}", new_value=record, request=request)
    db.commit()
    db.refresh(record)
    return terminal_connection_out(record)


@app.put("/api/terminal/connections/{record_id}", response_model=SSHConnectionOut)
@app.put("/terminal/connections/{record_id}", response_model=SSHConnectionOut)
def update_terminal_connection(record_id: int, payload: SSHConnectionUpdate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_terminal("can_edit"))):
    validate_ssh_connection_payload(payload)
    record = get_record(db, SSHConnection, record_id)
    old_value = sanitize_activity_value(record)
    record.connection_name = normalize(payload.connection_name)
    record.host_ip = normalize(payload.host_ip)
    record.ssh_port = int(payload.ssh_port or 22)
    record.username = normalize(payload.username)
    if normalize(payload.password):
        record.password = normalize(payload.password)
    record.status = payload.status or "Active"
    record.notes = payload.notes
    record.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(record)
    log_activity(db, user, "update_ssh_connection", "terminal", "SSHConnection", record.id, f"Updated SSH connection {record.connection_name}", old_value=old_value, new_value=record, request=request, commit=True)
    return terminal_connection_out(record)


@app.delete("/api/terminal/connections/{record_id}")
@app.delete("/terminal/connections/{record_id}")
def delete_terminal_connection(record_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(require_terminal("can_delete"))):
    record = get_record(db, SSHConnection, record_id)
    old_value = sanitize_activity_value(record)
    db.query(TerminalSession).filter(TerminalSession.connection_id == record.id).update({"connection_id": None}, synchronize_session=False)
    db.delete(record)
    log_activity(db, user, "delete_ssh_connection", "terminal", "SSHConnection", record_id, f"Deleted SSH connection {record.connection_name}", old_value=old_value, request=request)
    db.commit()
    return {"deleted": True}


@app.get("/api/terminal/connections/{record_id}/password", response_model=SSHConnectionPasswordOut)
@app.get("/terminal/connections/{record_id}/password", response_model=SSHConnectionPasswordOut)
def reveal_terminal_connection_password(record_id: int, db: Session = Depends(get_db), user: User = Depends(require_terminal("can_edit"))):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can reveal SSH passwords")
    record = get_record(db, SSHConnection, record_id)
    return {"password": record.password or ""}


@app.post("/api/terminal/connections/{record_id}/test")
@app.post("/terminal/connections/{record_id}/test")
def test_terminal_connection(record_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(require_terminal())):
    require_paramiko()
    record = get_record(db, SSHConnection, record_id)
    connection = {"host_ip": record.host_ip, "ssh_port": record.ssh_port or 22, "username": record.username, "password": record.password}
    try:
        client = open_ssh_client(connection)
        client.close()
    except Exception as exc:
        log_activity(db, user, "test_ssh_connection_failed", "terminal", "SSHConnection", record.id, f"SSH test failed for {record.connection_name}: {exc}", request=request, commit=True)
        raise HTTPException(status_code=400, detail=f"SSH test failed: {exc}") from exc
    log_activity(db, user, "test_ssh_connection", "terminal", "SSHConnection", record.id, f"SSH test succeeded for {record.connection_name}", request=request, commit=True)
    return {"ok": True, "message": "SSH connection successful"}


@app.websocket("/api/terminal/ws/{connection_id}")
@app.websocket("/terminal/ws/{connection_id}")
async def terminal_websocket(websocket: WebSocket, connection_id: int):
    token = websocket.query_params.get("token")
    session_id = None
    user_id = None
    ssh_client = None
    channel = None
    connection_name = None
    try:
        with SessionLocal() as db:
            user = user_from_ws_token(db, token)
            assert_terminal_user(db, user)
            record = db.get(SSHConnection, connection_id)
            if not record:
                await websocket.close(code=1008)
                return
            if (record.status or "Active") != "Active":
                await websocket.close(code=1008)
                return
            connection = {
                "host_ip": record.host_ip,
                "ssh_port": record.ssh_port or 22,
                "username": record.username,
                "password": record.password,
            }
            connection_name = record.connection_name
            session = TerminalSession(connection_id=record.id, user_id=user.id, status="Opening")
            db.add(session)
            db.flush()
            session_id = session.id
            user_id = user.id
            log_activity(db, user, "terminal_session_opened", "terminal", "TerminalSession", session.id, f"Terminal session opened for {record.connection_name}", new_value={"connection_id": record.id, "connection_name": record.connection_name}, request=websocket, commit=False)
            db.commit()

        await websocket.accept()
        await websocket.send_text(f"\r\nConnecting to {connection_name}...\r\n")
        ssh_client = await asyncio.to_thread(open_ssh_client, connection)
        channel = await asyncio.to_thread(ssh_client.invoke_shell, "xterm", 120, 36)
        channel.settimeout(0.0)
        await websocket.send_text("\r\nConnected.\r\n")
        with SessionLocal() as db:
            session = db.get(TerminalSession, session_id)
            if session:
                session.status = "Connected"
                db.commit()

        async def ssh_to_ws():
            while True:
                data = await asyncio.to_thread(read_ssh_channel, channel)
                if data is None:
                    break
                if data:
                    await websocket.send_text(data)

        async def ws_to_ssh():
            while True:
                data = await websocket.receive_text()
                if data.startswith("__resize__:"):
                    try:
                        _, cols, rows = data.split(":", 2)
                        await asyncio.to_thread(channel.resize_pty, int(cols), int(rows))
                    except Exception:
                        pass
                    continue
                await asyncio.to_thread(channel.send, data)

        tasks = [asyncio.create_task(ssh_to_ws()), asyncio.create_task(ws_to_ssh())]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        for task in done:
            task.result()
    except WebSocketDisconnect:
        pass
    except HTTPException:
        if websocket.client_state.name != "DISCONNECTED":
            await websocket.close(code=1008)
    except Exception as exc:
        logger.exception("Terminal websocket failed")
        try:
            if websocket.client_state.name != "DISCONNECTED":
                await websocket.send_text(f"\r\nTerminal error: {exc}\r\n")
        except Exception:
            pass
    finally:
        try:
            if channel:
                channel.close()
        except Exception:
            pass
        try:
            if ssh_client:
                ssh_client.close()
        except Exception:
            pass
        if session_id:
            with SessionLocal() as db:
                session = db.get(TerminalSession, session_id)
                user = db.get(User, user_id) if user_id else None
                if session:
                    session.status = "Closed"
                    session.ended_at = datetime.utcnow()
                    log_activity(db, user, "terminal_session_closed", "terminal", "TerminalSession", session.id, f"Terminal session closed for {connection_name or 'SSH connection'}", request=websocket, commit=False)
                    db.commit()


@app.get("/api/webphone/pbx/status")
@app.get("/webphone/pbx/status")
def get_webphone_pbx_status(user: User = Depends(require_webphone())):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="PBX Setup is restricted to admin")
    return pbx_status_payload()


@app.post("/api/webphone/pbx/connect")
@app.post("/webphone/pbx/connect")
def connect_webphone_pbx(payload: WebphonePbxConnectIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    ip_value = clean_config_value("IP", payload.ip)
    clean_config_value("Username", payload.username)
    if not normalize(payload.password):
        raise HTTPException(status_code=400, detail="Password is required")
    status = pbx_status_payload()
    if not status["installed"]:
        raise HTTPException(status_code=400, detail="Asterisk is not installed. Please install it manually on the VPS first.")
    if not status["running"]:
        raise HTTPException(status_code=400, detail="Asterisk is installed but not running.")
    log_activity(db, user, "pbx_connected", "webphone", "Asterisk", None, f"PBX connection checked for {ip_value}", new_value={"ip": ip_value, "username": payload.username, "password": "[redacted]"}, request=request, commit=True)
    return {"connected": True, "status": status}


@app.get("/api/webphone/pbx/install-guide")
@app.get("/webphone/pbx/install-guide")
def download_webphone_pbx_guide(user: User = Depends(require_webphone())):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="PBX Setup is restricted to admin")
    guide_path = Path(__file__).resolve().parent.parent / "docs" / "ASTERISK_WEBRTC_SETUP.md"
    if not guide_path.exists():
        raise HTTPException(status_code=404, detail="Asterisk install guide is missing")
    return FileResponse(guide_path, media_type="text/markdown", filename="ASTERISK_WEBRTC_SETUP.md")


def upsert_webphone_profile_from_config(db: Session, config: dict):
    profile_name = f"{config['pbx_domain']} DID Test"
    profile = db.query(WebphoneProfile).filter(WebphoneProfile.profile_name == profile_name).first()
    if not profile:
        profile = WebphoneProfile(profile_name=profile_name)
        db.add(profile)
    profile.sip_username = config["sip_username"]
    profile.sip_password = config["sip_password"]
    profile.websocket_url = f"wss://{config['pbx_domain']}:{config['wss_port']}/ws"
    profile.sip_domain = config["pbx_domain"]
    profile.outbound_proxy = None
    profile.cli = config["cli"] or None
    profile.status = "Active"
    profile.notes = f"Auto-created by PBX Setup. Dialplan trunk: {config['trunk_name']}"
    profile.updated_at = datetime.utcnow()
    db.flush()
    return profile


@app.post("/api/webphone/pbx/enable-webrtc")
@app.post("/webphone/pbx/enable-webrtc")
def enable_webphone_webrtc(request: Request, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    if not shutil.which("asterisk"):
        raise HTTPException(status_code=400, detail="Asterisk is not installed. Please install it manually on the VPS first.")
    config = default_pbx_config_for_enable()
    backup_dir = write_pbx_config_files(config)
    restart = run_safe_command(["systemctl", "restart", "asterisk"], timeout=20)
    if not restart["ok"]:
        reload_result = run_safe_command(["asterisk", "-rx", "core reload"], timeout=12)
        if not reload_result["ok"]:
            raise HTTPException(status_code=500, detail=f"Asterisk config written but restart/reload failed: {restart['output'] or reload_result['output']}")
    profile = upsert_webphone_profile_from_config(db, config)
    log_activity(
        db,
        user,
        "pbx_webrtc_enabled",
        "webphone",
        "WebphoneProfile",
        profile.id,
        "WebRTC enabled successfully from simplified PBX Setup",
        new_value={**config, "backup_dir": str(backup_dir), "sip_password": "[redacted]", "trunk_password": "[redacted]"},
        request=request,
    )
    db.commit()
    db.refresh(profile)
    return {"enabled": True, "message": "WebRTC Enabled Successfully", "backup_dir": str(backup_dir), "profile": webphone_profile_out(profile), "status": pbx_status_payload()}


@app.post("/api/webphone/pbx/configure")
@app.post("/webphone/pbx/configure")
def configure_webphone_pbx(payload: WebphonePbxConfigIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    if not shutil.which("asterisk"):
        raise HTTPException(status_code=400, detail="Asterisk is not installed. Please install it manually on the VPS first.")
    config = validate_pbx_config(payload)
    backup_dir = write_pbx_config_files(config)
    restart = run_safe_command(["systemctl", "restart", "asterisk"], timeout=20)
    if not restart["ok"]:
        reload_result = run_safe_command(["asterisk", "-rx", "core reload"], timeout=12)
        if not reload_result["ok"]:
            raise HTTPException(status_code=500, detail=f"Asterisk config written but restart/reload failed: {restart['output'] or reload_result['output']}")
    profile = upsert_webphone_profile_from_config(db, config)
    log_activity(
        db,
        user,
        "pbx_config_applied",
        "webphone",
        "WebphoneProfile",
        profile.id,
        f"PBX WebRTC config applied for {config['pbx_domain']}",
        new_value={**config, "backup_dir": str(backup_dir), "sip_password": "[redacted]", "trunk_password": "[redacted]"},
        request=request,
    )
    db.commit()
    db.refresh(profile)
    return {"configured": True, "backup_dir": str(backup_dir), "profile": webphone_profile_out(profile), "status": pbx_status_payload()}


@app.post("/api/webphone/pbx/restart")
@app.post("/webphone/pbx/restart")
def restart_webphone_pbx(request: Request, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    if not shutil.which("asterisk"):
        raise HTTPException(status_code=400, detail="Asterisk is not installed. Please install it manually on the VPS first.")
    result = run_safe_command(["systemctl", "restart", "asterisk"], timeout=20)
    if not result["ok"]:
        raise HTTPException(status_code=500, detail=result["output"] or "Asterisk restart failed")
    log_activity(db, user, "pbx_restarted", "webphone", "Asterisk", None, "Asterisk restarted from NOC360 PBX Setup", request=request, commit=True)
    return {"restarted": True, "status": pbx_status_payload()}


def seed_data(db: Session):
    for name in ["IM1", "IM2", "IM3", "ROLEX"]:
        if not db.query(Client).filter(Client.name == name).first():
            db.add(Client(name=name, status="Active", notes="Seed customer"))
    if not db.query(Client).first():
        db.add_all([Client(name="Apex Telecom", status="Active"), Client(name="BlueWave Connect", status="Active")])
    db.flush()

    seed_users = [
        ("admin", "admin123", "admin", None),
        ("noc", "noc123", "noc_user", None),
        ("im1", "123", "customer", "IM1"),
        ("im2", "123", "customer", "IM2"),
        ("im3", "123", "customer", "IM3"),
        ("rolex", "123", "customer", "ROLEX"),
    ]
    for username, password, role, client_name in seed_users:
        if not db.query(User).filter(User.username == username).first():
            client = db.query(Client).filter(Client.name == client_name).first() if client_name else None
            db.add(User(username=username, password_hash=hash_password(password), role=role, client_id=client.id if client else None))
    db.flush()

    existing_rdp_names = {rdp.name for rdp in db.query(RDP).all()}
    rdps = [
        RDP(name="RDP02", ip="10.20.2.10", status="Active", assigned_to="Dialer Ops", assigned_cluster="Cluster 2", notes="Primary media node"),
        RDP(name="RDP12", ip="10.20.12.10", status="Active", assigned_to="Dialer Ops", assigned_cluster="Cluster 12", notes="High volume"),
        RDP(name="RDP13", ip="10.20.13.10", status="Pending", assigned_to="Provisioning", assigned_cluster=None, notes="Awaiting firewall"),
        RDP(name="RDP14", ip="10.20.14.10", status="Inactive", assigned_to=None, assigned_cluster=None, notes="Maintenance hold"),
        RDP(name="RDP15", ip="10.20.15.10", status="Active", assigned_to="Dialer Ops", assigned_cluster="Cluster 15", notes="Inbound backup"),
        RDP(name="RDP17", ip="#N/A", status="Pending", assigned_to="Provisioning", assigned_cluster=None, notes="IP pending"),
    ]
    db.add_all([rdp for rdp in rdps if rdp.name not in existing_rdp_names])

    if not db.query(DialerCluster).first():
        clients = db.query(Client).order_by(Client.id.asc()).all()
        clusters = []
        for number in range(1, 16):
            assigned = {2: "RDP02", 12: "RDP12", 15: "RDP15"}.get(number)
            assigned_ip = {2: "10.20.2.10", 12: "10.20.12.10", 15: "10.20.15.10"}.get(number)
            client = clients[(number - 1) % len(clients)] if clients else None
            clusters.append(
                DialerCluster(
                    cluster_no=number,
                    account_name=f"NOC Dialer Cluster {number:02d}",
                    db_ip=f"172.16.{number}.10" if number != 7 else "#N/A",
                    web_ips=f"172.16.{number}.20, 172.16.{number}.21",
                    asterisk_ips=f"172.16.{number}.30, 172.16.{number}.31",
                    inbound_ip=f"172.16.{number}.40" if number != 11 else "",
                    client_id=client.id if client else None,
                    dids_patch=f"DID-PATCH-{number:02d}",
                    in_id=f"IN-{1000 + number}",
                    assigned_rdp=assigned,
                    assigned_rdp_ip=assigned_ip,
                    status="Active" if number in {1, 2, 3, 4, 5, 12, 15} else "Pending",
                )
            )
        db.add_all(clusters)
    else:
        clients = db.query(Client).order_by(Client.id.asc()).all()
        for index, cluster in enumerate(db.query(DialerCluster).order_by(DialerCluster.cluster_no.asc()).all()):
            if cluster.client_id is None and clients:
                cluster.client_id = clients[index % len(clients)].id

    if not db.query(VOSPortal).first():
        db.add_all(
            [
                VOSPortal(vos_version="VOS3000 2.1.8", portal_type="Admin", server_ip="10.50.1.11", status="Active", username="admin", password="change-me", anti_hack_url="https://vos01.example.com/antihack", anti_hack_password="change-me", uuid="VOS-01", cdr_panel_url="https://vos01.example.com/cdr", web_panel_url="https://vos01.example.com"),
                VOSPortal(vos_version="VOS3000 2.1.8", portal_type="CDR", server_ip="10.50.1.12", status="Active", username="cdr", password="change-me", anti_hack_url="https://vos02.example.com/antihack", anti_hack_password="change-me", uuid="VOS-02", cdr_panel_url="https://vos02.example.com/cdr", web_panel_url="https://vos02.example.com"),
                VOSPortal(vos_version="VOS3000 2.1.6", portal_type="Backup", server_ip="#N/A", status="Pending", username="backup", password="change-me", uuid="VOS-BK"),
            ]
        )
        db.flush()

    existing_portal_types = {portal.portal_type for portal in db.query(VOSPortal).all()}
    rdp_portals = [
        VOSPortal(vos_version="VOS3000 2.1.8", portal_type=rdp.name, server_ip=rdp.ip, status=rdp.status, assigned_to=rdp.assigned_to, assigned_cluster=rdp.assigned_cluster, notes=rdp.notes)
        for rdp in db.query(RDP).all()
        if rdp.name and rdp.name.upper().startswith("RDP") and rdp.name not in existing_portal_types
    ]
    db.add_all(rdp_portals)
    existing_portal_types.update(portal.portal_type for portal in rdp_portals)

    rtng_portals = [
        VOSPortal(vos_version="VOS3000 2.1.8", portal_type=f"RTNG{i:02d}", server_ip=f"10.60.{i}.10", status="Active" if i <= 4 else "Pending")
        for i in range(1, 7)
        if f"RTNG{i:02d}" not in existing_portal_types
    ]
    db.add_all(rtng_portals)

    if not db.query(RoutingGateway).first():
        db.add_all(
            [
                RoutingGateway(gateway_name=f"RTNG{i:02d}", gateway_ip=f"10.60.{i}.10", media1_name=f"RDP{i + 1:02d}", media1_ip=f"10.20.{i + 1}.10", media2_name=f"RDP{i + 11:02d}", media2_ip=f"10.20.{i + 11}.10", carrier_ip=f"192.168.{i}.1", ports="5060, 10000-20000", vendor_name="Telecom Carrier", status="Active" if i <= 4 else "Pending")
                for i in range(1, 7)
            ]
        )
    seed_billing_and_cdr(db)
    db.commit()


def list_records(db: Session, model):
    return db.query(model).order_by(model.id.desc()).all()


def seed_billing_and_cdr(db: Session):
    clients = db.query(Client).filter(Client.name.in_(["IM1", "IM2", "IM3", "ROLEX"])).all()
    clusters = db.query(DialerCluster).order_by(DialerCluster.cluster_no.asc()).all()
    today = date.today()
    if db.query(ClientLedger).first():
        ledger_seeded = True
    else:
        ledger_seeded = False
    if db.query(BillingCharge).first() or db.query(CDR).first():
        if not ledger_seeded:
            seed_client_ledger(db, clients, today)
        seed_data_costs(db, clients, today)
        return
    for index, client in enumerate(clients):
        cluster = clusters[index % len(clusters)] if clusters else None
        for days_ago in range(0, 10):
            billing_date = today - timedelta(days=days_ago)
            db.add(
                BillingCharge(
                    client_id=client.id,
                    cluster_id=cluster.id if cluster else None,
                    billing_date=billing_date,
                    charge_type="Usage Charges",
                    description=f"Daily traffic usage {billing_date.isoformat()}",
                    amount=round(25 + index * 7 + days_ago * 1.35, 2),
                    currency="USD",
                    created_by="seed",
                )
            )
        for charge_type, amount in [("DID Charges", 12.5), ("Data Charges", 8.75), ("Other Charges", 5.0)]:
            db.add(BillingCharge(client_id=client.id, cluster_id=cluster.id if cluster else None, billing_date=today, charge_type=charge_type, description=charge_type, amount=amount + index, currency="USD", created_by="seed"))
        for call_index in range(1, 18):
            db.add(CDR(client_id=client.id, cluster_id=cluster.id if cluster else None, call_date=datetime.utcnow() - timedelta(hours=call_index * 3), caller_id=f"1202555{index}{call_index:03d}", destination=f"44{call_index:09d}", duration=30 + call_index * 9, disposition="ANSWERED" if call_index % 4 else "FAILED", cost=round((30 + call_index * 9) / 60 * 0.018, 4), route="INTL-A", gateway=f"RTNG{(index % 6) + 1:02d}", cdr_source="seed"))

    if not ledger_seeded:
        seed_client_ledger(db, clients, today)
    seed_data_costs(db, clients, today)


def seed_client_ledger(db: Session, clients, today):
    for index, client in enumerate(clients):
        balance = 0
        for days_ago in range(9, -1, -1):
            amount = round(25 + index * 7 + days_ago * 1.35, 2)
            balance += amount
            db.add(ClientLedger(client_id=client.id, entry_date=today - timedelta(days=days_ago), entry_type="Debit", category="Usage Charges", description="Daily usage charges", debit_amount=amount, credit_amount=0, balance_after_entry=round(balance, 2), amount_usd=amount, exchange_rate=DEFAULT_USD_TO_INR, amount_inr=round(amount * DEFAULT_USD_TO_INR, 2), debit_usd=amount, credit_usd=0, debit_inr=round(amount * DEFAULT_USD_TO_INR, 2), credit_inr=0, balance_usd=round(balance, 2), balance_inr=round(balance * DEFAULT_USD_TO_INR, 2), created_by="seed"))
        payment = round(balance * 0.35, 2)
        balance -= payment
        db.add(ClientLedger(client_id=client.id, entry_date=today, entry_type="Credit", category="Payment", description="Customer payment", debit_amount=0, credit_amount=payment, balance_after_entry=round(balance, 2), amount_usd=payment, exchange_rate=DEFAULT_USD_TO_INR, amount_inr=round(payment * DEFAULT_USD_TO_INR, 2), debit_usd=0, credit_usd=payment, debit_inr=0, credit_inr=round(payment * DEFAULT_USD_TO_INR, 2), balance_usd=round(balance, 2), balance_inr=round(balance * DEFAULT_USD_TO_INR, 2), created_by="seed"))


def seed_data_costs(db: Session, clients, today):
    if db.query(DataCost).first():
        return
    for index, client in enumerate(clients):
        for days_ago in range(0, 10):
            quantity = 100 + index * 24 + days_ago * 5
            rate = round(0.08 + index * 0.01, 4)
            total = round(quantity * rate, 2)
            db.add(DataCost(client_id=client.id, entry_date=today - timedelta(days=days_ago), quantity=quantity, rate=rate, rate_usd=rate, total_cost=total, total_cost_usd=total, exchange_rate=DEFAULT_USD_TO_INR, total_cost_inr=round(total * DEFAULT_USD_TO_INR, 2), description="Bandwidth/data cost"))


def get_record(db: Session, model, record_id: int):
    record = db.get(model, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return record


def save_record(db: Session, record):
    try:
        db.add(record)
        db.commit()
        db.refresh(record)
        return record
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Duplicate or invalid record") from exc


def delete_record(db: Session, model, record_id: int):
    record = get_record(db, model, record_id)
    db.delete(record)
    db.commit()
    return {"deleted": True}


def scoped_client_id(requested_client_id: int | None, user: User):
    if user.role == "customer":
        return user.client_id
    return requested_client_id


def scoped_client_ids(db: Session, user: User, requested_ids=None):
    if user.role == "admin":
        return requested_ids or []
    allowed = user_client_ids(db, user)
    if user.role == "customer":
        return allowed
    if requested_ids:
        return [client_id for client_id in requested_ids if client_id in allowed] if allowed else requested_ids
    return allowed


def client_financial_totals(db: Session, client_id: int):
    rows = db.query(ClientLedger).filter(ClientLedger.client_id == client_id).all()
    debit_usd = sum(row.debit_usd or row.debit_amount or 0 for row in rows)
    credit_usd = sum(row.credit_usd or row.credit_amount or 0 for row in rows)
    debit_inr = sum(row.debit_inr or 0 for row in rows)
    credit_inr = sum(row.credit_inr or 0 for row in rows)
    return {
        "outstanding_usd": round(debit_usd - credit_usd, 2),
        "outstanding_inr": round(debit_inr - credit_inr, 2),
    }


def row_debit_usd(row):
    return float(row.debit_usd if row.debit_usd is not None else (row.debit_amount or 0))


def row_credit_usd(row):
    return float(row.credit_usd if row.credit_usd is not None else (row.credit_amount or 0))


def row_debit_inr(row):
    value = row.debit_inr
    if value is not None and value != 0:
        return float(value)
    return round(row_debit_usd(row) * float(row.exchange_rate or DEFAULT_USD_TO_INR), 2)


def row_credit_inr(row):
    value = row.credit_inr
    if value is not None and value != 0:
        return float(value)
    return round(row_credit_usd(row) * float(row.exchange_rate or DEFAULT_USD_TO_INR), 2)


def cost_usd(row):
    return float(row.total_cost_usd if row.total_cost_usd is not None and row.total_cost_usd != 0 else (row.total_cost or 0))


def cost_inr(row):
    value = row.total_cost_inr
    if value is not None and value != 0:
        return float(value)
    return round(cost_usd(row) * float(row.exchange_rate or DEFAULT_USD_TO_INR), 2)


def client_out(db: Session, client: Client):
    user = db.query(User).filter(User.role == "customer", User.client_id == client.id).order_by(User.id.asc()).first()
    totals = client_financial_totals(db, client.id)
    return {
        "id": client.id,
        "name": client.name,
        "status": client.status,
        "notes": client.notes,
        "username": user.username if user else None,
        **totals,
    }


def billing_query(db: Session, user: User, client_id=None, date_from=None, date_to=None, charge_type=None):
    query = db.query(BillingCharge)
    client_scope = scoped_client_id(client_id, user)
    if client_scope:
        query = query.filter(BillingCharge.client_id == client_scope)
    if date_from:
        query = query.filter(BillingCharge.billing_date >= date_from)
    if date_to:
        query = query.filter(BillingCharge.billing_date <= date_to)
    if charge_type:
        query = query.filter(BillingCharge.charge_type == charge_type)
    return query


def cdr_query(db: Session, user: User, client_id=None, date_from=None, date_to=None, search=None, disposition=None):
    query = db.query(CDR)
    client_scope = scoped_client_id(client_id, user)
    if client_scope:
        query = query.filter(CDR.client_id == client_scope)
    if date_from:
        query = query.filter(CDR.call_date >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        query = query.filter(CDR.call_date <= datetime.combine(date_to, datetime.max.time()))
    if search:
        like = f"%{search}%"
        query = query.filter((CDR.caller_id.ilike(like)) | (CDR.destination.ilike(like)))
    if disposition:
        query = query.filter(CDR.disposition == disposition)
    return query


def billing_summary(rows):
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    by_type = Counter()
    totals_by_type = {}
    total = 0
    today_total = 0
    week_total = 0
    month_total = 0
    day_totals = {}
    for row in rows:
        amount = float(row.amount or 0)
        total += amount
        by_type[row.charge_type] += 1
        totals_by_type[row.charge_type] = totals_by_type.get(row.charge_type, 0) + amount
        day_totals[row.billing_date.isoformat()] = day_totals.get(row.billing_date.isoformat(), 0) + amount
        if row.billing_date == today:
            today_total += amount
        if row.billing_date >= week_start:
            week_total += amount
        if row.billing_date >= month_start:
            month_total += amount
    return {
        "today_usage": round(today_total, 2),
        "weekly_total": round(week_total, 2),
        "monthly_total": round(month_total, 2),
        "outstanding": round(total, 2),
        "did_charges": round(totals_by_type.get("DID Charges", 0), 2),
        "data_charges": round(totals_by_type.get("Data Charges", 0), 2),
        "other_charges": round(totals_by_type.get("Other Charges", 0), 2),
        "charge_type_breakdown": {key: round(value, 2) for key, value in totals_by_type.items()},
        "day_wise": [{"billing_date": key, "amount": round(value, 2)} for key, value in sorted(day_totals.items(), reverse=True)],
    }


def ledger_query(db: Session, user: User, client_id=None, date_from=None, date_to=None, category=None, entry_type=None, search=None, created_by=None):
    query = db.query(ClientLedger)
    client_scope = scoped_client_id(client_id, user)
    if client_scope:
        query = query.filter(ClientLedger.client_id == client_scope)
    if date_from:
        query = query.filter(ClientLedger.entry_date >= date_from)
    if date_to:
        query = query.filter(ClientLedger.entry_date <= date_to)
    if category:
        query = query.filter(ClientLedger.category == category)
    if entry_type:
        query = query.filter(ClientLedger.entry_type == entry_type)
    if search:
        query = query.filter(ClientLedger.description.ilike(f"%{search}%"))
    if created_by:
        query = query.filter(ClientLedger.created_by.ilike(f"%{created_by}%"))
    return query


def ledger_payload_values(db: Session, payload: ClientLedgerCreate, user: User | None = None):
    if payload.entry_type not in {"Debit", "Credit"}:
        raise HTTPException(status_code=400, detail="entry_type must be Debit or Credit")
    if payload.category not in LEDGER_CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid ledger category")
    if not db.get(Client, payload.client_id):
        raise HTTPException(status_code=400, detail="Client does not exist")
    rate = float(payload.exchange_rate or get_billing_setting(db).usd_to_inr_rate or DEFAULT_USD_TO_INR)
    if payload.amount_usd is not None:
        amount = float(payload.amount_usd)
    elif payload.amount_inr is not None and rate:
        amount = float(payload.amount_inr) / rate
    else:
        amount = float((payload.debit_amount or 0) if payload.entry_type == "Debit" else (payload.credit_amount or 0))
    debit = amount if payload.entry_type == "Debit" else 0
    credit = amount if payload.entry_type == "Credit" else 0
    amount_inr = float(payload.amount_inr) if payload.amount_inr is not None else amount * rate
    data = payload.model_dump()
    data.update({
        "amount_usd": round(amount, 2),
        "exchange_rate": rate,
        "amount_inr": round(amount_inr, 2),
        "debit_amount": round(debit, 2),
        "credit_amount": round(credit, 2),
        "debit_usd": round(debit, 2),
        "credit_usd": round(credit, 2),
        "debit_inr": round(amount_inr if payload.entry_type == "Debit" else 0, 2),
        "credit_inr": round(amount_inr if payload.entry_type == "Credit" else 0, 2),
    })
    if user is not None:
        data["created_by"] = user.username
    return data


def recalc_client_ledger(db: Session, client_id: int):
    balance_usd = 0
    balance_inr = 0
    rows = db.query(ClientLedger).filter(ClientLedger.client_id == client_id).order_by(ClientLedger.entry_date.asc(), ClientLedger.id.asc()).all()
    for row in rows:
        rate = float(row.exchange_rate or DEFAULT_USD_TO_INR)
        debit_usd = float(row.debit_usd if row.debit_usd is not None else (row.debit_amount or 0))
        credit_usd = float(row.credit_usd if row.credit_usd is not None else (row.credit_amount or 0))
        if row.entry_type == "Debit" and not debit_usd:
            debit_usd = float(row.amount_usd or 0)
        if row.entry_type == "Credit" and not credit_usd:
            credit_usd = float(row.amount_usd or 0)
        amount_usd = debit_usd or credit_usd or float(row.amount_usd or 0)
        existing_debit_inr = float(row.debit_inr or 0)
        existing_credit_inr = float(row.credit_inr or 0)
        existing_amount_inr = float(row.amount_inr or 0)
        debit_inr = existing_debit_inr if existing_debit_inr else debit_usd * rate
        credit_inr = existing_credit_inr if existing_credit_inr else credit_usd * rate
        amount_inr = existing_amount_inr if existing_amount_inr else debit_inr or credit_inr or amount_usd * rate
        row.exchange_rate = rate
        row.amount_usd = round(amount_usd, 2)
        row.amount_inr = round(amount_inr, 2)
        row.debit_usd = round(debit_usd, 2)
        row.credit_usd = round(credit_usd, 2)
        row.debit_inr = round(debit_inr, 2)
        row.credit_inr = round(credit_inr, 2)
        row.debit_amount = row.debit_usd
        row.credit_amount = row.credit_usd
        balance_usd += debit_usd - credit_usd
        balance_inr += row.debit_inr - row.credit_inr
        row.balance_usd = round(balance_usd, 2)
        row.balance_inr = round(balance_inr, 2)
        row.balance_after_entry = row.balance_usd
    db.flush()


def ledger_summary(rows):
    today = date.today()
    month_start = today.replace(day=1)
    today_charges = sum(row.debit_usd or row.debit_amount or 0 for row in rows if row.entry_date == today)
    today_payments = sum(row.credit_usd or row.credit_amount or 0 for row in rows if row.entry_date == today)
    monthly_charges = sum(row.debit_usd or row.debit_amount or 0 for row in rows if row.entry_date >= month_start)
    monthly_payments = sum(row.credit_usd or row.credit_amount or 0 for row in rows if row.entry_date >= month_start)
    outstanding = sum((row.debit_usd or row.debit_amount or 0) - (row.credit_usd or row.credit_amount or 0) for row in rows)
    today_charges_inr = sum(row.debit_inr or 0 for row in rows if row.entry_date == today)
    today_payments_inr = sum(row.credit_inr or 0 for row in rows if row.entry_date == today)
    monthly_charges_inr = sum(row.debit_inr or 0 for row in rows if row.entry_date >= month_start)
    monthly_payments_inr = sum(row.credit_inr or 0 for row in rows if row.entry_date >= month_start)
    outstanding_inr = sum((row.debit_inr or 0) - (row.credit_inr or 0) for row in rows)
    by_client = {}
    by_client_inr = {}
    for row in rows:
        name = row.client_name or "Unassigned"
        by_client[name] = by_client.get(name, 0) + (row.debit_usd or row.debit_amount or 0) - (row.credit_usd or row.credit_amount or 0)
        by_client_inr[name] = by_client_inr.get(name, 0) + (row.debit_inr or 0) - (row.credit_inr or 0)
    return {
        "today_total_charges": round(today_charges, 2),
        "today_payments": round(today_payments, 2),
        "monthly_charges": round(monthly_charges, 2),
        "monthly_payments": round(monthly_payments, 2),
        "total_outstanding": round(outstanding, 2),
        "today_total_charges_inr": round(today_charges_inr, 2),
        "today_payments_inr": round(today_payments_inr, 2),
        "monthly_charges_inr": round(monthly_charges_inr, 2),
        "monthly_payments_inr": round(monthly_payments_inr, 2),
        "total_outstanding_inr": round(outstanding_inr, 2),
        "client_outstanding": [{"client": key, "outstanding": round(value, 2), "outstanding_inr": round(by_client_inr.get(key, 0), 2)} for key, value in sorted(by_client.items())],
    }


def cdr_summary(rows):
    total_calls = len(rows)
    answered = len([row for row in rows if row.disposition == "ANSWERED"])
    total_seconds = sum(row.duration or 0 for row in rows)
    total_cost = sum(row.cost or 0 for row in rows)
    return {
        "total_calls": total_calls,
        "answered_calls": answered,
        "total_minutes": round(total_seconds / 60, 2),
        "total_cost": round(total_cost, 4),
    }


def operational_dashboard(db: Session):
    clients = db.query(Client).all()
    clusters = db.query(DialerCluster).order_by(DialerCluster.cluster_no.asc()).all()
    rdps = get_rdp_portals(db)
    gateways = db.query(RoutingGateway).all()
    ledger_rows = db.query(ClientLedger).all()
    outstanding = {}
    for row in ledger_rows:
        current = outstanding.get(row.client_id, {"usd": 0, "inr": 0})
        current["usd"] += row_debit_usd(row) - row_credit_usd(row)
        current["inr"] += row_debit_inr(row) - row_credit_inr(row)
        outstanding[row.client_id] = current
    rdp_rows = []
    for rdp in rdps:
        usage = rdp_out(rdp, clusters, gateways)
        rdp_rows.append({"rdp_name": rdp.portal_type, "ip": rdp.server_ip, "status": rdp.status, "assigned_cluster": usage["assigned_cluster"], "client": usage["assigned_to"], "used_in_routing": usage["used_in_routing"], "usage_status": usage["usage_status"]})
    client_rows = []
    for client in clients:
        client_clusters = [cluster for cluster in clusters if cluster.client_id == client.id]
        used_rdp = sorted({cluster.live_rdp_name for cluster in client_clusters if normalize(cluster.live_rdp_name)})
        totals = outstanding.get(client.id, {"usd": 0, "inr": 0})
        client_rows.append({"client": client.name, "assigned_clusters": len(client_clusters), "used_rdp": ", ".join(used_rdp), "outstanding": round(totals["usd"], 2), "outstanding_inr": round(totals["inr"], 2)})
    duplicate_names = active_rdp_duplicate_names(clusters)
    alerts = []
    for cluster in clusters:
        for field in ["inbound_ip", "assigned_rdp_ip"]:
            value = cluster.live_rdp_ip if field == "assigned_rdp_ip" else getattr(cluster, field)
            if is_missing(value):
                alerts.append({"type": "missing", "message": f"Cluster {cluster.cluster_no} missing {field}"})
    for gateway in gateways:
        sync_gateway_live_fields(gateway)
        for field in ["live_gateway_ip", "live_media1_ip", "live_media2_ip", "carrier_ip"]:
            if is_missing(getattr(gateway, field)):
                alerts.append({"type": "missing", "message": f"{gateway.live_gateway_name} missing {field.replace('live_', '')}"})
    for name in duplicate_names:
        alerts.append({"type": "duplicate", "message": f"Duplicate active RDP across clients: {name}"})
    audit = system_audit(db)
    for item in audit.get("duplicate_rdp_in_routing", []):
        alerts.append({"type": "duplicate", "message": f"Duplicate RDP in routing: {item['rdp']} used by {', '.join(item['gateways'])}"})
    for item in audit.get("rdp_missing_links", []):
        alerts.append({"type": "missing", "message": f"Missing RDP link in {item['type']} {item['id']} ({item['field']})"})
    for gateway in gateways:
        for warning in routing_validation_alerts(gateway):
            alerts.append({"type": "duplicate", "message": warning})
    used_rdp = {cluster.live_rdp_name for cluster in clusters if cluster.status == "Active" and normalize(cluster.live_rdp_name)}
    return {
        "summary": {
            "rdp_total": len(rdps),
            "rdp_used": len(used_rdp),
            "rdp_free": len([rdp for rdp in rdps if rdp.portal_type not in used_rdp]),
            "routing_gateways": len(gateways),
            "clusters": len(clusters),
            "clients": len(clients),
            "alerts": len(alerts),
        },
        "rdp_brief": rdp_rows,
        "routing_brief": [routing_gateway_out(row) for row in gateways],
        "cluster_brief": [{"cluster_no": row.cluster_no, "cluster_name": row.cluster_name, "inbound_ip": row.inbound_ip, "client": row.client_name, "assigned_rdp": row.live_rdp_name, "assigned_rdp_ip": row.live_rdp_ip, "status": row.status} for row in clusters],
        "client_brief": client_rows,
        "alerts": alerts,
    }


def parse_ids(value: str | None):
    if not value:
        return []
    return [int(item) for item in value.split(",") if item.strip().isdigit()]


def report_scope(db: Session, user: User, client_ids: str | None = None, date_from: date | None = None, date_to: date | None = None):
    ids = parse_ids(client_ids)
    ids = scoped_client_ids(db, user, ids)
    return ids, date_from, date_to


def scoped_ledger_rows(db: Session, user: User, client_ids=None, date_from=None, date_to=None):
    ids, date_from, date_to = report_scope(db, user, client_ids, date_from, date_to)
    query = db.query(ClientLedger)
    if ids:
        query = query.filter(ClientLedger.client_id.in_(ids))
    if date_from:
        query = query.filter(ClientLedger.entry_date >= date_from)
    if date_to:
        query = query.filter(ClientLedger.entry_date <= date_to)
    return query.order_by(ClientLedger.entry_date.asc(), ClientLedger.id.asc()).all()


def data_cost_rows(db: Session, user: User, client_ids=None, date_from=None, date_to=None):
    ids, date_from, date_to = report_scope(db, user, client_ids, date_from, date_to)
    query = db.query(DataCost)
    if ids:
        query = query.filter(DataCost.client_id.in_(ids))
    if date_from:
        query = query.filter(DataCost.entry_date >= date_from)
    if date_to:
        query = query.filter(DataCost.entry_date <= date_to)
    return query.order_by(DataCost.entry_date.desc(), DataCost.id.desc()).all()


def normalize_data_cost_currency(db: Session):
    changed = False
    for row in db.query(DataCost).all():
        rate_usd = row.rate_usd or row.rate or 0
        total_usd = row.total_cost_usd or row.total_cost or round((row.quantity or 0) * rate_usd, 2)
        exchange = row.exchange_rate or DEFAULT_USD_TO_INR
        row.rate = rate_usd
        row.rate_usd = rate_usd
        row.total_cost = total_usd
        row.total_cost_usd = total_usd
        row.exchange_rate = exchange
        row.total_cost_inr = round(total_usd * exchange, 2)
        changed = True
    if changed:
        db.commit()


def client_financials(db: Session, user: User, client_ids=None, date_from=None, date_to=None):
    rows = scoped_ledger_rows(db, user, client_ids, date_from, date_to)
    data_costs = data_cost_rows(db, user, client_ids, date_from, date_to)
    by_client = {}
    for row in rows:
        item = by_client.setdefault(row.client_id, {"client": row.client_name, "revenue": 0, "credit": 0, "revenue_inr": 0, "credit_inr": 0, "did_cost": 0, "did_cost_inr": 0, "server_cost": 0, "server_cost_inr": 0, "other_cost": 0, "other_cost_inr": 0})
        debit = row_debit_usd(row)
        credit = row_credit_usd(row)
        debit_inr = row_debit_inr(row)
        item["revenue"] += debit
        item["credit"] += credit
        item["revenue_inr"] += debit_inr
        item["credit_inr"] += row_credit_inr(row)
        if row.category == "DID Charges":
            item["did_cost"] += debit
            item["did_cost_inr"] += debit_inr
        elif row.category in {"Server Charges", "Port Charges", "Setup Charges"}:
            item["server_cost"] += debit
            item["server_cost_inr"] += debit_inr
        elif row.category in {"Other Charges", "Adjustment"}:
            item["other_cost"] += debit
            item["other_cost_inr"] += debit_inr
    for cost in data_costs:
        item = by_client.setdefault(cost.client_id, {"client": cost.client_name, "revenue": 0, "credit": 0, "revenue_inr": 0, "credit_inr": 0, "did_cost": 0, "did_cost_inr": 0, "server_cost": 0, "server_cost_inr": 0, "other_cost": 0, "other_cost_inr": 0})
        item["data_cost"] = item.get("data_cost", 0) + cost_usd(cost)
        item["data_cost_inr"] = item.get("data_cost_inr", 0) + cost_inr(cost)
    for item in by_client.values():
        item.setdefault("data_cost", 0)
        item.setdefault("data_cost_inr", 0)
        total_cost = item["data_cost"] + item["did_cost"] + item["server_cost"] + item["other_cost"]
        total_cost_inr = item["data_cost_inr"] + item["did_cost_inr"] + item["server_cost_inr"] + item["other_cost_inr"]
        item["profit"] = round(item["revenue"] - total_cost, 2)
        item["profit_inr"] = round(item["revenue_inr"] - total_cost_inr, 2)
        item["margin"] = round((item["profit"] / item["revenue"] * 100), 2) if item["revenue"] else 0
        item["outstanding"] = round(item["revenue"] - item["credit"], 2)
        item["outstanding_inr"] = round(item["revenue_inr"] - item["credit_inr"], 2)
    return by_client


def portal_type_query(db: Session, prefix: str):
    return db.query(VOSPortal).filter(VOSPortal.portal_type.ilike(f"{prefix}%"))


def is_rtng_portal(portal: VOSPortal | None):
    return bool(portal and normalize(portal.portal_type) and portal.portal_type.upper().startswith("RTNG"))


def is_media_portal(portal: VOSPortal | None):
    if not portal or not normalize(portal.portal_type):
        return False
    portal_type = portal.portal_type.upper()
    return portal_type.startswith("RDP") or portal_type.startswith("DID") or "DID" in portal_type


def get_rdp_portals(db: Session):
    return portal_type_query(db, "RDP").order_by(VOSPortal.portal_type.asc()).all()


def get_rtng_portals(db: Session):
    return portal_type_query(db, "RTNG").order_by(VOSPortal.portal_type.asc()).all()


def get_media_portals(db: Session):
    return db.query(VOSPortal).filter(or_(VOSPortal.portal_type.ilike("RDP%"), VOSPortal.portal_type.ilike("DID%"), VOSPortal.portal_type.ilike("%DID%"))).order_by(VOSPortal.portal_type.asc()).all()


def get_portal_exact(db: Session, portal_type: str | None):
    portal_type = normalize(portal_type)
    if not portal_type:
        return None
    return db.query(VOSPortal).filter(VOSPortal.portal_type == portal_type).first()


def get_portal_by_type(db: Session, portal_type: str, prefix: str):
    portal_type = normalize(portal_type)
    if not portal_type:
        return None
    return portal_type_query(db, prefix).filter(VOSPortal.portal_type == portal_type).first()


def get_portal_by_id(db: Session, portal_id: int | None, prefix: str):
    if portal_id is None:
        return None
    portal = db.get(VOSPortal, portal_id)
    if not portal or not normalize(portal.portal_type) or not portal.portal_type.upper().startswith(prefix):
        return None
    return portal


def cluster_rdp_portal(db: Session, cluster: DialerCluster):
    return get_portal_by_id(db, cluster.rdp_vos_id, "RDP") or get_portal_by_type(db, cluster.assigned_rdp, "RDP")


def gateway_id(gateway: RoutingGateway):
    return gateway.routing_gateway_id or gateway.rtng_vos_id


def media_id(gateway: RoutingGateway, slot: int):
    return (gateway.media_1_portal_id or gateway.media1_vos_id) if slot == 1 else (gateway.media_2_portal_id or gateway.media2_vos_id)


def get_gateway_portal(db: Session, gateway: RoutingGateway):
    portal_id = gateway_id(gateway)
    portal = db.get(VOSPortal, portal_id) if portal_id else None
    if is_rtng_portal(portal):
        return portal
    legacy = get_portal_exact(db, gateway.gateway_name)
    return legacy if is_rtng_portal(legacy) else None


def get_media_portal(db: Session, gateway: RoutingGateway, slot: int):
    portal_id = media_id(gateway, slot)
    portal = db.get(VOSPortal, portal_id) if portal_id else None
    if is_media_portal(portal):
        return portal
    legacy_name = gateway.media1_name if slot == 1 else gateway.media2_name
    legacy = get_portal_exact(db, legacy_name)
    return legacy if is_media_portal(legacy) else None


def gateway_portals(db: Session, gateway: RoutingGateway):
    return get_gateway_portal(db, gateway), get_media_portal(db, gateway, 1), get_media_portal(db, gateway, 2)


def sync_cluster_live_rdp(db: Session, cluster: DialerCluster):
    rdp = cluster_rdp_portal(db, cluster)
    if rdp:
        cluster.rdp_vos_id = rdp.id
        cluster.assigned_rdp = rdp.portal_type
        cluster.assigned_rdp_ip = rdp.server_ip
    elif not normalize(cluster.assigned_rdp):
        cluster.rdp_vos_id = None
        cluster.assigned_rdp_ip = None
    return rdp


def sync_gateway_live_fields(gateway: RoutingGateway):
    gateway_portal = gateway.routing_gateway_portal or gateway.rtng_vos
    media1_portal = gateway.media_1_portal or gateway.media1_vos
    media2_portal = gateway.media_2_portal or gateway.media2_vos
    if is_rtng_portal(gateway_portal):
        gateway.routing_gateway_id = gateway_portal.id
        gateway.rtng_vos_id = gateway_portal.id
        gateway.gateway_name = gateway_portal.portal_type
        gateway.gateway_ip = gateway_portal.server_ip
    if is_media_portal(media1_portal):
        gateway.media_1_portal_id = media1_portal.id
        gateway.media1_vos_id = media1_portal.id
        gateway.media1_name = media1_portal.portal_type
        gateway.media1_ip = media1_portal.server_ip
    elif not normalize(gateway.media1_name):
        gateway.media1_ip = None
    if is_media_portal(media2_portal):
        gateway.media_2_portal_id = media2_portal.id
        gateway.media2_vos_id = media2_portal.id
        gateway.media2_name = media2_portal.portal_type
        gateway.media2_ip = media2_portal.server_ip
    elif not normalize(gateway.media2_name):
        gateway.media2_ip = None
    return gateway


def rdp_out(portal: VOSPortal, clusters=None, gateways=None):
    clusters = clusters or []
    gateways = gateways or []
    active_clusters = [
        cluster for cluster in clusters
        if cluster.status != "Inactive" and (cluster.rdp_vos_id == portal.id or cluster.live_rdp_name == portal.portal_type)
    ]
    active_routing = []
    for gateway in gateways:
        if gateway.status == "Inactive":
            continue
        sync_gateway_live_fields(gateway)
        media_ids = {gateway.media1_vos_id, gateway.media2_vos_id}
        media_names = {normalize(gateway.live_media1_name), normalize(gateway.live_media2_name)}
        if portal.id in media_ids or normalize(portal.portal_type) in media_names:
            active_routing.append(gateway)
    cluster_names = sorted({cluster.cluster_name for cluster in active_clusters if normalize(cluster.cluster_name)})
    cluster_clients = sorted({cluster.client_name for cluster in active_clusters if normalize(cluster.client_name)})
    routing_names = sorted({gateway.live_gateway_name for gateway in active_routing if normalize(gateway.live_gateway_name)})
    routing_clients = sorted({gateway.client.name for gateway in active_routing if getattr(gateway, "client", None)})
    assigned_to = ", ".join(cluster_clients or routing_clients) or None
    if len({cluster.id for cluster in active_clusters}) > 1 or len({gateway.id for gateway in active_routing}) > 1:
        usage_status = "Conflict"
    elif active_routing:
        usage_status = "Used in Routing"
    elif active_clusters:
        usage_status = "Assigned to Cluster"
    else:
        usage_status = "Free"
    return {
        "id": portal.id,
        "name": portal.portal_type,
        "ip": portal.server_ip,
        "status": portal.status,
        "assigned_to": assigned_to,
        "assigned_cluster": ", ".join(cluster_names) or None,
        "used_in_routing": ", ".join(routing_names) or None,
        "usage_status": usage_status,
        "notes": portal.notes or (f"Used in Routing: {', '.join(routing_names)}" if routing_names else None),
    }


def validate_vos_portal(db: Session, payload, record_id=None):
    portal_type = normalize(payload.portal_type)
    server_ip = normalize(payload.server_ip)
    if not portal_type:
        raise HTTPException(status_code=400, detail="portal_type is required")
    existing_type = db.query(VOSPortal).filter(VOSPortal.portal_type == portal_type)
    if record_id is not None:
        existing_type = existing_type.filter(VOSPortal.id != record_id)
    if existing_type.first():
        raise HTTPException(status_code=409, detail="portal_type must be unique in VOS Portal Master")

    if portal_type.upper().startswith("RDP") and server_ip:
        existing_ip = portal_type_query(db, "RDP").filter(VOSPortal.server_ip == server_ip)
        if record_id is not None:
            existing_ip = existing_ip.filter(VOSPortal.id != record_id)
        if existing_ip.first():
            raise HTTPException(status_code=409, detail="RDP server_ip must be unique in VOS Portal Master")


def sync_vos_references(db: Session, old_type: str, portal: VOSPortal):
    old_type = normalize(old_type)
    new_type = normalize(portal.portal_type)
    if not new_type:
        return
    new_upper = new_type.upper()
    old_upper = old_type.upper() if old_type else ""
    is_new_media = new_upper.startswith("RDP") or new_upper.startswith("DID") or "DID" in new_upper
    was_media = old_upper.startswith("RDP") or old_upper.startswith("DID") or "DID" in old_upper

    if new_upper.startswith("RDP") or old_upper.startswith("RDP"):
        if old_type and old_type != new_type:
            db.query(DialerCluster).filter(DialerCluster.assigned_rdp == old_type).update({"assigned_rdp": new_type})
        db.query(DialerCluster).filter(DialerCluster.rdp_vos_id == portal.id).update({"assigned_rdp": new_type, "assigned_rdp_ip": portal.server_ip})
        db.query(DialerCluster).filter(DialerCluster.assigned_rdp == new_type).update({"assigned_rdp_ip": portal.server_ip})

    if is_new_media or was_media:
        if old_type and old_type != new_type:
            db.query(RoutingGateway).filter(RoutingGateway.media1_name == old_type).update({"media1_name": new_type})
            db.query(RoutingGateway).filter(RoutingGateway.media2_name == old_type).update({"media2_name": new_type})
        db.query(RoutingGateway).filter(RoutingGateway.media1_vos_id == portal.id).update({"media1_name": new_type, "media1_ip": portal.server_ip})
        db.query(RoutingGateway).filter(RoutingGateway.media_1_portal_id == portal.id).update({"media1_name": new_type, "media1_ip": portal.server_ip})
        db.query(RoutingGateway).filter(RoutingGateway.media2_vos_id == portal.id).update({"media2_name": new_type, "media2_ip": portal.server_ip})
        db.query(RoutingGateway).filter(RoutingGateway.media_2_portal_id == portal.id).update({"media2_name": new_type, "media2_ip": portal.server_ip})
        db.query(RoutingGateway).filter(RoutingGateway.media1_name == new_type).update({"media1_ip": portal.server_ip})
        db.query(RoutingGateway).filter(RoutingGateway.media2_name == new_type).update({"media2_ip": portal.server_ip})

    if new_upper.startswith("RTNG") or old_upper.startswith("RTNG"):
        if old_type and old_type != new_type:
            db.query(RoutingGateway).filter(RoutingGateway.gateway_name == old_type).update({"gateway_name": new_type})
        db.query(RoutingGateway).filter(RoutingGateway.rtng_vos_id == portal.id).update({"gateway_name": new_type, "gateway_ip": portal.server_ip})
        db.query(RoutingGateway).filter(RoutingGateway.routing_gateway_id == portal.id).update({"gateway_name": new_type, "gateway_ip": portal.server_ip})
        db.query(RoutingGateway).filter(RoutingGateway.gateway_name == new_type).update({"gateway_ip": portal.server_ip})


def apply_cluster_assignment_rules(db: Session, payload, cluster_id=None):
    rdp = get_portal_by_id(db, getattr(payload, "rdp_vos_id", None), "RDP")
    assigned_rdp = normalize(payload.assigned_rdp)
    if not rdp and assigned_rdp:
        rdp = get_portal_by_type(db, assigned_rdp, "RDP")

    if not rdp and not assigned_rdp:
        payload.rdp_vos_id = None
        payload.assigned_rdp = None
        payload.assigned_rdp_ip = None
        return payload

    if not rdp:
        raise HTTPException(status_code=400, detail="Assigned RDP must exist in VOS Portal Master")
    active_assignment = db.query(DialerCluster).filter(
        DialerCluster.rdp_vos_id == rdp.id,
        DialerCluster.status == "Active",
    )
    legacy_active = db.query(DialerCluster).filter(DialerCluster.assigned_rdp == rdp.portal_type, DialerCluster.status == "Active")
    if cluster_id is not None:
        active_assignment = active_assignment.filter(DialerCluster.id != cluster_id)
        legacy_active = legacy_active.filter(DialerCluster.id != cluster_id)
    for assigned_cluster in active_assignment.all() + legacy_active.all():
        if payload.status == "Active" and assigned_cluster.client_id != payload.client_id:
            raise HTTPException(status_code=409, detail="RDP is already assigned to an active cluster for another client")
    payload.rdp_vos_id = rdp.id
    payload.assigned_rdp = rdp.portal_type
    payload.assigned_rdp_ip = rdp.server_ip
    return payload


def apply_gateway_rules(db: Session, payload, record_id=None):
    gateway_name = normalize(getattr(payload, "gateway_name", None))
    if gateway_name and gateway_name.upper().startswith("RDP"):
        raise HTTPException(status_code=400, detail="Invalid mapping: Media node selected as gateway")
    gateway = get_portal_by_id(db, getattr(payload, "routing_gateway_id", None), "RTNG") or get_portal_by_id(db, getattr(payload, "rtng_vos_id", None), "RTNG") or get_portal_by_type(db, gateway_name, "RTNG")
    if not gateway:
        raise HTTPException(status_code=400, detail="Routing gateway must exist in VOS Portal Master with RTNG portal_type")
    payload.routing_gateway_id = gateway.id
    payload.rtng_vos_id = gateway.id
    payload.gateway_name = gateway.portal_type
    payload.gateway_ip = gateway.server_ip

    for slot, legacy_name_field, alias_name_field, ip_field, legacy_id_field, alias_id_field in [
        (1, "media1_name", "media_1_name", "media1_ip", "media1_vos_id", "media_1_portal_id"),
        (2, "media2_name", "media_2_name", "media2_ip", "media2_vos_id", "media_2_portal_id"),
    ]:
        media_name = normalize(getattr(payload, alias_name_field, None)) or normalize(getattr(payload, legacy_name_field, None))
        portal_id = getattr(payload, alias_id_field, None) or getattr(payload, legacy_id_field, None)
        media = db.get(VOSPortal, portal_id) if portal_id else None
        if media and is_rtng_portal(media):
            raise HTTPException(status_code=400, detail=f"Invalid mapping: Routing gateway selected as Media {slot}")
        if not media and media_name:
            if media_name.upper().startswith("RTNG"):
                raise HTTPException(status_code=400, detail=f"Invalid mapping: Routing gateway selected as Media {slot}")
            media = get_portal_exact(db, media_name)
        if not media and not media_name:
            setattr(payload, legacy_id_field, None)
            setattr(payload, alias_id_field, None)
            setattr(payload, legacy_name_field, None)
            setattr(payload, alias_name_field, None)
            setattr(payload, ip_field, None)
            setattr(payload, f"media_{slot}_ip", None)
            continue
        if not is_media_portal(media):
            raise HTTPException(status_code=400, detail=f"Media {slot} must be RDP or DID from VOS Portal Master")
        setattr(payload, legacy_id_field, media.id)
        setattr(payload, alias_id_field, media.id)
        setattr(payload, legacy_name_field, media.portal_type)
        setattr(payload, alias_name_field, media.portal_type)
        setattr(payload, ip_field, media.server_ip)
        setattr(payload, f"media_{slot}_ip", media.server_ip)
    payload.vendor_name = normalize(getattr(payload, "vendor", None)) or normalize(payload.vendor_name)
    payload.vendor = payload.vendor_name
    if payload.status == "Active":
        selected_ids = {value for value in [payload.media_1_portal_id, payload.media1_vos_id, payload.media_2_portal_id, payload.media2_vos_id] if value}
        for media_portal_id in selected_ids:
            existing = db.query(RoutingGateway).filter(
                RoutingGateway.status == "Active",
                or_(
                    RoutingGateway.media1_vos_id == media_portal_id,
                    RoutingGateway.media2_vos_id == media_portal_id,
                    RoutingGateway.media_1_portal_id == media_portal_id,
                    RoutingGateway.media_2_portal_id == media_portal_id,
                ),
            )
            if record_id is not None:
                existing = existing.filter(RoutingGateway.id != record_id)
            if existing.first():
                raise HTTPException(status_code=409, detail="RDP already assigned to another routing gateway")
    return payload


def active_rdp_duplicate_names(clusters):
    clients_by_rdp = {}
    for cluster in clusters:
        key = cluster.rdp_vos_id or normalize(cluster.assigned_rdp)
        if cluster.status == "Active" and key:
            clients_by_rdp.setdefault(key, {"clients": set(), "name": cluster.live_rdp_name}).get("clients").add(cluster.client_id)
    return {item["name"] for item in clients_by_rdp.values() if len(item["clients"]) > 1}


def routing_validation_alerts(row: RoutingGateway):
    alerts = []
    gateway_name = normalize(row.live_gateway_name)
    media1_name = normalize(row.live_media1_name)
    media2_name = normalize(row.live_media2_name)
    if gateway_name and gateway_name.upper().startswith("RDP"):
        alerts.append("Invalid mapping: Media node selected as gateway")
    if media1_name and media1_name.upper().startswith("RTNG"):
        alerts.append("Invalid mapping: Routing gateway selected as Media 1")
    if media2_name and media2_name.upper().startswith("RTNG"):
        alerts.append("Invalid mapping: Routing gateway selected as Media 2")
    return alerts


def routing_gateway_out(row: RoutingGateway):
    sync_gateway_live_fields(row)
    gateway_id_value = row.routing_gateway_id or row.rtng_vos_id
    media1_id_value = row.media_1_portal_id or row.media1_vos_id
    media2_id_value = row.media_2_portal_id or row.media2_vos_id
    return {
        "id": row.id,
        "gateway_name": row.live_gateway_name,
        "gateway_ip": row.live_gateway_ip,
        "routing_gateway_id": gateway_id_value,
        "rtng_vos_id": gateway_id_value,
        "client_id": row.client_id,
        "media_1_portal_id": media1_id_value,
        "media1_vos_id": media1_id_value,
        "media_1_name": row.live_media1_name,
        "media1_name": row.live_media1_name,
        "media_1_ip": row.live_media1_ip,
        "media1_ip": row.live_media1_ip,
        "media_2_portal_id": media2_id_value,
        "media2_vos_id": media2_id_value,
        "media_2_name": row.live_media2_name,
        "media2_name": row.live_media2_name,
        "media_2_ip": row.live_media2_ip,
        "media2_ip": row.live_media2_ip,
        "carrier_ip": row.carrier_ip,
        "ports": row.ports,
        "vendor": row.vendor_name,
        "vendor_name": row.vendor_name,
        "status": row.status,
        "notes": row.notes,
        "validation_alerts": routing_validation_alerts(row),
    }


def routing_gateway_db_payload(payload):
    db_fields = {column.name for column in RoutingGateway.__table__.columns}
    return {key: value for key, value in payload.model_dump(exclude={"validation_alerts"}).items() if key in db_fields}


def cluster_assignment_out(cluster: DialerCluster):
    return {
        "cluster_id": cluster.id,
        "cluster_no": cluster.cluster_no,
        "cluster": cluster.cluster_name,
        "cluster_name": cluster.cluster_name,
        "account_name": cluster.account_name,
        "inbound_ip": cluster.inbound_ip,
        "client_id": cluster.client_id,
        "client_name": cluster.client_name,
        "status": cluster.status,
    }


def rdp_cluster_assignment_out(cluster: DialerCluster, duplicate_names):
    duplicate = normalize(cluster.assigned_rdp) in duplicate_names
    rdp_name = cluster.live_rdp_name
    rdp_ip = cluster.live_rdp_ip
    duplicate = normalize(rdp_name) in duplicate_names
    return {
        "cluster_id": cluster.id,
        "cluster_no": cluster.cluster_no,
        "cluster": cluster.cluster_name,
        "cluster_name": cluster.cluster_name,
        "account_name": cluster.account_name,
        "client_id": cluster.client_id,
        "client_name": cluster.client_name,
        "rdp_vos_id": cluster.rdp_vos_id,
        "assigned_rdp": rdp_name,
        "assigned_rdp_ip": rdp_ip,
        "status": cluster.status,
        "duplicate_alert": duplicate,
        "duplicate_message": "Duplicate active RDP assignment" if duplicate else "",
    }


def routing_media_assignment_out(gateway_name, gateway_ip, mapping=None):
    client_names = []
    if mapping:
        sync_gateway_live_fields(mapping)
        media_names = {normalize(mapping.live_media1_name), normalize(mapping.live_media2_name)}
        media_names.discard(None)
        clients = {
            cluster.client_name
            for cluster in getattr(mapping, "_management_clusters", [])
            if normalize(cluster.live_rdp_name) in media_names and normalize(cluster.client_name)
        }
        client_names = sorted(clients)
    return {
        "id": mapping.id if mapping else None,
        "gateway_name": gateway_name,
        "gateway_ip": gateway_ip,
        "routing_gateway_id": (mapping.routing_gateway_id or mapping.rtng_vos_id) if mapping else None,
        "rtng_vos_id": (mapping.routing_gateway_id or mapping.rtng_vos_id) if mapping else None,
        "media_1_portal_id": (mapping.media_1_portal_id or mapping.media1_vos_id) if mapping else None,
        "media1_vos_id": (mapping.media_1_portal_id or mapping.media1_vos_id) if mapping else None,
        "media_1_name": mapping.live_media1_name if mapping else None,
        "media1_name": mapping.live_media1_name if mapping else None,
        "media_1_ip": mapping.live_media1_ip if mapping else None,
        "media1_ip": mapping.live_media1_ip if mapping else None,
        "media_2_portal_id": (mapping.media_2_portal_id or mapping.media2_vos_id) if mapping else None,
        "media2_vos_id": (mapping.media_2_portal_id or mapping.media2_vos_id) if mapping else None,
        "media_2_name": mapping.live_media2_name if mapping else None,
        "media2_name": mapping.live_media2_name if mapping else None,
        "media_2_ip": mapping.live_media2_ip if mapping else None,
        "media2_ip": mapping.live_media2_ip if mapping else None,
        "carrier_ip": mapping.carrier_ip if mapping else None,
        "ports": mapping.ports if mapping else None,
        "vendor": mapping.vendor_name if mapping else None,
        "vendor_name": mapping.vendor_name if mapping else None,
        "status": mapping.status if mapping else "Pending",
        "clients": ", ".join(client_names),
        "validation_alerts": routing_validation_alerts(mapping) if mapping else [],
    }


def management_summary(db: Session):
    clusters = db.query(DialerCluster).order_by(DialerCluster.cluster_no.asc()).all()
    clients = db.query(Client).all()
    rdps = get_rdp_portals(db)
    gateways = get_rtng_portals(db)
    gateway_mappings = db.query(RoutingGateway).all()
    active_assignments = {
        cluster.live_rdp_name
        for cluster in clusters
        if cluster.status == "Active" and normalize(cluster.live_rdp_name)
    }
    duplicate_names = active_rdp_duplicate_names(clusters)
    return {
        "total_clients": len(clients),
        "active_clients": len([client for client in clients if client.status == "Active"]),
        "total_clusters": len(clusters),
        "assigned_clusters": len([cluster for cluster in clusters if cluster.client_id is not None]),
        "free_rdp": len([rdp for rdp in rdps if rdp.portal_type not in active_assignments]),
        "used_rdp": len([rdp for rdp in rdps if rdp.portal_type in active_assignments]),
        "routing_gateways_configured": len([gateway for gateway in gateway_mappings if normalize(gateway.gateway_name)]),
        "duplicate_alerts": len(duplicate_names),
        "rdp_used_per_client": dict(
            Counter(cluster.client_name or "Unassigned" for cluster in clusters if cluster.status == "Active" and normalize(cluster.live_rdp_name))
        ),
        "clusters_per_client": dict(Counter(cluster.client_name or "Unassigned" for cluster in clusters)),
    }


def system_audit(db: Session):
    clusters = db.query(DialerCluster).order_by(DialerCluster.cluster_no.asc()).all()
    gateways = db.query(RoutingGateway).order_by(RoutingGateway.gateway_name.asc()).all()
    clients = {client.id: client for client in db.query(Client).all()}
    rdp_portals = {portal.id: portal for portal in get_rdp_portals(db)}
    media_portals = {portal.id: portal for portal in get_media_portals(db)}
    rtng_portals = {portal.id: portal for portal in get_rtng_portals(db)}
    duplicate_names = active_rdp_duplicate_names(clusters)
    audit = {
        "duplicate_rdp_in_routing": [],
        "rdp_assigned_multiple_clusters": [],
        "rdp_missing_links": [],
        "duplicate_rdp_assignments": [],
        "missing_cluster_references": [],
        "missing_client_references": [],
        "missing_rdp_references": [],
        "orphan_assignment_records": [],
        "missing_ip_values": [],
        "stale_copied_names": [],
    }

    for name in sorted(duplicate_names):
        affected = [cluster.cluster_name for cluster in clusters if cluster.status == "Active" and cluster.live_rdp_name == name]
        audit["duplicate_rdp_assignments"].append({"rdp": name, "clusters": affected})
        audit["rdp_assigned_multiple_clusters"].append({"rdp": name, "clusters": sorted(set(affected))})

    routing_usage = {}
    for gateway in gateways:
        if gateway.status != "Active":
            continue
        sync_gateway_live_fields(gateway)
        seen_in_gateway = set()
        for portal_id, portal_name in [(media_id(gateway, 1), gateway.live_media1_name), (media_id(gateway, 2), gateway.live_media2_name)]:
            key = portal_id or normalize(portal_name)
            if not key or key in seen_in_gateway:
                continue
            seen_in_gateway.add(key)
            if (normalize(portal_name) or "").upper().startswith("RTNG"):
                continue
            if key:
                routing_usage.setdefault(key, {"rdp": portal_name, "gateways": set()})["gateways"].add(gateway.live_gateway_name)
    for item in routing_usage.values():
        if len(item["gateways"]) > 1:
            audit["duplicate_rdp_in_routing"].append({"rdp": item["rdp"], "gateways": sorted(item["gateways"])})

    for cluster in clusters:
        if cluster.client_id and cluster.client_id not in clients:
            audit["missing_client_references"].append({"type": "DialerCluster", "id": cluster.id, "cluster": cluster.cluster_name, "client_id": cluster.client_id})
        rdp = cluster_rdp_portal(db, cluster)
        if cluster.rdp_vos_id and cluster.rdp_vos_id not in rdp_portals:
            audit["missing_rdp_references"].append({"type": "DialerCluster", "id": cluster.id, "cluster": cluster.cluster_name, "rdp_vos_id": cluster.rdp_vos_id})
        if normalize(cluster.assigned_rdp) and not rdp:
            audit["missing_rdp_references"].append({"type": "DialerCluster", "id": cluster.id, "cluster": cluster.cluster_name, "assigned_rdp": cluster.assigned_rdp})
        if is_missing(cluster.inbound_ip):
            audit["missing_ip_values"].append({"type": "DialerCluster", "id": cluster.id, "cluster": cluster.cluster_name, "field": "inbound_ip"})
        if rdp and normalize(cluster.assigned_rdp) and cluster.assigned_rdp != rdp.portal_type:
            audit["stale_copied_names"].append({"type": "DialerCluster", "id": cluster.id, "field": "assigned_rdp", "stored": cluster.assigned_rdp, "live": rdp.portal_type})
        if rdp and normalize(cluster.assigned_rdp_ip) and cluster.assigned_rdp_ip != rdp.server_ip:
            audit["stale_copied_names"].append({"type": "DialerCluster", "id": cluster.id, "field": "assigned_rdp_ip", "stored": cluster.assigned_rdp_ip, "live": rdp.server_ip})

    for gateway in gateways:
        rtng, media1, media2 = gateway_portals(db, gateway)
        for field in ["routing_gateway_id", "rtng_vos_id"]:
            vos_id = getattr(gateway, field)
            if vos_id and vos_id not in rtng_portals:
                audit["orphan_assignment_records"].append({"type": "RoutingGateway", "id": gateway.id, "field": field, "value": vos_id})
        for field, alias_field, portal in [("media1", "media_1_portal_id", media1), ("media2", "media_2_portal_id", media2)]:
            legacy_id = getattr(gateway, f"{field}_vos_id")
            alias_id = getattr(gateway, alias_field)
            name = getattr(gateway, f"{field}_name")
            for id_field, vos_id in [(f"{field}_vos_id", legacy_id), (alias_field, alias_id)]:
                if vos_id and vos_id not in media_portals:
                    issue = {"type": "RoutingGateway", "id": gateway.id, "field": id_field, "value": vos_id}
                    audit["missing_rdp_references"].append(issue)
                    audit["rdp_missing_links"].append(issue)
            if (normalize(name) or "").upper().startswith("RTNG"):
                audit["orphan_assignment_records"].append({"type": "RoutingGateway", "id": gateway.id, "field": f"{field}_name", "value": name, "message": f"Invalid mapping: Routing gateway selected as {field}"})
            if legacy_id and legacy_id not in rdp_portals and legacy_id not in media_portals:
                issue = {"type": "RoutingGateway", "id": gateway.id, "field": f"{field}_vos_id", "value": legacy_id}
                audit["missing_rdp_references"].append(issue)
                audit["rdp_missing_links"].append(issue)
            if normalize(name) and not portal:
                issue = {"type": "RoutingGateway", "id": gateway.id, "field": f"{field}_name", "value": name}
                audit["missing_rdp_references"].append(issue)
                audit["rdp_missing_links"].append(issue)
        for field, portal, stored_name, stored_ip in [
            ("gateway", rtng, gateway.gateway_name, gateway.gateway_ip),
            ("media1", media1, gateway.media1_name, gateway.media1_ip),
            ("media2", media2, gateway.media2_name, gateway.media2_ip),
        ]:
            if portal and normalize(stored_name) and stored_name != portal.portal_type:
                audit["stale_copied_names"].append({"type": "RoutingGateway", "id": gateway.id, "field": f"{field}_name", "stored": stored_name, "live": portal.portal_type})
            if portal and normalize(stored_ip) and stored_ip != portal.server_ip:
                audit["stale_copied_names"].append({"type": "RoutingGateway", "id": gateway.id, "field": f"{field}_ip", "stored": stored_ip, "live": portal.server_ip})
            if portal and is_missing(portal.server_ip):
                audit["missing_ip_values"].append({"type": "RoutingGateway", "id": gateway.id, "field": f"{field}_ip", "value": portal.server_ip})
        if is_missing(gateway.carrier_ip):
            audit["missing_ip_values"].append({"type": "RoutingGateway", "id": gateway.id, "field": "carrier_ip"})

    for model, label in [(BillingCharge, "BillingCharge"), (CDR, "CDR")]:
        for row in db.query(model).all():
            if row.cluster_id and not db.get(DialerCluster, row.cluster_id):
                audit["missing_cluster_references"].append({"type": label, "id": row.id, "cluster_id": row.cluster_id})
            if row.client_id and row.client_id not in clients:
                audit["missing_client_references"].append({"type": label, "id": row.id, "client_id": row.client_id})
    for model, label in [(ClientLedger, "ClientLedger"), (DataCost, "DataCost")]:
        for row in db.query(model).all():
            if row.client_id and row.client_id not in clients:
                audit["missing_client_references"].append({"type": label, "id": row.id, "client_id": row.client_id})
    return audit


def vos_desktop_records(db: Session):
    return db.query(VOSPortal).order_by(VOSPortal.portal_type.asc()).all()


def vos_type(portal_type: str | None):
    value = (portal_type or "").upper()
    if value.startswith("RDP"):
        return "RDP"
    if value.startswith("RTNG"):
        return "RTNG"
    if value.startswith("DID") or "DID" in value:
        return "DID"
    return "Other"


def vos_desktop_out(portal: VOSPortal):
    return {
        "id": portal.id,
        "vos_name": portal.portal_type,
        "portal_type": portal.portal_type,
        "vos_type": vos_type(portal.portal_type),
        "server_ip": portal.server_ip,
        "status": portal.status,
        "username": portal.username,
        "anti_hack_url": portal.anti_hack_url,
        "web_panel_url": portal.web_panel_url,
        "vos_port": portal.vos_port or 80,
        "vos_desktop_enabled": bool(portal.vos_desktop_enabled),
        "vos_notes": portal.vos_notes,
        "has_password": bool(portal.password),
    }


def vos_desktop_details_out(portal: VOSPortal):
    return {
        "id": portal.id,
        "vos_name": portal.portal_type,
        "vos_version": portal.vos_version,
        "portal_type": portal.portal_type,
        "server_ip": portal.server_ip,
        "web_panel_url": portal.web_panel_url,
        "username": portal.username,
        "password": portal.password,
        "anti_hack_url": portal.anti_hack_url,
        "anti_hack_password": portal.anti_hack_password,
        "uuid": portal.uuid,
        "notes": portal.notes or portal.vos_notes,
        "vos_notes": portal.vos_notes,
        "status": portal.status,
    }


def get_vos_desktop_portal(db: Session, record_id: int):
    return get_record(db, VOSPortal, record_id)


@app.get("/api/vos-desktop", response_model=list[VOSDesktopOut])
@app.get("/vos-desktop", response_model=list[VOSDesktopOut])
def get_vos_desktop(db: Session = Depends(get_db), user: User = Depends(require_vos_desktop())):
    return [vos_desktop_out(portal) for portal in vos_desktop_records(db)]


@app.get("/api/vos-desktop/download-launcher")
@app.get("/vos-desktop/download-launcher")
def download_vos_launcher(user: User = Depends(require_vos_desktop("can_export"))):
    root = Path(__file__).resolve().parent.parent
    agent_dir = root / "local-agent"
    if not agent_dir.exists():
        raise HTTPException(status_code=404, detail="Local agent package is missing")
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in agent_dir.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(root).as_posix())
        docs_path = root / "docs" / "LOCAL_AGENT.md"
        if docs_path.exists():
            archive.write(docs_path, "docs/LOCAL_AGENT.md")
    buffer.seek(0)
    headers = {"Content-Disposition": 'attachment; filename="noc360-local-launcher.zip"'}
    return StreamingResponse(buffer, media_type="application/zip", headers=headers)


@app.get("/api/vos-desktop/{record_id}/details", response_model=VOSDesktopDetailsOut)
@app.get("/vos-desktop/{record_id}/details", response_model=VOSDesktopDetailsOut)
def get_vos_desktop_details(record_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(require_vos_desktop("can_export"))):
    portal = get_vos_desktop_portal(db, record_id)
    log_activity(db, user, "view_credentials", "vos_desktop", "VOSPortal", portal.id, f"VOS details viewed for {portal.portal_type}", request=request, commit=True)
    return vos_desktop_details_out(portal)


@app.get("/api/vos-desktop/{record_id}/login", response_model=VOSDesktopLoginOut)
@app.get("/vos-desktop/{record_id}/login", response_model=VOSDesktopLoginOut)
def get_vos_desktop_login(record_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(require_vos_desktop("can_export"))):
    portal = get_vos_desktop_portal(db, record_id)
    log_activity(db, user, "copy_credentials", "vos_desktop", "VOSPortal", portal.id, f"VOS credentials copied for {portal.portal_type}", request=request, commit=True)
    return {"server": portal.server_ip, "username": portal.username, "password": portal.password, "anti_hack_url": portal.anti_hack_url, "anti_hack_password": portal.anti_hack_password}


@app.put("/api/vos-desktop/{record_id}", response_model=VOSDesktopOut)
@app.put("/vos-desktop/{record_id}", response_model=VOSDesktopOut)
def update_vos_desktop(record_id: int, payload: VOSDesktopUpdateIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_vos_desktop("can_edit"))):
    portal = get_vos_desktop_portal(db, record_id)
    old_value = sanitize_activity_value(portal)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(portal, key, value)
    db.commit()
    db.refresh(portal)
    log_activity(db, user, "update_vos_desktop", "vos_desktop", "VOSPortal", portal.id, f"VOS Desktop settings updated for {portal.portal_type}", old_value=old_value, new_value=portal, request=request, commit=True)
    return vos_desktop_out(portal)


@app.post("/api/vos-desktop/{record_id}/launch")
@app.post("/vos-desktop/{record_id}/launch")
def launch_vos_desktop(record_id: int, payload: VOSLaunchIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_vos_desktop("can_export"))) -> VOSLaunchOut:
    portal = get_vos_desktop_portal(db, record_id)
    launcher_path = normalize(payload.launcher_path) or normalize(payload.vos_path)
    shortcut_path = normalize(payload.shortcut_path)
    if not launcher_path:
        raise HTTPException(status_code=400, detail="Launcher not configured. Please create vos_launcher.bat in D:\\NOC360\\Launcher")
    if not shortcut_path:
        raise HTTPException(status_code=400, detail="Please set local VOS shortcut/app path first.")
    if is_missing(portal.server_ip):
        raise HTTPException(status_code=400, detail="Server IP is missing")
    anti_hack_url = portal.anti_hack_url or ""
    command = f'"{launcher_path}" "{anti_hack_url}" "{shortcut_path}"'
    log_activity(db, user, "launch_desktop", "vos_desktop", "VOSPortal", portal.id, f"VOS desktop launch requested for {portal.portal_type}", new_value={"launcher_path": launcher_path, "shortcut_path": shortcut_path, "anti_hack_url": bool(anti_hack_url)}, request=request, commit=True)
    return {
        "launcher_path": launcher_path,
        "shortcut_path": shortcut_path,
        "anti_hack_url": anti_hack_url,
        "command": command,
    }


@app.post("/api/vos-desktop/{record_id}/last-used")
@app.post("/vos-desktop/{record_id}/last-used")
def mark_vos_desktop_last_used(record_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(require_vos_desktop("can_export"))):
    get_vos_desktop_portal(db, record_id)
    return {"updated": True}


@app.get("/api/vos-portals", response_model=list[VOSPortalOut])
@app.get("/vos-portals", response_model=list[VOSPortalOut])
def get_vos_portals(db: Session = Depends(get_db), user: User = Depends(require_page("vos_portals"))):
    return list_records(db, VOSPortal)


@app.post("/api/vos-portals", response_model=VOSPortalOut)
@app.post("/vos-portals", response_model=VOSPortalOut)
def create_vos_portal(payload: VOSPortalCreate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_page("vos_portals", "can_create"))):
    validate_vos_portal(db, payload)
    saved = save_record(db, VOSPortal(**payload.model_dump()))
    log_activity(db, user, "create", "vos_portals", "VOSPortal", saved.id, f"Created VOS Portal {saved.portal_type}", new_value=saved, request=request, commit=True)
    return saved


@app.put("/api/vos-portals/{record_id}", response_model=VOSPortalOut)
@app.put("/vos-portals/{record_id}", response_model=VOSPortalOut)
def update_vos_portal(record_id: int, payload: VOSPortalUpdate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_page("vos_portals", "can_edit"))):
    validate_vos_portal(db, payload, record_id)
    record = get_record(db, VOSPortal, record_id)
    old_value = sanitize_activity_value(record)
    old_type = record.portal_type
    for key, value in payload.model_dump().items():
        setattr(record, key, value)
    sync_vos_references(db, old_type, record)
    saved = save_record(db, record)
    log_activity(db, user, "update", "vos_portals", "VOSPortal", saved.id, f"Updated VOS Portal {saved.portal_type}", old_value=old_value, new_value=saved, request=request, commit=True)
    return saved


@app.delete("/api/vos-portals/{record_id}")
@app.delete("/vos-portals/{record_id}")
def delete_vos_portal(record_id: int, db: Session = Depends(get_db), user: User = Depends(require_page("vos_portals", "can_delete"))):
    return delete_record(db, VOSPortal, record_id)


@app.get("/api/dialer-clusters", response_model=list[DialerClusterOut])
@app.get("/dialer-clusters", response_model=list[DialerClusterOut])
def get_dialer_clusters(db: Session = Depends(get_db), user: User = Depends(require_page("dialer_clusters"))):
    return db.query(DialerCluster).order_by(DialerCluster.cluster_no.asc()).all()


@app.post("/api/dialer-clusters", response_model=DialerClusterOut)
@app.post("/dialer-clusters", response_model=DialerClusterOut)
def create_dialer_cluster(payload: DialerClusterCreate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_page("dialer_clusters", "can_create"))):
    payload = apply_cluster_assignment_rules(db, payload)
    saved = save_record(db, DialerCluster(**payload.model_dump()))
    log_activity(db, user, "create", "dialer_clusters", "DialerCluster", saved.id, f"Created dialer cluster {saved.cluster_name}", new_value=saved, request=request, commit=True)
    return saved


@app.put("/api/dialer-clusters/{record_id}", response_model=DialerClusterOut)
@app.put("/dialer-clusters/{record_id}", response_model=DialerClusterOut)
def update_dialer_cluster(record_id: int, payload: DialerClusterUpdate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_page("dialer_clusters", "can_edit"))):
    record = get_record(db, DialerCluster, record_id)
    old_value = sanitize_activity_value(record)
    payload = apply_cluster_assignment_rules(db, payload, record_id)
    for key, value in payload.model_dump().items():
        setattr(record, key, value)
    saved = save_record(db, record)
    log_activity(db, user, "update", "dialer_clusters", "DialerCluster", saved.id, f"Updated dialer cluster {saved.cluster_name}", old_value=old_value, new_value=saved, request=request, commit=True)
    return saved


@app.delete("/api/dialer-clusters/{record_id}")
@app.delete("/dialer-clusters/{record_id}")
def delete_dialer_cluster(record_id: int, db: Session = Depends(get_db), user: User = Depends(require_page("dialer_clusters", "can_delete"))):
    return delete_record(db, DialerCluster, record_id)


@app.get("/api/rdps", response_model=list[RDPOut])
@app.get("/rdps", response_model=list[RDPOut])
@app.get("/api/rdp-media", response_model=list[RDPOut])
@app.get("/rdp-media", response_model=list[RDPOut])
def get_rdps(db: Session = Depends(get_db), user: User = Depends(require_page("rdp_media"))):
    clusters = db.query(DialerCluster).all()
    gateways = db.query(RoutingGateway).all()
    return [rdp_out(portal, clusters, gateways) for portal in get_rdp_portals(db)]


@app.post("/api/rdps")
def create_rdp(user: User = Depends(require_page("rdp_media", "can_create"))):
    raise HTTPException(status_code=405, detail="Create RDP records in VOS Portal Master using portal_type RDPxx")


@app.put("/api/rdps/{record_id}", response_model=RDPOut)
@app.put("/rdps/{record_id}", response_model=RDPOut)
def update_rdp(record_id: int, payload: RDPUpdate, db: Session = Depends(get_db), user: User = Depends(require_page("rdp_media", "can_edit"))):
    record = get_record(db, VOSPortal, record_id)
    if not record.portal_type.upper().startswith("RDP"):
        raise HTTPException(status_code=400, detail="Only RDP VOS portal records can be edited here")
    record.assigned_to = payload.assigned_to
    record.assigned_cluster = payload.assigned_cluster
    record.notes = payload.notes
    return rdp_out(save_record(db, record), db.query(DialerCluster).all(), db.query(RoutingGateway).all())


@app.delete("/api/rdps/{record_id}")
def delete_rdp(record_id: int, user: User = Depends(require_page("rdp_media", "can_delete"))):
    raise HTTPException(status_code=405, detail="Delete RDP records from VOS Portal Master")


@app.get("/api/routing-gateways", response_model=list[RoutingGatewayOut])
@app.get("/routing-gateways", response_model=list[RoutingGatewayOut])
def get_routing_gateways(db: Session = Depends(get_db), user: User = Depends(require_page("routing_gateways"))):
    rows = db.query(RoutingGateway).order_by(RoutingGateway.gateway_name.asc()).all()
    return [routing_gateway_out(row) for row in rows]


@app.post("/api/routing-gateways", response_model=RoutingGatewayOut)
@app.post("/routing-gateways", response_model=RoutingGatewayOut)
def create_routing_gateway(payload: RoutingGatewayCreate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_page("routing_gateways", "can_create"))):
    payload = apply_gateway_rules(db, payload)
    saved = save_record(db, RoutingGateway(**routing_gateway_db_payload(payload)))
    log_activity(db, user, "create", "routing_gateways", "RoutingGateway", saved.id, f"Created routing gateway mapping {saved.live_gateway_name}", new_value=routing_gateway_out(saved), request=request, commit=True)
    return routing_gateway_out(saved)


@app.put("/api/routing-gateways/{record_id}", response_model=RoutingGatewayOut)
@app.put("/routing-gateways/{record_id}", response_model=RoutingGatewayOut)
def update_routing_gateway(record_id: int, payload: RoutingGatewayUpdate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_page("routing_gateways", "can_edit"))):
    record = get_record(db, RoutingGateway, record_id)
    old_value = routing_gateway_out(record)
    payload = apply_gateway_rules(db, payload, record.id)
    for key, value in routing_gateway_db_payload(payload).items():
        setattr(record, key, value)
    saved = save_record(db, record)
    log_activity(db, user, "update", "routing_gateways", "RoutingGateway", saved.id, f"Updated routing gateway mapping {saved.live_gateway_name}", old_value=old_value, new_value=routing_gateway_out(saved), request=request, commit=True)
    return routing_gateway_out(saved)


@app.delete("/api/routing-gateways/{record_id}")
@app.delete("/routing-gateways/{record_id}")
def delete_routing_gateway(record_id: int, db: Session = Depends(get_db), user: User = Depends(require_page("routing_gateways", "can_delete"))):
    return delete_record(db, RoutingGateway, record_id)


@app.get("/clients", response_model=list[ClientOut])
@app.get("/api/clients", response_model=list[ClientOut])
def get_clients(db: Session = Depends(get_db), user: User = Depends(current_user)):
    query = db.query(Client)
    if user.role == "customer":
        allowed = user_client_ids(db, user)
        query = query.filter(Client.id.in_(allowed or [-1]))
    return [client_out(db, client) for client in query.order_by(Client.name.asc()).all()]


@app.post("/clients", response_model=ClientOut)
@app.post("/api/clients", response_model=ClientOut)
def create_client(payload: ClientCreate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_page("clients", "can_create"))):
    payload.name = normalize(payload.name)
    if not payload.name:
        raise HTTPException(status_code=400, detail="Client name is required")
    username = normalize(payload.login_username)
    password = normalize(payload.login_password)
    confirm = normalize(payload.confirm_password)
    if not username or not password:
        raise HTTPException(status_code=400, detail="Login username and password are required")
    if password != confirm:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=409, detail="Username already exists")
    client = Client(name=payload.name, status=payload.status, notes=payload.notes)
    db.add(client)
    db.flush()
    customer = User(username=username, password_hash=hash_password(password), role="customer", client_id=client.id, status="Active", full_name=payload.name)
    db.add(customer)
    db.flush()
    for page in ROLE_DEFAULT_PAGES["customer"]:
        db.add(PagePermission(user_id=customer.id, page_key=page, **default_rights_for_role("customer", page)))
    db.add(ClientAccess(user_id=customer.id, client_id=client.id))
    ensure_chat_room(db, client.id)
    db.commit()
    db.refresh(client)
    log_activity(db, user, "create", "clients", "Client", client.id, f"Created client {client.name}", new_value={"client": client, "login_user": username}, request=request, commit=True)
    return client_out(db, client)


@app.put("/clients/{record_id}", response_model=ClientOut)
@app.put("/api/clients/{record_id}", response_model=ClientOut)
def update_client(record_id: int, payload: ClientCreate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_page("clients", "can_edit"))):
    record = get_record(db, Client, record_id)
    old_value = sanitize_activity_value(record)
    payload.name = normalize(payload.name)
    if not payload.name:
        raise HTTPException(status_code=400, detail="Client name is required")
    record.name = payload.name
    record.status = payload.status
    record.notes = payload.notes
    saved = save_record(db, record)
    log_activity(db, user, "update", "clients", "Client", saved.id, f"Updated client {saved.name}", old_value=old_value, new_value=saved, request=request, commit=True)
    return client_out(db, saved)


@app.post("/clients/{record_id}/reset-password")
@app.post("/api/clients/{record_id}/reset-password")
def reset_client_password(record_id: int, payload: PasswordResetIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_page("clients", "can_edit"))):
    client = get_record(db, Client, record_id)
    customer = db.query(User).filter(User.role == "customer", User.client_id == record_id).order_by(User.id.asc()).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Linked customer user not found")
    if not normalize(payload.password):
        raise HTTPException(status_code=400, detail="Password is required")
    customer.password_hash = hash_password(payload.password)
    save_record(db, customer)
    log_activity(db, user, "reset_password", "clients", "Client", client.id, f"Reset customer login password for {client.name}", new_value={"customer_user": customer.username, "password_changed": True}, request=request, commit=True)
    return {"reset": True}


@app.delete("/clients/{record_id}")
@app.delete("/api/clients/{record_id}")
def delete_client(record_id: int, db: Session = Depends(get_db), user: User = Depends(require_page("clients", "can_delete"))):
    return delete_record(db, Client, record_id)


@app.get("/api/users", response_model=list[UserOut])
@app.get("/users", response_model=list[UserOut])
def get_users(db: Session = Depends(get_db), user: User = Depends(require_page("user_access"))):
    return [user_out(db, row) for row in db.query(User).order_by(User.id.asc()).all()]


@app.post("/api/users", response_model=UserOut)
@app.post("/users", response_model=UserOut)
def create_user(payload: UserCreate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_page("user_access", "can_create"))):
    username = normalize(payload.username)
    if not username or not normalize(payload.password):
        raise HTTPException(status_code=400, detail="Username and password are required")
    if payload.role not in {"admin", "noc_user", "customer", "viewer"}:
        raise HTTPException(status_code=400, detail="Invalid role")
    if payload.client_id and not db.get(Client, payload.client_id):
        raise HTTPException(status_code=400, detail="Client does not exist")
    record = User(username=username, password_hash=hash_password(payload.password), full_name=payload.full_name, email=payload.email, role=payload.role, client_id=payload.client_id, status=payload.status)
    saved = save_record(db, record)
    seed_user_access_defaults(db)
    log_activity(db, user, "create_user", "user_access", "User", saved.id, f"Created user {saved.username}", new_value=saved, request=request, commit=True)
    return user_out(db, saved)


@app.put("/api/users/{record_id}", response_model=UserOut)
@app.put("/users/{record_id}", response_model=UserOut)
def update_user(record_id: int, payload: UserUpdate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_page("user_access", "can_edit"))):
    record = get_record(db, User, record_id)
    old_value = sanitize_activity_value(record)
    if payload.role not in {"admin", "noc_user", "customer", "viewer"}:
        raise HTTPException(status_code=400, detail="Invalid role")
    if payload.client_id and not db.get(Client, payload.client_id):
        raise HTTPException(status_code=400, detail="Client does not exist")
    for key, value in payload.model_dump().items():
        setattr(record, key, normalize(value) if key == "username" else value)
    saved = save_record(db, record)
    seed_user_access_defaults(db)
    log_activity(db, user, "update_user", "user_access", "User", saved.id, f"Updated user {saved.username}", old_value=old_value, new_value=saved, request=request, commit=True)
    return user_out(db, saved)


@app.delete("/api/users/{record_id}")
@app.delete("/users/{record_id}")
def delete_user(record_id: int, db: Session = Depends(get_db), user: User = Depends(require_page("user_access", "can_delete"))):
    if record_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own user")
    db.query(PagePermission).filter(PagePermission.user_id == record_id).delete()
    db.query(ClientAccess).filter(ClientAccess.user_id == record_id).delete()
    return delete_record(db, User, record_id)


@app.post("/api/users/{record_id}/reset-password", response_model=UserOut)
@app.post("/users/{record_id}/reset-password", response_model=UserOut)
def reset_user_password(record_id: int, payload: PasswordResetIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_page("user_access", "can_edit"))):
    record = get_record(db, User, record_id)
    if not normalize(payload.password):
        raise HTTPException(status_code=400, detail="Password is required")
    record.password_hash = hash_password(payload.password)
    saved = save_record(db, record)
    log_activity(db, user, "reset_password", "user_access", "User", saved.id, f"Reset password for user {saved.username}", new_value={"username": saved.username, "password_changed": True}, request=request, commit=True)
    return user_out(db, saved)


@app.get("/api/users/{record_id}/permissions", response_model=list[PagePermissionOut])
@app.get("/users/{record_id}/permissions", response_model=list[PagePermissionOut])
def get_user_permissions(record_id: int, db: Session = Depends(get_db), user: User = Depends(require_page("user_access"))):
    get_record(db, User, record_id)
    return db.query(PagePermission).filter(PagePermission.user_id == record_id).order_by(PagePermission.page_key.asc()).all()


@app.post("/api/users/{record_id}/permissions", response_model=list[PagePermissionOut])
@app.post("/users/{record_id}/permissions", response_model=list[PagePermissionOut])
def save_user_permissions(record_id: int, payload: list[PagePermissionIn], request: Request, db: Session = Depends(get_db), user: User = Depends(require_page("user_access", "can_edit"))):
    get_record(db, User, record_id)
    old_value = [sanitize_activity_value(row) for row in db.query(PagePermission).filter(PagePermission.user_id == record_id).order_by(PagePermission.page_key.asc()).all()]
    db.query(PagePermission).filter(PagePermission.user_id == record_id).delete()
    for item in payload:
        if item.page_key not in ALLOWED_PERMISSION_KEYS:
            raise HTTPException(status_code=400, detail=f"Invalid page key: {item.page_key}")
        db.add(PagePermission(user_id=record_id, page_key=item.page_key, can_view=int(item.can_view), can_create=int(item.can_create), can_edit=int(item.can_edit), can_delete=int(item.can_delete), can_export=int(item.can_export)))
    db.commit()
    log_activity(db, user, "update_permissions", "user_access", "User", record_id, "Updated page permission matrix", old_value=old_value, new_value=[item.model_dump() for item in payload], request=request, commit=True)
    return get_user_permissions(record_id, db, user)


@app.get("/api/users/{record_id}/client-access")
@app.get("/users/{record_id}/client-access")
def get_user_client_access(record_id: int, db: Session = Depends(get_db), user: User = Depends(require_page("user_access"))):
    get_record(db, User, record_id)
    return {"client_ids": [row.client_id for row in db.query(ClientAccess).filter(ClientAccess.user_id == record_id).all()]}


@app.post("/api/users/{record_id}/client-access")
@app.post("/users/{record_id}/client-access")
def save_user_client_access(record_id: int, payload: ClientAccessIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_page("user_access", "can_edit"))):
    record = get_record(db, User, record_id)
    old_value = {"client_ids": [row.client_id for row in db.query(ClientAccess).filter(ClientAccess.user_id == record_id).all()]}
    valid_ids = {client.id for client in db.query(Client).all()}
    if any(client_id not in valid_ids for client_id in payload.client_ids):
        raise HTTPException(status_code=400, detail="Invalid client id")
    db.query(ClientAccess).filter(ClientAccess.user_id == record_id).delete()
    for client_id in payload.client_ids:
        db.add(ClientAccess(user_id=record_id, client_id=client_id))
    if record.role == "customer" and payload.client_ids:
        record.client_id = payload.client_ids[0]
    db.commit()
    log_activity(db, user, "update_client_access", "user_access", "User", record_id, f"Updated client access for {record.username}", old_value=old_value, new_value={"client_ids": payload.client_ids}, request=request, commit=True)
    return {"client_ids": payload.client_ids}


@app.get("/api/clients/{record_id}/detail")
@app.get("/clients/{record_id}/detail")
@app.get("/api/clients/{record_id}/details")
@app.get("/clients/{record_id}/details")
def get_client_detail(record_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.role == "customer" and user.client_id != record_id:
        raise HTTPException(status_code=403, detail="Cannot view another customer")
    if user.role != "admin" and user.role != "customer":
        allowed = user_client_ids(db, user)
        if allowed and record_id not in allowed:
            raise HTTPException(status_code=403, detail="Client access denied")
    client = get_record(db, Client, record_id)
    clusters = db.query(DialerCluster).filter(DialerCluster.client_id == record_id).all()
    rdps = sorted({cluster.live_rdp_name for cluster in clusters if normalize(cluster.live_rdp_name)})
    gateways = db.query(RoutingGateway).all()
    used_gateways = []
    for gateway in gateways:
        sync_gateway_live_fields(gateway)
        media = {normalize(gateway.live_media1_name), normalize(gateway.live_media2_name)}
        if any(rdp in media for rdp in rdps):
            used_gateways.append(gateway.live_gateway_name)
    ledger = db.query(ClientLedger).filter(ClientLedger.client_id == record_id).order_by(ClientLedger.entry_date.desc(), ClientLedger.id.desc()).all()
    data_costs = db.query(DataCost).filter(DataCost.client_id == record_id).order_by(DataCost.entry_date.desc(), DataCost.id.desc()).all()
    total_charges = sum(row.debit_usd or row.debit_amount or 0 for row in ledger)
    total_payments = sum(row.credit_usd or row.credit_amount or 0 for row in ledger)
    total_charges_inr = sum(row.debit_inr or 0 for row in ledger)
    total_payments_inr = sum(row.credit_inr or 0 for row in ledger)
    return {
        "client": {"id": client.id, "name": client.name, "status": client.status, "notes": client.notes},
        "assigned_clusters": [cluster_assignment_out(cluster) for cluster in clusters],
        "assigned_rdps": rdps,
        "routing_gateways": used_gateways,
        "total_charges": round(total_charges, 2),
        "total_payments": round(total_payments, 2),
        "total_outstanding": round(total_charges - total_payments, 2),
        "total_charges_inr": round(total_charges_inr, 2),
        "total_payments_inr": round(total_payments_inr, 2),
        "total_outstanding_inr": round(total_charges_inr - total_payments_inr, 2),
        "ledger": ledger,
        "data_costs": data_costs,
    }


@app.get("/api/ledger", response_model=ClientLedgerPageOut)
@app.get("/ledger", response_model=ClientLedgerPageOut)
@app.get("/api/billing/ledger", response_model=ClientLedgerPageOut)
@app.get("/billing/ledger", response_model=ClientLedgerPageOut)
def get_ledger(
    client_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    category: str | None = None,
    entry_type: str | None = None,
    search: str | None = None,
    created_by: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: str = Query(default="50"),
    db: Session = Depends(get_db),
    user: User = Depends(require_any_page(("billing", "can_view"), ("my_ledger", "can_view"))),
):
    start_date = from_date or date_from
    end_date = to_date or date_to
    query = ledger_query(db, user, client_id, start_date, end_date, category, entry_type, search, created_by)
    total = query.count()
    requested_all = str(page_size).lower() == "all"
    if requested_all:
        size = total or 0
        total_pages = 1
        current_page = 1
        items = query.order_by(ClientLedger.entry_date.desc(), ClientLedger.id.desc()).all()
    else:
        try:
            size = int(page_size)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="page_size must be 25, 50, 100, or all") from exc
        if size not in {25, 50, 100}:
            raise HTTPException(status_code=400, detail="page_size must be 25, 50, 100, or all")
        total_pages = max(1, (total + size - 1) // size)
        current_page = min(page, total_pages)
        items = query.order_by(ClientLedger.entry_date.desc(), ClientLedger.id.desc()).offset((current_page - 1) * size).limit(size).all()
    logger.info(
        "Ledger fetch user=%s client_id=%s from_date=%s to_date=%s category=%s entry_type=%s search=%s created_by=%s page=%s page_size=%s total=%s",
        user.username,
        client_id,
        start_date,
        end_date,
        category,
        entry_type,
        search,
        created_by,
        current_page,
        "all" if requested_all else size,
        total,
    )
    return {"items": items, "total": total, "page": current_page, "page_size": size, "total_pages": total_pages}


@app.post("/api/ledger", response_model=ClientLedgerMutationOut)
@app.post("/ledger", response_model=ClientLedgerMutationOut)
@app.post("/api/billing/ledger", response_model=ClientLedgerMutationOut)
@app.post("/billing/ledger", response_model=ClientLedgerMutationOut)
def create_ledger(payload: ClientLedgerCreate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_page("billing", "can_create"))):
    data = ledger_payload_values(db, payload, user)
    record = ClientLedger(**data)
    db.add(record)
    db.flush()
    recalc_client_ledger(db, payload.client_id)
    db.commit()
    db.refresh(record)
    logger.info("Ledger entry saved id=%s client_id=%s user=%s", record.id, record.client_id, user.username)
    log_activity(db, user, "create_ledger", "billing", "ClientLedger", record.id, f"Created {record.entry_type} ledger entry for {record.client_name}", new_value=record, request=request, commit=True)
    return {"success": True, "entry": record}


@app.put("/api/ledger/{record_id}", response_model=ClientLedgerMutationOut)
@app.put("/ledger/{record_id}", response_model=ClientLedgerMutationOut)
@app.put("/api/billing/ledger/{record_id}", response_model=ClientLedgerMutationOut)
@app.put("/billing/ledger/{record_id}", response_model=ClientLedgerMutationOut)
def update_ledger(record_id: int, payload: ClientLedgerCreate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_page("billing", "can_edit"))):
    record = get_record(db, ClientLedger, record_id)
    old_value = sanitize_activity_value(record)
    old_client_id = record.client_id
    data = ledger_payload_values(db, payload)
    data.pop("created_by", None)
    for key, value in data.items():
        setattr(record, key, value)
    db.flush()
    recalc_client_ledger(db, old_client_id)
    if old_client_id != payload.client_id:
        recalc_client_ledger(db, payload.client_id)
    db.commit()
    db.refresh(record)
    logger.info("Ledger entry updated id=%s old_client_id=%s client_id=%s user=%s", record.id, old_client_id, record.client_id, user.username)
    log_activity(db, user, "update_ledger", "billing", "ClientLedger", record.id, f"Updated ledger entry {record.id}", old_value=old_value, new_value=record, request=request, commit=True)
    return {"success": True, "entry": record}


@app.delete("/api/ledger/{record_id}")
@app.delete("/ledger/{record_id}")
@app.delete("/api/billing/ledger/{record_id}")
@app.delete("/billing/ledger/{record_id}")
def delete_ledger(record_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(require_page("billing", "can_delete"))):
    record = get_record(db, ClientLedger, record_id)
    old_value = sanitize_activity_value(record)
    client_id = record.client_id
    db.delete(record)
    db.flush()
    recalc_client_ledger(db, client_id)
    db.commit()
    logger.info("Ledger entry deleted id=%s client_id=%s user=%s", record_id, client_id, user.username)
    log_activity(db, user, "delete_ledger", "billing", "ClientLedger", record_id, f"Deleted ledger entry {record_id}", old_value=old_value, request=request, commit=True)
    return {"success": True, "deleted_id": record_id}


@app.get("/api/ledger/summary")
@app.get("/ledger/summary")
@app.get("/api/billing/client-outstanding")
@app.get("/billing/client-outstanding")
def get_ledger_summary(client_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(require_any_page(("billing", "can_view"), ("my_ledger", "can_view")))):
    return ledger_summary(ledger_query(db, user, client_id).all())


@app.get("/api/settings/billing-rate", response_model=BillingSettingOut)
@app.get("/settings/billing-rate", response_model=BillingSettingOut)
@app.get("/api/billing/rate", response_model=BillingSettingOut)
@app.get("/billing/rate", response_model=BillingSettingOut)
def get_billing_rate(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return get_billing_setting(db)


@app.put("/api/settings/billing-rate", response_model=BillingSettingOut)
@app.put("/settings/billing-rate", response_model=BillingSettingOut)
@app.post("/api/billing/rate", response_model=BillingSettingOut)
@app.post("/billing/rate", response_model=BillingSettingOut)
def update_billing_rate(payload: BillingSettingUpdate, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    if payload.usd_to_inr_rate <= 0:
        raise HTTPException(status_code=400, detail="USD to INR rate must be greater than zero")
    setting = get_billing_setting(db)
    setting.usd_to_inr_rate = round(payload.usd_to_inr_rate, 4)
    return save_record(db, setting)


@app.get("/api/billing", response_model=list[BillingChargeOut])
@app.get("/billing", response_model=list[BillingChargeOut])
def get_billing(
    client_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    charge_type: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_any_page(("billing", "can_view"), ("my_ledger", "can_view"))),
):
    return billing_query(db, user, client_id, date_from, date_to, charge_type).order_by(BillingCharge.billing_date.desc(), BillingCharge.id.desc()).all()


@app.post("/api/billing", response_model=BillingChargeOut)
@app.post("/billing", response_model=BillingChargeOut)
def create_billing(payload: BillingChargeCreate, db: Session = Depends(get_db), user: User = Depends(require_page("billing", "can_create"))):
    if payload.charge_type not in CHARGE_TYPES:
        raise HTTPException(status_code=400, detail="Invalid charge type")
    if not db.get(Client, payload.client_id):
        raise HTTPException(status_code=400, detail="Client does not exist")
    record = BillingCharge(**payload.model_dump(), created_by=user.username)
    return save_record(db, record)


@app.put("/api/billing/{record_id}", response_model=BillingChargeOut)
@app.put("/billing/{record_id}", response_model=BillingChargeOut)
def update_billing(record_id: int, payload: BillingChargeUpdate, db: Session = Depends(get_db), user: User = Depends(require_page("billing", "can_edit"))):
    record = get_record(db, BillingCharge, record_id)
    for key, value in payload.model_dump().items():
        setattr(record, key, value)
    return save_record(db, record)


@app.delete("/api/billing/{record_id}")
@app.delete("/billing/{record_id}")
def delete_billing(record_id: int, db: Session = Depends(get_db), user: User = Depends(require_page("billing", "can_delete"))):
    return delete_record(db, BillingCharge, record_id)


@app.get("/api/billing/summary")
@app.get("/billing/summary")
def get_billing_summary(
    client_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_any_page(("billing", "can_view"), ("my_ledger", "can_view"))),
):
    rows = billing_query(db, user, client_id, date_from, date_to).all()
    return billing_summary(rows)


@app.get("/api/cdr", response_model=list[CDROut])
@app.get("/cdr", response_model=list[CDROut])
def get_cdr(
    client_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    search: str | None = None,
    disposition: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_any_page(("cdr", "can_view"), ("my_cdr", "can_view"))),
):
    return cdr_query(db, user, client_id, date_from, date_to, search, disposition).order_by(CDR.call_date.desc()).limit(1000).all()


@app.post("/api/cdr", response_model=CDROut)
@app.post("/cdr", response_model=CDROut)
def create_cdr(payload: CDRCreate, db: Session = Depends(get_db), user: User = Depends(require_page("cdr", "can_create"))):
    if not db.get(Client, payload.client_id):
        raise HTTPException(status_code=400, detail="Client does not exist")
    return save_record(db, CDR(**payload.model_dump()))


@app.put("/api/cdr/{record_id}", response_model=CDROut)
@app.put("/cdr/{record_id}", response_model=CDROut)
def update_cdr(record_id: int, payload: CDRUpdate, db: Session = Depends(get_db), user: User = Depends(require_page("cdr", "can_edit"))):
    record = get_record(db, CDR, record_id)
    for key, value in payload.model_dump().items():
        setattr(record, key, value)
    return save_record(db, record)


@app.delete("/api/cdr/{record_id}")
@app.delete("/cdr/{record_id}")
def delete_cdr(record_id: int, db: Session = Depends(get_db), user: User = Depends(require_page("cdr", "can_delete"))):
    return delete_record(db, CDR, record_id)


@app.get("/api/cdr/summary")
@app.get("/cdr/summary")
def get_cdr_summary(
    client_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    search: str | None = None,
    disposition: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_any_page(("cdr", "can_view"), ("my_cdr", "can_view"))),
):
    return cdr_summary(cdr_query(db, user, client_id, date_from, date_to, search, disposition).all())


@app.get("/api/management/summary")
@app.get("/management/summary")
def get_management_summary(db: Session = Depends(get_db), user: User = Depends(require_page("management_portal"))):
    return management_summary(db)


@app.get("/api/management/cluster-assignments")
@app.get("/management/cluster-assignments")
@app.get("/api/management/cluster-client-assignments")
@app.get("/management/cluster-client-assignments")
def get_cluster_assignments(db: Session = Depends(get_db), user: User = Depends(require_page("management_portal"))):
    clusters = db.query(DialerCluster).order_by(DialerCluster.cluster_no.asc()).all()
    return [cluster_assignment_out(cluster) for cluster in clusters]


@app.put("/api/management/cluster-assignments")
@app.put("/management/cluster-assignments")
@app.post("/api/management/cluster-client-assignments")
@app.post("/management/cluster-client-assignments")
@app.post("/api/management/cluster-assignments")
@app.post("/management/cluster-assignments")
def save_cluster_assignment(payload: ClusterAccountAssignmentIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_page("management_portal", "can_edit"))):
    cluster = get_record(db, DialerCluster, payload.cluster_id)
    old_value = sanitize_activity_value(cluster)
    if payload.client_id is not None and not db.get(Client, payload.client_id):
        raise HTTPException(status_code=400, detail="Client does not exist")
    cluster.client_id = payload.client_id
    saved = save_record(db, cluster)
    log_activity(db, user, "update_cluster_client_assignment", "management_portal", "DialerCluster", saved.id, f"Updated client assignment for {saved.cluster_name}", old_value=old_value, new_value=saved, request=request, commit=True)
    return cluster_assignment_out(saved)


@app.get("/api/management/rdp-cluster-assignments")
@app.get("/management/rdp-cluster-assignments")
def get_rdp_cluster_assignments(db: Session = Depends(get_db), user: User = Depends(require_page("management_portal"))):
    clusters = db.query(DialerCluster).order_by(DialerCluster.cluster_no.asc()).all()
    duplicate_names = active_rdp_duplicate_names(clusters)
    return [rdp_cluster_assignment_out(cluster, duplicate_names) for cluster in clusters]


@app.put("/api/management/rdp-cluster-assignments")
@app.put("/management/rdp-cluster-assignments")
@app.post("/api/management/rdp-cluster-assignments")
@app.post("/management/rdp-cluster-assignments")
def save_rdp_cluster_assignment(payload: RDPClusterAssignmentIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_page("management_portal", "can_edit"))):
    cluster = get_record(db, DialerCluster, payload.cluster_id)
    old_value = sanitize_activity_value(cluster)
    payload_data = DialerClusterUpdate(
        cluster_no=cluster.cluster_no,
        account_name=cluster.account_name,
        db_ip=cluster.db_ip,
        web_ips=cluster.web_ips,
        asterisk_ips=cluster.asterisk_ips,
        inbound_ip=cluster.inbound_ip,
        client_id=cluster.client_id,
        dids_patch=cluster.dids_patch,
        in_id=cluster.in_id,
        assigned_rdp=payload.assigned_rdp,
        assigned_rdp_ip=cluster.assigned_rdp_ip,
        rdp_vos_id=payload.rdp_vos_id,
        status=cluster.status,
    )
    payload_data = apply_cluster_assignment_rules(db, payload_data, cluster.id)
    cluster.assigned_rdp = payload_data.assigned_rdp
    cluster.assigned_rdp_ip = payload_data.assigned_rdp_ip
    cluster.rdp_vos_id = payload_data.rdp_vos_id
    saved = save_record(db, cluster)
    log_activity(db, user, "update_rdp_assignment", "management_portal", "DialerCluster", saved.id, f"Updated RDP assignment for {saved.cluster_name}", old_value=old_value, new_value=saved, request=request, commit=True)
    duplicate_names = active_rdp_duplicate_names(db.query(DialerCluster).all())
    return rdp_cluster_assignment_out(saved, duplicate_names)


@app.get("/api/management/routing-media-assignments")
@app.get("/management/routing-media-assignments")
def get_routing_media_assignments(db: Session = Depends(get_db), user: User = Depends(require_page("management_portal"))):
    mappings = {mapping.gateway_name: mapping for mapping in db.query(RoutingGateway).all()}
    mappings_by_id = {(mapping.routing_gateway_id or mapping.rtng_vos_id): mapping for mapping in mappings.values() if (mapping.routing_gateway_id or mapping.rtng_vos_id)}
    clusters = db.query(DialerCluster).all()
    for mapping in mappings.values():
        mapping._management_clusters = clusters
    return [
        routing_media_assignment_out(gateway.portal_type, gateway.server_ip, mappings_by_id.get(gateway.id) or mappings.get(gateway.portal_type))
        for gateway in get_rtng_portals(db)
    ]


@app.put("/api/management/routing-media-assignments")
@app.put("/management/routing-media-assignments")
@app.post("/api/management/routing-media-assignments")
@app.post("/management/routing-media-assignments")
def save_routing_media_assignment(payload: RoutingMediaAssignmentIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_page("management_portal", "can_edit"))):
    gateway = get_portal_by_id(db, payload.routing_gateway_id, "RTNG") or get_portal_by_id(db, payload.rtng_vos_id, "RTNG") or get_portal_by_type(db, payload.gateway_name, "RTNG")
    if not gateway:
        raise HTTPException(status_code=400, detail="Routing gateway must exist in VOS Portal Master")

    data = RoutingGatewayUpdate(
        gateway_name=gateway.portal_type,
        gateway_ip=gateway.server_ip,
        routing_gateway_id=payload.routing_gateway_id or payload.rtng_vos_id or gateway.id,
        rtng_vos_id=payload.routing_gateway_id or payload.rtng_vos_id or gateway.id,
        media_1_name=payload.media_1_name or payload.media1_name,
        media_1_ip=None,
        media_1_portal_id=payload.media_1_portal_id or payload.media1_vos_id,
        media1_name=payload.media_1_name or payload.media1_name,
        media1_ip=None,
        media1_vos_id=payload.media_1_portal_id or payload.media1_vos_id,
        media_2_name=payload.media_2_name or payload.media2_name,
        media_2_ip=None,
        media_2_portal_id=payload.media_2_portal_id or payload.media2_vos_id,
        media2_name=payload.media_2_name or payload.media2_name,
        media2_ip=None,
        media2_vos_id=payload.media_2_portal_id or payload.media2_vos_id,
        carrier_ip=payload.carrier_ip,
        ports=payload.ports,
        vendor=payload.vendor or payload.vendor_name,
        vendor_name=payload.vendor or payload.vendor_name,
        status=payload.status,
    )
    record = db.query(RoutingGateway).filter(or_(RoutingGateway.routing_gateway_id == data.routing_gateway_id, RoutingGateway.rtng_vos_id == data.rtng_vos_id)).first()
    if not record:
        record = db.query(RoutingGateway).filter(RoutingGateway.gateway_name == data.gateway_name).first()
    old_value = routing_gateway_out(record) if record else None
    data = apply_gateway_rules(db, data, record.id if record else None)
    if not record:
        record = RoutingGateway(**routing_gateway_db_payload(data))
    else:
        for key, value in routing_gateway_db_payload(data).items():
            setattr(record, key, value)
    saved = save_record(db, record)
    log_activity(db, user, "update_routing_assignment", "management_portal", "RoutingGateway", saved.id, f"Updated routing media assignment for {saved.live_gateway_name}", old_value=old_value, new_value=routing_gateway_out(saved), request=request, commit=True)
    saved._management_clusters = db.query(DialerCluster).all()
    return routing_media_assignment_out(saved.gateway_name, saved.gateway_ip, saved)


@app.get("/api/dashboard")
@app.get("/dashboard")
@app.get("/api/dashboard/summary")
@app.get("/dashboard/summary")
@app.get("/api/dashboard/brief")
@app.get("/dashboard/brief")
def dashboard(db: Session = Depends(get_db), user: User = Depends(require_page("dashboard"))):
    return operational_dashboard(db)


@app.get("/api/system/audit")
@app.get("/system/audit")
def get_system_audit(db: Session = Depends(get_db), user: User = Depends(require_page("management_portal"))):
    return system_audit(db)


@app.get("/api/reports/ledger")
@app.get("/reports/ledger")
def report_ledger(client_ids: str | None = None, date_from: date | None = None, date_to: date | None = None, db: Session = Depends(get_db), user: User = Depends(require_any_page(("reports", "can_view"), ("my_reports", "can_view")))):
    rows = scoped_ledger_rows(db, user, client_ids, date_from, date_to)
    result = []
    by_client = {}
    for row in rows:
        item = by_client.setdefault(row.client_id, {"client": row.client_name, "opening_balance_usd": 0, "opening_balance_inr": 0, "debit_usd": 0, "credit_usd": 0, "debit_inr": 0, "credit_inr": 0, "closing_outstanding_usd": 0, "closing_outstanding_inr": 0})
        item["debit_usd"] += row_debit_usd(row)
        item["credit_usd"] += row_credit_usd(row)
        item["debit_inr"] += row_debit_inr(row)
        item["credit_inr"] += row_credit_inr(row)
        item["closing_outstanding_usd"] = row.balance_usd or row.balance_after_entry or 0
        item["closing_outstanding_inr"] = row.balance_inr or 0
    for item in by_client.values():
        for key in list(item.keys()):
            if key != "client":
                item[key] = round(item[key], 2)
        result.append(item)
    return result


@app.get("/api/reports/daily-billing")
@app.get("/reports/daily-billing")
def report_daily_billing(client_ids: str | None = None, date_from: date | None = None, date_to: date | None = None, charge_type: str | None = None, db: Session = Depends(get_db), user: User = Depends(require_any_page(("reports", "can_view"), ("my_reports", "can_view")))):
    rows = scoped_ledger_rows(db, user, client_ids, date_from, date_to)
    if charge_type:
        rows = [row for row in rows if row.category == charge_type]
    grouped = {}
    for row in rows:
        key = (row.entry_date.isoformat(), row.client_name)
        item = grouped.setdefault(key, {"date": key[0], "client": key[1], "Usage Charges USD": 0, "Usage Charges INR": 0, "DID Charges USD": 0, "DID Charges INR": 0, "Data Charges USD": 0, "Data Charges INR": 0, "Server Charges USD": 0, "Server Charges INR": 0, "Other Charges USD": 0, "Other Charges INR": 0, "Payment USD": 0, "Payment INR": 0, "outstanding_usd": 0, "outstanding_inr": 0})
        debit_usd = row_debit_usd(row)
        credit_usd = row_credit_usd(row)
        if row.entry_type == "Credit":
            item["Payment USD"] += credit_usd
            item["Payment INR"] += row_credit_inr(row)
        elif f"{row.category} USD" in item:
            item[f"{row.category} USD"] += debit_usd or credit_usd
            item[f"{row.category} INR"] += row_debit_inr(row) or row_credit_inr(row)
        elif row.entry_type == "Debit":
            item["Other Charges USD"] += debit_usd
            item["Other Charges INR"] += row_debit_inr(row)
        item["outstanding_usd"] += debit_usd - credit_usd
        item["outstanding_inr"] += row_debit_inr(row) - row_credit_inr(row)
    return [{key: (round(value, 2) if isinstance(value, (int, float)) else value) for key, value in item.items()} for item in grouped.values()]


@app.get("/api/reports/data-cost")
@app.get("/reports/data-cost")
def report_data_cost(client_ids: str | None = None, date_from: date | None = None, date_to: date | None = None, db: Session = Depends(get_db), user: User = Depends(require_any_page(("reports", "can_view"), ("my_reports", "can_view")))):
    return [
        {
            "date": row.entry_date,
            "client": row.client_name,
            "quantity": row.quantity,
            "rate_usd": row.rate_usd or row.rate,
            "total_data_cost_usd": round(cost_usd(row), 2),
            "exchange_rate": row.exchange_rate or DEFAULT_USD_TO_INR,
            "total_data_cost_inr": round(cost_inr(row), 2),
            "description": row.description,
        }
        for row in data_cost_rows(db, user, client_ids, date_from, date_to)
    ]


@app.post("/api/reports/data-cost", response_model=DataCostOut)
@app.post("/reports/data-cost", response_model=DataCostOut)
def create_data_cost(payload: DataCostCreate, db: Session = Depends(get_db), user: User = Depends(require_page("reports", "can_create"))):
    rate = payload.rate_usd if payload.rate_usd is not None else payload.rate
    total = round((payload.quantity or 0) * (rate or 0), 2)
    exchange = get_billing_setting(db).usd_to_inr_rate
    data = payload.model_dump()
    data.update({"rate": rate, "rate_usd": rate, "total_cost": total, "total_cost_usd": total, "exchange_rate": exchange, "total_cost_inr": round(total * exchange, 2)})
    return save_record(db, DataCost(**data))


@app.get("/api/reports/outstanding")
@app.get("/reports/outstanding")
def report_outstanding(client_ids: str | None = None, date_from: date | None = None, date_to: date | None = None, db: Session = Depends(get_db), user: User = Depends(require_any_page(("reports", "can_view"), ("my_reports", "can_view")))):
    financials = client_financials(db, user, client_ids, date_from, date_to)
    return [{"client": item["client"], "total_charges_usd": round(item["revenue"], 2), "total_charges_inr": round(item["revenue_inr"], 2), "total_payments_usd": round(item["credit"], 2), "total_payments_inr": round(item["credit_inr"], 2), "outstanding_usd": item["outstanding"], "outstanding_inr": item["outstanding_inr"]} for item in financials.values()]


@app.get("/api/reports/cluster-usage")
@app.get("/reports/cluster-usage")
def report_cluster_usage(client_ids: str | None = None, db: Session = Depends(get_db), user: User = Depends(require_any_page(("reports", "can_view"), ("my_reports", "can_view")))):
    ids = parse_ids(client_ids)
    if user.role == "customer":
        ids = [user.client_id]
    clusters = db.query(DialerCluster).all()
    if ids:
        clusters = [cluster for cluster in clusters if cluster.client_id in ids]
    gateways = db.query(RoutingGateway).all()
    for gateway in gateways:
        sync_gateway_live_fields(gateway)
    return [{"cluster": cluster.cluster_name, "client": cluster.client_name, "assigned_rdp": cluster.live_rdp_name, "rdp_ip": cluster.live_rdp_ip, "routing_gateway": next((gw.live_gateway_name for gw in gateways if cluster.live_rdp_name in {gw.live_media1_name, gw.live_media2_name}), None), "ports": next((gw.ports for gw in gateways if cluster.live_rdp_name in {gw.live_media1_name, gw.live_media2_name}), None), "status": cluster.status} for cluster in clusters]


@app.get("/api/reports/rdp-utilization")
@app.get("/reports/rdp-utilization")
def report_rdp_utilization(db: Session = Depends(get_db), user: User = Depends(require_any_page(("reports", "can_view"), ("my_reports", "can_view")))):
    clusters = db.query(DialerCluster).all()
    return [{"rdp": rdp.portal_type, "ip": rdp.server_ip, "assigned_cluster": (cluster.cluster_name if (cluster := next((c for c in clusters if c.live_rdp_name == rdp.portal_type and c.status != "Inactive"), None)) else None), "client": cluster.client_name if cluster else None, "status": rdp.status, "usage": "Used" if cluster else "Free"} for rdp in get_rdp_portals(db)]


@app.get("/api/reports/routing-capacity")
@app.get("/reports/routing-capacity")
def report_routing_capacity(db: Session = Depends(get_db), user: User = Depends(require_any_page(("reports", "can_view"), ("my_reports", "can_view")))):
    rows = db.query(RoutingGateway).all()
    for row in rows:
        sync_gateway_live_fields(row)
    return [{"gateway": row.live_gateway_name, "gateway_ip": row.live_gateway_ip, "media1": row.live_media1_name, "media2": row.live_media2_name, "carrier_ip": row.carrier_ip, "ports": row.ports, "vendor": row.vendor_name, "status": row.status} for row in rows]


@app.get("/api/reports/profit-margin")
@app.get("/reports/profit-margin")
def report_profit_margin(client_ids: str | None = None, date_from: date | None = None, date_to: date | None = None, db: Session = Depends(get_db), user: User = Depends(require_any_page(("reports", "can_view"), ("my_reports", "can_view")))):
    return [{"client": item["client"], "revenue_usd": round(item["revenue"], 2), "revenue_inr": round(item["revenue_inr"], 2), "data_cost_usd": round(item.get("data_cost", 0), 2), "data_cost_inr": round(item.get("data_cost_inr", 0), 2), "did_cost_usd": round(item["did_cost"], 2), "did_cost_inr": round(item["did_cost_inr"], 2), "server_cost_usd": round(item["server_cost"], 2), "server_cost_inr": round(item["server_cost_inr"], 2), "other_cost_usd": round(item["other_cost"], 2), "other_cost_inr": round(item["other_cost_inr"], 2), "profit_usd": item["profit"], "profit_inr": item["profit_inr"], "margin": item["margin"]} for item in client_financials(db, user, client_ids, date_from, date_to).values()]


@app.get("/api/business-ai/summary")
@app.get("/business-ai/summary")
def business_ai_summary(client_ids: str | None = None, date_from: date | None = None, date_to: date | None = None, charge_type: str | None = None, db: Session = Depends(get_db), user: User = Depends(require_page("business_ai"))):
    return business_ai_billing_summary(db, user, client_ids, date_from, date_to, charge_type)


def pct_change(current: float, previous: float):
    if not previous:
        return 100 if current else 0
    return round((current - previous) / previous * 100, 2)


def business_ai_billing_summary(db: Session, user: User, client_ids: str | None = None, date_from: date | None = None, date_to: date | None = None, charge_type: str | None = None):
    ledger_rows = scoped_ledger_rows(db, user, client_ids, date_from, date_to)
    if charge_type:
        ledger_rows = [row for row in ledger_rows if row.category == charge_type]
    billing_by_day = {}
    payment_by_day = {}
    by_type = {}
    by_client = {}
    today = date.today()
    month_start = today.replace(day=1)
    today_billing = today_billing_inr = monthly_billing = monthly_billing_inr = 0
    for row in ledger_rows:
        debit_usd = row_debit_usd(row)
        credit_usd = row_credit_usd(row)
        debit_inr = row_debit_inr(row)
        credit_inr = row_credit_inr(row)
        day_key = row.entry_date.isoformat()
        client = by_client.setdefault(row.client_id, {"client": row.client_name, "billing": 0, "billing_inr": 0, "payments": 0, "payments_inr": 0, "outstanding": 0, "outstanding_inr": 0})
        client["billing"] += debit_usd
        client["billing_inr"] += debit_inr
        client["payments"] += credit_usd
        client["payments_inr"] += credit_inr
        client["outstanding"] += debit_usd - credit_usd
        client["outstanding_inr"] += debit_inr - credit_inr
        if debit_usd:
            billing_by_day.setdefault(day_key, {"usd": 0, "inr": 0})
            billing_by_day[day_key]["usd"] += debit_usd
            billing_by_day[day_key]["inr"] += debit_inr
            by_type.setdefault(row.category, {"usd": 0, "inr": 0})
            by_type[row.category]["usd"] += debit_usd
            by_type[row.category]["inr"] += debit_inr
            if row.entry_date == today:
                today_billing += debit_usd
                today_billing_inr += debit_inr
            if row.entry_date >= month_start:
                monthly_billing += debit_usd
                monthly_billing_inr += debit_inr
        if credit_usd:
            payment_by_day.setdefault(day_key, {"usd": 0, "inr": 0})
            payment_by_day[day_key]["usd"] += credit_usd
            payment_by_day[day_key]["inr"] += credit_inr

    previous_rows = []
    if date_from and date_to:
        period_days = (date_to - date_from).days + 1
        prev_to = date_from - timedelta(days=1)
        prev_from = prev_to - timedelta(days=period_days - 1)
        previous_rows = scoped_ledger_rows(db, user, client_ids, prev_from, prev_to)
        if charge_type:
            previous_rows = [row for row in previous_rows if row.category == charge_type]
    prev_billing = sum(row_debit_usd(row) for row in previous_rows)
    prev_payment = sum(row_credit_usd(row) for row in previous_rows)
    prev_outstanding = sum(row_debit_usd(row) - row_credit_usd(row) for row in previous_rows)
    total_billing = sum(item["billing"] for item in by_client.values())
    total_billing_inr = sum(item["billing_inr"] for item in by_client.values())
    total_payments = sum(item["payments"] for item in by_client.values())
    total_payments_inr = sum(item["payments_inr"] for item in by_client.values())
    total_outstanding = sum(item["outstanding"] for item in by_client.values())
    total_outstanding_inr = sum(item["outstanding_inr"] for item in by_client.values())
    ranking = sorted(by_client.values(), key=lambda item: item["billing"], reverse=True)
    outstanding_rows = sorted(by_client.values(), key=lambda item: item["outstanding"], reverse=True)
    paid_clients = [item for item in by_client.values() if item["payments"] > 0]
    most_paid = max(paid_clients, key=lambda item: item["payments"], default=None)
    return {
        "cards": {
            "total_billing": round(total_billing, 2),
            "total_billing_inr": round(total_billing_inr, 2),
            "total_payments": round(total_payments, 2),
            "total_payments_inr": round(total_payments_inr, 2),
            "total_outstanding": round(total_outstanding, 2),
            "total_outstanding_inr": round(total_outstanding_inr, 2),
            "today_billing": round(today_billing, 2),
            "today_billing_inr": round(today_billing_inr, 2),
            "monthly_billing": round(monthly_billing, 2),
            "monthly_billing_inr": round(monthly_billing_inr, 2),
            "active_clients": db.query(Client).filter(Client.status == "Active").count(),
            "top_billing_client": ranking[0]["client"] if ranking else None,
            "highest_outstanding_client": outstanding_rows[0]["client"] if outstanding_rows else None,
            "top_payment_client": most_paid["client"] if most_paid else None,
        },
        "charts": {
            "billing_trend_by_day": [{"label": k, "value": round(v["usd"], 2), "value_inr": round(v["inr"], 2)} for k, v in sorted(billing_by_day.items())],
            "payment_trend_by_day": [{"label": k, "value": round(v["usd"], 2), "value_inr": round(v["inr"], 2)} for k, v in sorted(payment_by_day.items())],
            "outstanding_by_client": [{"client": item["client"], "outstanding": round(item["outstanding"], 2), "outstanding_inr": round(item["outstanding_inr"], 2)} for item in outstanding_rows],
            "client_billing_ranking": [{"client": item["client"], "billing": round(item["billing"], 2), "billing_inr": round(item["billing_inr"], 2), "payments": round(item["payments"], 2), "payments_inr": round(item["payments_inr"], 2), "outstanding": round(item["outstanding"], 2), "outstanding_inr": round(item["outstanding_inr"], 2)} for item in ranking],
            "charge_type_breakdown": [{"label": k, "value": round(v["usd"], 2), "value_inr": round(v["inr"], 2)} for k, v in by_type.items()],
            "client_growth_trend": [
                {"label": "Billing change", "value": pct_change(total_billing, prev_billing)},
                {"label": "Payment change", "value": pct_change(total_payments, prev_payment)},
                {"label": "Outstanding change", "value": pct_change(total_outstanding, prev_outstanding)},
            ],
        },
    }


@app.get("/api/business-ai/insights")
@app.get("/business-ai/insights")
def business_ai_insights(client_ids: str | None = None, date_from: date | None = None, date_to: date | None = None, charge_type: str | None = None, db: Session = Depends(get_db), user: User = Depends(require_page("business_ai"))):
    summary = business_ai_billing_summary(db, user, client_ids, date_from, date_to, charge_type)
    cards = summary["cards"]
    insights = []
    ranking = summary["charts"]["client_billing_ranking"]
    growth = summary["charts"]["client_growth_trend"]
    charge_types = summary["charts"]["charge_type_breakdown"]
    if cards["highest_outstanding_client"]:
        insights.append(f"{cards['highest_outstanding_client']} has the highest outstanding balance and needs payment follow-up.")
    if cards["top_billing_client"]:
        insights.append(f"{cards['top_billing_client']} has the highest billing in the selected period.")
    if cards["top_payment_client"]:
        insights.append(f"{cards['top_payment_client']} paid the most in the selected period.")
    if ranking:
        improving = next((row for row in ranking if row["payments"] >= row["billing"] and row["billing"] > 0), None)
        if improving:
            insights.append(f"{improving['client']} is improving because payments are covering current billing.")
        follow_up = next((row for row in ranking if row["outstanding"] > 0 and row["payments"] < row["billing"]), None)
        if follow_up:
            insights.append(f"{follow_up['client']} needs payment follow-up because billing is ahead of payments.")
    if charge_types:
        top_charge = max(charge_types, key=lambda row: row["value"])
        insights.append(f"{top_charge['label']} is the largest charge type in this period.")
    for row in growth:
        direction = "increased" if row["value"] > 0 else "decreased" if row["value"] < 0 else "remained flat"
        insights.append(f"{row['label']} {direction} by {abs(row['value'])}% compared with the previous period.")
    return {"insights": insights}
