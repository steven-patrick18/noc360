import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
from collections import Counter
from datetime import date, datetime, timedelta

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import inspect, or_, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import Base, SessionLocal, engine, get_db
from models import BillingCharge, BillingSetting, CDR, Client, ClientAccess, ClientLedger, DataCost, DialerCluster, PagePermission, RDP, RoutingGateway, User, VOSPortal
from schemas import (
    BillingChargeCreate,
    BillingChargeOut,
    BillingChargeUpdate,
    BillingSettingOut,
    BillingSettingUpdate,
    CDRCreate,
    CDROut,
    CDRUpdate,
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
    LoginIn,
    PagePermissionIn,
    PagePermissionOut,
    PasswordResetIn,
    TokenOut,
    UserCreate,
    UserUpdate,
    UserOut,
    VOSPortalCreate,
    VOSPortalOut,
    VOSPortalUpdate,
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
    "dialer_clusters",
    "rdp_media",
    "routing_gateways",
    "user_access",
]
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
}
ROLE_DEFAULT_PAGES = {
    "admin": PAGE_KEYS,
    "noc_user": ["dashboard", "management_portal", "billing", "reports", "vos_portals", "dialer_clusters", "rdp_media", "routing_gateways"],
    "viewer": ["dashboard", "reports"],
    "customer": ["my_dashboard", "my_ledger", "my_cdr", "my_reports"],
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
    rtng_vos_id: int | None = None
    media1_name: str | None = None
    media1_vos_id: int | None = None
    media2_name: str | None = None
    media2_vos_id: int | None = None
    carrier_ip: str | None = None
    ports: str | None = None
    vendor_name: str | None = None
    status: str = "Active"


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def b64url_decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        _, salt, digest = stored_hash.split("$", 2)
    except ValueError:
        return False
    return hmac.compare_digest(hash_password(password, salt), stored_hash)


def permission_dict(db: Session, user: User):
    if user.role == "admin":
        return {key: {"can_view": True, "can_create": True, "can_edit": True, "can_delete": True, "can_export": True} for key in PAGE_KEYS}
    rows = db.query(PagePermission).filter(PagePermission.user_id == user.id).all()
    if user.role == "customer":
        customer_pages = set(ROLE_DEFAULT_PAGES["customer"])
        rows = [row for row in rows if row.page_key in customer_pages]
    permissions = {
        row.page_key: {
            "can_view": bool(row.can_view),
            "can_create": bool(row.can_create),
            "can_edit": bool(row.can_edit),
            "can_delete": bool(row.can_delete),
            "can_export": bool(row.can_export),
        }
        for row in rows
    }
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


def require_page(page_key: str, action: str = "can_view"):
    def checker(user: User = Depends(current_user), db: Session = Depends(get_db)):
        if user.role == "admin":
            return user
        permission = permission_dict(db, user).get(page_key)
        if not permission or not permission.get(action):
            raise HTTPException(status_code=403, detail="Page permission denied")
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


def is_missing(value):
    stripped = normalize(value)
    return stripped is None or stripped.upper() == "#N/A"


def repair_sqlite_schema():
    if not str(engine.url).startswith("sqlite"):
        return
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    missing_by_table = {}
    if "rdp" in table_names:
        missing_by_table["rdp"] = {
            "assigned_cluster": "VARCHAR",
            "notes": "TEXT",
        }
    if "vos_portals" in table_names:
        missing_by_table["vos_portals"] = {
            "assigned_to": "VARCHAR",
            "assigned_cluster": "VARCHAR",
            "notes": "TEXT",
        }
    if "dialer_clusters" in table_names:
        missing_by_table["dialer_clusters"] = {
            "client_id": "INTEGER",
            "rdp_vos_id": "INTEGER",
        }
    if "users" in table_names:
        missing_by_table["users"] = {
            "full_name": "VARCHAR",
            "email": "VARCHAR",
            "created_at": "DATETIME",
        }
    if "client_ledger" in table_names:
        missing_by_table["client_ledger"] = {
            "amount_usd": "FLOAT",
            "exchange_rate": "FLOAT",
            "amount_inr": "FLOAT",
            "debit_usd": "FLOAT",
            "credit_usd": "FLOAT",
            "debit_inr": "FLOAT",
            "credit_inr": "FLOAT",
            "balance_usd": "FLOAT",
            "balance_inr": "FLOAT",
        }
    if "routing_gateways" in table_names:
        missing_by_table["routing_gateways"] = {
            "rtng_vos_id": "INTEGER",
            "client_id": "INTEGER",
            "media1_vos_id": "INTEGER",
            "media2_vos_id": "INTEGER",
            "notes": "TEXT",
        }
    if "data_costs" in table_names:
        missing_by_table["data_costs"] = {
            "rate_usd": "FLOAT",
            "total_cost_usd": "FLOAT",
            "exchange_rate": "FLOAT",
            "total_cost_inr": "FLOAT",
        }
    with engine.begin() as connection:
        for table, missing_columns in missing_by_table.items():
            columns = {column["name"] for column in inspector.get_columns(table)}
            for column, column_type in missing_columns.items():
                if column not in columns:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}"))


def create_database():
    Base.metadata.create_all(bind=engine)
    repair_sqlite_schema()


def seed_user_access_defaults(db: Session):
    clients_by_name = {client.name: client for client in db.query(Client).all()}
    default_users = [
        ("admin", "admin123", "admin", None, "System Admin", "admin@noc360.local"),
        ("noc", "noc123", "noc_user", None, "NOC Operator", "noc@noc360.local"),
        ("viewer", "viewer123", "viewer", None, "Read Only Viewer", "viewer@noc360.local"),
        ("im1", "123", "customer", "IM1", "IM1 Customer", "billing@im1.example"),
        ("im2", "123", "customer", "IM2", "IM2 Customer", "billing@im2.example"),
        ("rolex", "123", "customer", "ROLEX", "ROLEX Customer", "billing@rolex.example"),
    ]
    for username, password, role, client_name, full_name, email in default_users:
        client = clients_by_name.get(client_name) if client_name else None
        user = db.query(User).filter(User.username == username).first()
        if not user:
            db.add(User(username=username, password_hash=hash_password(password), role=role, client_id=client.id if client else None, status="Active", full_name=full_name, email=email))
        else:
            user.role = role
            user.client_id = client.id if client else user.client_id
            user.full_name = user.full_name or full_name
            user.email = user.email or email
            if username in {"noc", "viewer", "im1", "im2", "rolex"}:
                user.password_hash = hash_password(password)
    db.flush()
    for user in db.query(User).all():
        if user.role == "admin":
            pages = PAGE_KEYS
            rights = {"can_view": 1, "can_create": 1, "can_edit": 1, "can_delete": 1, "can_export": 1}
        else:
            pages = ROLE_DEFAULT_PAGES.get(user.role, [])
            readonly = user.role in {"viewer", "customer"}
            export_allowed = user.role != "viewer"
            rights = {"can_view": 1, "can_create": 0 if readonly else 1, "can_edit": 0 if readonly else 1, "can_delete": 0, "can_export": 1 if export_allowed else 0}
        existing = {row.page_key for row in db.query(PagePermission).filter(PagePermission.user_id == user.id).all()}
        for page in pages:
            if page not in existing:
                db.add(PagePermission(user_id=user.id, page_key=page, **rights))
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
        if gateway.rtng_vos_id is None and normalize(gateway.gateway_name) in rtng_by_name:
            gateway.rtng_vos_id = rtng_by_name[normalize(gateway.gateway_name)].id
            changed = True
        if gateway.media1_vos_id is None and normalize(gateway.media1_name) in rdp_by_name:
            gateway.media1_vos_id = rdp_by_name[normalize(gateway.media1_name)].id
            changed = True
        if gateway.media2_vos_id is None and normalize(gateway.media2_name) in rdp_by_name:
            gateway.media2_vos_id = rdp_by_name[normalize(gateway.media2_name)].id
            changed = True
        rtng = db.get(VOSPortal, gateway.rtng_vos_id) if gateway.rtng_vos_id else None
        media1 = db.get(VOSPortal, gateway.media1_vos_id) if gateway.media1_vos_id else None
        media2 = db.get(VOSPortal, gateway.media2_vos_id) if gateway.media2_vos_id else None
        if rtng:
            gateway.gateway_name, gateway.gateway_ip = rtng.portal_type, rtng.server_ip
        if media1:
            gateway.media1_name, gateway.media1_ip = media1.portal_type, media1.server_ip
        if media2:
            gateway.media2_name, gateway.media2_ip = media2.portal_type, media2.server_ip
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
        if not db.query(Client).first():
            from seed import seed_database

            seed_database(clear=False, db=db)
        backfill_reference_ids(db)
        get_billing_setting(db)
        normalize_ledger_currency(db)
        normalize_data_cost_currency(db)
        seed_user_access_defaults(db)


@app.get("/")
def home():
    return {"message": "NOC360 Backend Running"}

@app.get("/health")
@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/auth/login", response_model=TokenOut)
@app.post("/auth/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if user.status != "Active":
        raise HTTPException(status_code=403, detail="User is inactive")
    return {"access_token": create_token(user), "role": user.role, "client_id": user.client_id, "user": user_out(db, user)}


@app.get("/api/auth/me")
@app.get("/auth/me")
def me(user: User = Depends(current_user)):
    with SessionLocal() as db:
        return user_out(db, db.get(User, user.id))


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
        "routing_brief": [{"gateway_name": row.live_gateway_name, "gateway_ip": row.live_gateway_ip, "media1_name": row.live_media1_name, "media2_name": row.live_media2_name, "carrier_ip": row.carrier_ip, "ports": row.ports, "vendor_name": row.vendor_name, "status": row.status} for row in gateways],
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


def get_rdp_portals(db: Session):
    return portal_type_query(db, "RDP").order_by(VOSPortal.portal_type.asc()).all()


def get_rtng_portals(db: Session):
    return portal_type_query(db, "RTNG").order_by(VOSPortal.portal_type.asc()).all()


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


def gateway_portals(db: Session, gateway: RoutingGateway):
    rtng = get_portal_by_id(db, gateway.rtng_vos_id, "RTNG") or get_portal_by_type(db, gateway.gateway_name, "RTNG")
    media1 = get_portal_by_id(db, gateway.media1_vos_id, "RDP") or get_portal_by_type(db, gateway.media1_name, "RDP")
    media2 = get_portal_by_id(db, gateway.media2_vos_id, "RDP") or get_portal_by_type(db, gateway.media2_name, "RDP")
    return rtng, media1, media2


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
    if gateway.rtng_vos:
        gateway.gateway_name = gateway.rtng_vos.portal_type
        gateway.gateway_ip = gateway.rtng_vos.server_ip
    if gateway.media1_vos:
        gateway.media1_name = gateway.media1_vos.portal_type
        gateway.media1_ip = gateway.media1_vos.server_ip
    elif not normalize(gateway.media1_name):
        gateway.media1_ip = None
    if gateway.media2_vos:
        gateway.media2_name = gateway.media2_vos.portal_type
        gateway.media2_ip = gateway.media2_vos.server_ip
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

    if new_type.upper().startswith("RDP") or (old_type and old_type.upper().startswith("RDP")):
        if old_type and old_type != new_type:
            db.query(DialerCluster).filter(DialerCluster.assigned_rdp == old_type).update({"assigned_rdp": new_type})
            db.query(RoutingGateway).filter(RoutingGateway.media1_name == old_type).update({"media1_name": new_type})
            db.query(RoutingGateway).filter(RoutingGateway.media2_name == old_type).update({"media2_name": new_type})
        db.query(DialerCluster).filter(DialerCluster.rdp_vos_id == portal.id).update({"assigned_rdp": new_type, "assigned_rdp_ip": portal.server_ip})
        db.query(RoutingGateway).filter(RoutingGateway.media1_vos_id == portal.id).update({"media1_name": new_type, "media1_ip": portal.server_ip})
        db.query(RoutingGateway).filter(RoutingGateway.media2_vos_id == portal.id).update({"media2_name": new_type, "media2_ip": portal.server_ip})
        db.query(DialerCluster).filter(DialerCluster.assigned_rdp == new_type).update({"assigned_rdp_ip": portal.server_ip})
        db.query(RoutingGateway).filter(RoutingGateway.media1_name == new_type).update({"media1_ip": portal.server_ip})
        db.query(RoutingGateway).filter(RoutingGateway.media2_name == new_type).update({"media2_ip": portal.server_ip})

    if new_type.upper().startswith("RTNG") or (old_type and old_type.upper().startswith("RTNG")):
        if old_type and old_type != new_type:
            db.query(RoutingGateway).filter(RoutingGateway.gateway_name == old_type).update({"gateway_name": new_type})
        db.query(RoutingGateway).filter(RoutingGateway.rtng_vos_id == portal.id).update({"gateway_name": new_type, "gateway_ip": portal.server_ip})
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
    gateway = get_portal_by_id(db, getattr(payload, "rtng_vos_id", None), "RTNG") or get_portal_by_type(db, payload.gateway_name, "RTNG")
    if not gateway:
        raise HTTPException(status_code=400, detail="Routing gateway must exist in VOS Portal Master with RTNG portal_type")
    payload.rtng_vos_id = gateway.id
    payload.gateway_name = gateway.portal_type
    payload.gateway_ip = gateway.server_ip

    for name_field, ip_field, id_field in [("media1_name", "media1_ip", "media1_vos_id"), ("media2_name", "media2_ip", "media2_vos_id")]:
        media_name = normalize(getattr(payload, name_field))
        rdp = get_portal_by_id(db, getattr(payload, id_field, None), "RDP") or get_portal_by_type(db, media_name, "RDP")
        setattr(payload, name_field, media_name)
        if not rdp and not media_name:
            setattr(payload, id_field, None)
            setattr(payload, ip_field, None)
            continue
        if not rdp:
            raise HTTPException(status_code=400, detail=f"{name_field} must be an RDP portal from VOS Portal Master")
        setattr(payload, id_field, rdp.id)
        setattr(payload, name_field, rdp.portal_type)
        setattr(payload, ip_field, rdp.server_ip)
    if payload.status == "Active":
        selected_ids = {value for value in [payload.media1_vos_id, payload.media2_vos_id] if value}
        for rdp_id in selected_ids:
            existing = db.query(RoutingGateway).filter(
                RoutingGateway.status == "Active",
                or_(RoutingGateway.media1_vos_id == rdp_id, RoutingGateway.media2_vos_id == rdp_id),
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
        "rtng_vos_id": mapping.rtng_vos_id if mapping else None,
        "media1_vos_id": mapping.media1_vos_id if mapping else None,
        "media1_name": mapping.live_media1_name if mapping else None,
        "media1_ip": mapping.live_media1_ip if mapping else None,
        "media2_vos_id": mapping.media2_vos_id if mapping else None,
        "media2_name": mapping.live_media2_name if mapping else None,
        "media2_ip": mapping.live_media2_ip if mapping else None,
        "carrier_ip": mapping.carrier_ip if mapping else None,
        "ports": mapping.ports if mapping else None,
        "vendor_name": mapping.vendor_name if mapping else None,
        "status": mapping.status if mapping else "Pending",
        "clients": ", ".join(client_names),
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
        for rdp_id, rdp_name in {(gateway.media1_vos_id, gateway.live_media1_name), (gateway.media2_vos_id, gateway.live_media2_name)}:
            key = rdp_id or normalize(rdp_name)
            if key:
                routing_usage.setdefault(key, {"rdp": rdp_name, "gateways": set()})["gateways"].add(gateway.live_gateway_name)
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
        if gateway.rtng_vos_id and gateway.rtng_vos_id not in rtng_portals:
            audit["orphan_assignment_records"].append({"type": "RoutingGateway", "id": gateway.id, "field": "rtng_vos_id", "value": gateway.rtng_vos_id})
        for field, portal in [("media1", media1), ("media2", media2)]:
            vos_id = getattr(gateway, f"{field}_vos_id")
            name = getattr(gateway, f"{field}_name")
            if vos_id and vos_id not in rdp_portals:
                issue = {"type": "RoutingGateway", "id": gateway.id, "field": f"{field}_vos_id", "value": vos_id}
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


@app.get("/api/vos-portals", response_model=list[VOSPortalOut])
@app.get("/vos-portals", response_model=list[VOSPortalOut])
def get_vos_portals(db: Session = Depends(get_db), user: User = Depends(require_page("vos_portals"))):
    return list_records(db, VOSPortal)


@app.post("/api/vos-portals", response_model=VOSPortalOut)
@app.post("/vos-portals", response_model=VOSPortalOut)
def create_vos_portal(payload: VOSPortalCreate, db: Session = Depends(get_db), user: User = Depends(require_page("vos_portals", "can_create"))):
    validate_vos_portal(db, payload)
    return save_record(db, VOSPortal(**payload.model_dump()))


@app.put("/api/vos-portals/{record_id}", response_model=VOSPortalOut)
@app.put("/vos-portals/{record_id}", response_model=VOSPortalOut)
def update_vos_portal(record_id: int, payload: VOSPortalUpdate, db: Session = Depends(get_db), user: User = Depends(require_page("vos_portals", "can_edit"))):
    validate_vos_portal(db, payload, record_id)
    record = get_record(db, VOSPortal, record_id)
    old_type = record.portal_type
    for key, value in payload.model_dump().items():
        setattr(record, key, value)
    sync_vos_references(db, old_type, record)
    return save_record(db, record)


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
def create_dialer_cluster(payload: DialerClusterCreate, db: Session = Depends(get_db), user: User = Depends(require_page("dialer_clusters", "can_create"))):
    payload = apply_cluster_assignment_rules(db, payload)
    return save_record(db, DialerCluster(**payload.model_dump()))


@app.put("/api/dialer-clusters/{record_id}", response_model=DialerClusterOut)
@app.put("/dialer-clusters/{record_id}", response_model=DialerClusterOut)
def update_dialer_cluster(record_id: int, payload: DialerClusterUpdate, db: Session = Depends(get_db), user: User = Depends(require_page("dialer_clusters", "can_edit"))):
    record = get_record(db, DialerCluster, record_id)
    payload = apply_cluster_assignment_rules(db, payload, record_id)
    for key, value in payload.model_dump().items():
        setattr(record, key, value)
    return save_record(db, record)


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
    for row in rows:
        sync_gateway_live_fields(row)
    return rows


@app.post("/api/routing-gateways", response_model=RoutingGatewayOut)
@app.post("/routing-gateways", response_model=RoutingGatewayOut)
def create_routing_gateway(payload: RoutingGatewayCreate, db: Session = Depends(get_db), user: User = Depends(require_page("routing_gateways", "can_create"))):
    payload = apply_gateway_rules(db, payload)
    return save_record(db, RoutingGateway(**payload.model_dump()))


@app.put("/api/routing-gateways/{record_id}", response_model=RoutingGatewayOut)
@app.put("/routing-gateways/{record_id}", response_model=RoutingGatewayOut)
def update_routing_gateway(record_id: int, payload: RoutingGatewayUpdate, db: Session = Depends(get_db), user: User = Depends(require_page("routing_gateways", "can_edit"))):
    record = get_record(db, RoutingGateway, record_id)
    payload = apply_gateway_rules(db, payload, record.id)
    for key, value in payload.model_dump().items():
        setattr(record, key, value)
    return save_record(db, record)


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
def create_client(payload: ClientCreate, db: Session = Depends(get_db), user: User = Depends(require_page("clients", "can_create"))):
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
    rights = {"can_view": 1, "can_create": 0, "can_edit": 0, "can_delete": 0, "can_export": 1}
    for page in ROLE_DEFAULT_PAGES["customer"]:
        db.add(PagePermission(user_id=customer.id, page_key=page, **rights))
    db.add(ClientAccess(user_id=customer.id, client_id=client.id))
    db.commit()
    db.refresh(client)
    return client_out(db, client)


@app.put("/clients/{record_id}", response_model=ClientOut)
@app.put("/api/clients/{record_id}", response_model=ClientOut)
def update_client(record_id: int, payload: ClientCreate, db: Session = Depends(get_db), user: User = Depends(require_page("clients", "can_edit"))):
    record = get_record(db, Client, record_id)
    payload.name = normalize(payload.name)
    if not payload.name:
        raise HTTPException(status_code=400, detail="Client name is required")
    record.name = payload.name
    record.status = payload.status
    record.notes = payload.notes
    return client_out(db, save_record(db, record))


@app.post("/clients/{record_id}/reset-password")
@app.post("/api/clients/{record_id}/reset-password")
def reset_client_password(record_id: int, payload: PasswordResetIn, db: Session = Depends(get_db), user: User = Depends(require_page("clients", "can_edit"))):
    get_record(db, Client, record_id)
    customer = db.query(User).filter(User.role == "customer", User.client_id == record_id).order_by(User.id.asc()).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Linked customer user not found")
    if not normalize(payload.password):
        raise HTTPException(status_code=400, detail="Password is required")
    customer.password_hash = hash_password(payload.password)
    save_record(db, customer)
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
def create_user(payload: UserCreate, db: Session = Depends(get_db), user: User = Depends(require_page("user_access", "can_create"))):
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
    return user_out(db, saved)


@app.put("/api/users/{record_id}", response_model=UserOut)
@app.put("/users/{record_id}", response_model=UserOut)
def update_user(record_id: int, payload: UserUpdate, db: Session = Depends(get_db), user: User = Depends(require_page("user_access", "can_edit"))):
    record = get_record(db, User, record_id)
    if payload.role not in {"admin", "noc_user", "customer", "viewer"}:
        raise HTTPException(status_code=400, detail="Invalid role")
    if payload.client_id and not db.get(Client, payload.client_id):
        raise HTTPException(status_code=400, detail="Client does not exist")
    for key, value in payload.model_dump().items():
        setattr(record, key, normalize(value) if key == "username" else value)
    saved = save_record(db, record)
    seed_user_access_defaults(db)
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
def reset_user_password(record_id: int, payload: PasswordResetIn, db: Session = Depends(get_db), user: User = Depends(require_page("user_access", "can_edit"))):
    record = get_record(db, User, record_id)
    if not normalize(payload.password):
        raise HTTPException(status_code=400, detail="Password is required")
    record.password_hash = hash_password(payload.password)
    return user_out(db, save_record(db, record))


@app.get("/api/users/{record_id}/permissions", response_model=list[PagePermissionOut])
@app.get("/users/{record_id}/permissions", response_model=list[PagePermissionOut])
def get_user_permissions(record_id: int, db: Session = Depends(get_db), user: User = Depends(require_page("user_access"))):
    get_record(db, User, record_id)
    return db.query(PagePermission).filter(PagePermission.user_id == record_id).order_by(PagePermission.page_key.asc()).all()


@app.post("/api/users/{record_id}/permissions", response_model=list[PagePermissionOut])
@app.post("/users/{record_id}/permissions", response_model=list[PagePermissionOut])
def save_user_permissions(record_id: int, payload: list[PagePermissionIn], db: Session = Depends(get_db), user: User = Depends(require_page("user_access", "can_edit"))):
    get_record(db, User, record_id)
    db.query(PagePermission).filter(PagePermission.user_id == record_id).delete()
    for item in payload:
        if item.page_key not in PAGE_KEYS:
            raise HTTPException(status_code=400, detail=f"Invalid page key: {item.page_key}")
        db.add(PagePermission(user_id=record_id, page_key=item.page_key, can_view=int(item.can_view), can_create=int(item.can_create), can_edit=int(item.can_edit), can_delete=int(item.can_delete), can_export=int(item.can_export)))
    db.commit()
    return get_user_permissions(record_id, db, user)


@app.get("/api/users/{record_id}/client-access")
@app.get("/users/{record_id}/client-access")
def get_user_client_access(record_id: int, db: Session = Depends(get_db), user: User = Depends(require_page("user_access"))):
    get_record(db, User, record_id)
    return {"client_ids": [row.client_id for row in db.query(ClientAccess).filter(ClientAccess.user_id == record_id).all()]}


@app.post("/api/users/{record_id}/client-access")
@app.post("/users/{record_id}/client-access")
def save_user_client_access(record_id: int, payload: ClientAccessIn, db: Session = Depends(get_db), user: User = Depends(require_page("user_access", "can_edit"))):
    record = get_record(db, User, record_id)
    valid_ids = {client.id for client in db.query(Client).all()}
    if any(client_id not in valid_ids for client_id in payload.client_ids):
        raise HTTPException(status_code=400, detail="Invalid client id")
    db.query(ClientAccess).filter(ClientAccess.user_id == record_id).delete()
    for client_id in payload.client_ids:
        db.add(ClientAccess(user_id=record_id, client_id=client_id))
    if record.role == "customer" and payload.client_ids:
        record.client_id = payload.client_ids[0]
    db.commit()
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
def create_ledger(payload: ClientLedgerCreate, db: Session = Depends(get_db), user: User = Depends(require_page("billing", "can_create"))):
    data = ledger_payload_values(db, payload, user)
    record = ClientLedger(**data)
    db.add(record)
    db.flush()
    recalc_client_ledger(db, payload.client_id)
    db.commit()
    db.refresh(record)
    logger.info("Ledger entry saved id=%s client_id=%s user=%s", record.id, record.client_id, user.username)
    return {"success": True, "entry": record}


@app.put("/api/ledger/{record_id}", response_model=ClientLedgerMutationOut)
@app.put("/ledger/{record_id}", response_model=ClientLedgerMutationOut)
@app.put("/api/billing/ledger/{record_id}", response_model=ClientLedgerMutationOut)
@app.put("/billing/ledger/{record_id}", response_model=ClientLedgerMutationOut)
def update_ledger(record_id: int, payload: ClientLedgerCreate, db: Session = Depends(get_db), user: User = Depends(require_page("billing", "can_edit"))):
    record = get_record(db, ClientLedger, record_id)
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
    return {"success": True, "entry": record}


@app.delete("/api/ledger/{record_id}")
@app.delete("/ledger/{record_id}")
@app.delete("/api/billing/ledger/{record_id}")
@app.delete("/billing/ledger/{record_id}")
def delete_ledger(record_id: int, db: Session = Depends(get_db), user: User = Depends(require_page("billing", "can_delete"))):
    record = get_record(db, ClientLedger, record_id)
    client_id = record.client_id
    db.delete(record)
    db.flush()
    recalc_client_ledger(db, client_id)
    db.commit()
    logger.info("Ledger entry deleted id=%s client_id=%s user=%s", record_id, client_id, user.username)
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
def save_cluster_assignment(payload: ClusterAccountAssignmentIn, db: Session = Depends(get_db), user: User = Depends(require_page("management_portal", "can_edit"))):
    cluster = get_record(db, DialerCluster, payload.cluster_id)
    if payload.client_id is not None and not db.get(Client, payload.client_id):
        raise HTTPException(status_code=400, detail="Client does not exist")
    cluster.client_id = payload.client_id
    return cluster_assignment_out(save_record(db, cluster))


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
def save_rdp_cluster_assignment(payload: RDPClusterAssignmentIn, db: Session = Depends(get_db), user: User = Depends(require_page("management_portal", "can_edit"))):
    cluster = get_record(db, DialerCluster, payload.cluster_id)
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
    duplicate_names = active_rdp_duplicate_names(db.query(DialerCluster).all())
    return rdp_cluster_assignment_out(saved, duplicate_names)


@app.get("/api/management/routing-media-assignments")
@app.get("/management/routing-media-assignments")
def get_routing_media_assignments(db: Session = Depends(get_db), user: User = Depends(require_page("management_portal"))):
    mappings = {mapping.gateway_name: mapping for mapping in db.query(RoutingGateway).all()}
    mappings_by_id = {mapping.rtng_vos_id: mapping for mapping in mappings.values() if mapping.rtng_vos_id}
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
def save_routing_media_assignment(payload: RoutingMediaAssignmentIn, db: Session = Depends(get_db), user: User = Depends(require_page("management_portal", "can_edit"))):
    gateway = get_portal_by_type(db, payload.gateway_name, "RTNG")
    if not gateway:
        raise HTTPException(status_code=400, detail="Routing gateway must exist in VOS Portal Master")

    data = RoutingGatewayUpdate(
        gateway_name=payload.gateway_name,
        gateway_ip=gateway.server_ip,
        rtng_vos_id=payload.rtng_vos_id or gateway.id,
        media1_name=payload.media1_name,
        media1_ip=None,
        media1_vos_id=payload.media1_vos_id,
        media2_name=payload.media2_name,
        media2_ip=None,
        media2_vos_id=payload.media2_vos_id,
        carrier_ip=payload.carrier_ip,
        ports=payload.ports,
        vendor_name=payload.vendor_name,
        status=payload.status,
    )
    record = db.query(RoutingGateway).filter(RoutingGateway.rtng_vos_id == data.rtng_vos_id).first()
    if not record:
        record = db.query(RoutingGateway).filter(RoutingGateway.gateway_name == data.gateway_name).first()
    data = apply_gateway_rules(db, data, record.id if record else None)
    if not record:
        record = RoutingGateway(**data.model_dump())
    else:
        for key, value in data.model_dump().items():
            setattr(record, key, value)
    saved = save_record(db, record)
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
