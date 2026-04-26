import argparse
import hashlib
import secrets
import uuid
from datetime import date, datetime, timedelta

from database import Base, SessionLocal, engine
from models import BillingSetting, CDR, Client, ClientAccess, ClientLedger, DataCost, DialerCluster, PagePermission, RoutingGateway, User, VOSPortal


USD_TO_INR = 83.0
PAGE_KEYS = [
    "dashboard", "my_dashboard", "business_ai", "reports", "my_reports", "management_portal",
    "billing", "my_ledger", "clients", "cdr", "my_cdr", "vos_portals", "dialer_clusters",
    "rdp_media", "routing_gateways", "vos_desktop_launcher", "user_access", "activity_logs",
    "chat_center", "my_chat", "group_chat", "tickets", "my_tickets", "webphone",
]
ROLE_DEFAULT_PAGES = {
    "admin": PAGE_KEYS,
    "noc_user": ["dashboard", "management_portal", "billing", "reports", "vos_portals", "vos_desktop_launcher", "dialer_clusters", "rdp_media", "routing_gateways", "chat_center", "group_chat", "tickets", "webphone"],
    "viewer": ["dashboard", "reports"],
    "customer": ["my_dashboard", "my_ledger", "my_cdr", "my_reports", "my_chat", "my_tickets"],
}


CLIENTS = [
    "IM1",
    "IM2",
    "IM3",
    "ROLEX",
    "Apex Telecom",
    "BlueWave Connect",
]

RDP_PORTALS = {
    "RDP02": "75.127.1.194",
    "RDP12": "107.175.157.66",
    "RDP13": "107.175.155.130",
    "RDP14": "107.175.144.130",
    "RDP15": "23.95.185.194",
    "RDP17": "107.173.67.130",
}

RTNG_PORTALS = {
    "RTNG01": "178.156.191.188",
    "RTNG02": "192.3.187.130",
    "RTNG03": "198.23.159.170",
    "RTNG04": "192.227.159.34",
    "RTNG05": "192.227.159.90",
    "RTNG06": "198.23.159.200",
}

DID_PORTALS = {
    "DID Portal": "5.161.86.173",
    "DID Portal B": "198.23.253.90",
}

CLUSTER_NAMES = {
    1: "Alfa",
    2: "Bravo",
    3: "Delta",
    4: "Echo",
    5: "Omega",
    6: "Nova",
    7: "Zen",
    8: "Max",
    9: "Prime",
    10: "Core",
    11: "Lava",
    12: "Gama",
    13: "Zeta",
    14: "Meta",
    15: "Sota",
}

CLUSTER_CLIENTS = {
    1: "Apex Telecom",
    2: "IM1",
    3: "IM2",
    4: "IM3",
    5: "ROLEX",
    6: "BlueWave Connect",
    7: "Apex Telecom",
    8: "IM1",
    9: "IM2",
    10: "IM3",
    11: "ROLEX",
    12: "BlueWave Connect",
    13: "Apex Telecom",
    14: "IM1",
    15: "IM2",
}

CLUSTER_RDPS = {
    1: "RDP02",
    2: "RDP12",
    3: "RDP13",
    4: "RDP14",
    5: "RDP15",
    6: "RDP17",
}

ROUTING_MAPPINGS = {
    "RTNG01": ("IM1", "RDP12", None, "5.78.115.169", "2000", "Mueen", "Active"),
    "RTNG02": ("IM2", "RDP13", None, "5.78.115.169", "1000", "Mueen", "Active"),
    "RTNG03": ("IM3", "RDP14", "RDP17", "5.161.243.196", "2000", "Mueen", "Active"),
    "RTNG04": ("ROLEX", "RDP15", "RDP02", "5.78.45.192", "2000", "Mueen", "Active"),
    "RTNG05": (None, None, None, "207.246.87.247", "", "John", "Pending"),
    "RTNG06": (None, None, None, "", "", "Pending Vendor", "Pending"),
}


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def ledger_entry(client_id, entry_date, entry_type, category, description, amount_usd, balance_usd, created_by="seed"):
    debit_usd = round(amount_usd, 2) if entry_type == "Debit" else 0
    credit_usd = round(amount_usd, 2) if entry_type == "Credit" else 0
    return ClientLedger(
        client_id=client_id,
        entry_date=entry_date,
        entry_type=entry_type,
        category=category,
        description=description,
        amount_usd=round(amount_usd, 2),
        exchange_rate=USD_TO_INR,
        amount_inr=round(amount_usd * USD_TO_INR, 2),
        debit_amount=debit_usd,
        credit_amount=credit_usd,
        balance_after_entry=round(balance_usd, 2),
        debit_usd=debit_usd,
        credit_usd=credit_usd,
        debit_inr=round(debit_usd * USD_TO_INR, 2),
        credit_inr=round(credit_usd * USD_TO_INR, 2),
        balance_usd=round(balance_usd, 2),
        balance_inr=round(balance_usd * USD_TO_INR, 2),
        created_by=created_by,
    )


def create_clients(db):
    clients = {}
    for name in CLIENTS:
        client = Client(name=name, status="Active", notes=f"{name} telecom billing customer")
        db.add(client)
        clients[name] = client
    db.flush()
    return clients


def create_users(db, clients):
    users = [
        ("admin", "admin123", "admin", None, "System Admin", "admin@noc360.local"),
        ("noc", "noc123", "noc_user", None, "NOC Operator", "noc@noc360.local"),
        ("viewer", "viewer123", "viewer", None, "Read Only Viewer", "viewer@noc360.local"),
        ("im1", "123", "customer", "IM1", "IM1 Customer", "billing@im1.example"),
        ("im2", "123", "customer", "IM2", "IM2 Customer", "billing@im2.example"),
        ("rolex", "123", "customer", "ROLEX", "ROLEX Customer", "billing@rolex.example"),
    ]
    saved_users = {}
    for username, password, role, client_name, full_name, email in users:
        client = clients.get(client_name) if client_name else None
        user = User(username=username, password_hash=hash_password(password), role=role, client_id=client.id if client else None, status="Active", full_name=full_name, email=email)
        db.add(user)
        saved_users[username] = user
    db.flush()
    for user in saved_users.values():
        pages = ROLE_DEFAULT_PAGES[user.role]
        readonly = user.role in {"viewer", "customer"}
        rights = {"can_view": 1, "can_create": 0 if readonly else 1, "can_edit": 0 if readonly else 1, "can_delete": 1 if user.role == "admin" else 0, "can_export": 1}
        for page in pages:
            page_rights = rights
            if user.role == "noc_user" and page == "vos_desktop_launcher":
                page_rights = {"can_view": 1, "can_create": 0, "can_edit": 0, "can_delete": 0, "can_export": 1}
            if user.role == "customer" and page in {"my_chat", "my_tickets"}:
                page_rights = {"can_view": 1, "can_create": 1, "can_edit": 0, "can_delete": 0, "can_export": 0}
            db.add(PagePermission(user_id=user.id, page_key=page, **page_rights))
        if user.client_id:
            db.add(ClientAccess(user_id=user.id, client_id=user.client_id))


def create_vos_portals(db):
    rdp_portals = {}
    rtng_portals = {}
    def portal_url(ip):
        return f"http://{ip}:8989/anti-atck"

    for name, ip in RDP_PORTALS.items():
        portal = VOSPortal(
            vos_version="V2.1.8.05",
            portal_type=name,
            server_ip=ip,
            status="Active",
            username="admin",
            password="demo only",
            anti_hack_url=portal_url(ip),
            anti_hack_password="Marks@5971",
            uuid=str(uuid.uuid4()),
            cdr_panel_url=f"http://{ip}/cdr",
            web_panel_url=f"http://{ip}/",
            notes="Media/RDP server from master inventory",
            vos_port=80,
            vos_desktop_enabled=True,
            vos_notes="VOS Desktop launcher enabled",
        )
        db.add(portal)
        rdp_portals[name] = portal
    for name, ip in RTNG_PORTALS.items():
        portal = VOSPortal(
            vos_version="V2.1.8.05",
            portal_type=name,
            server_ip=ip,
            status="Pending" if name == "RTNG05" else "Active",
            username="admin",
            password="demo only",
            anti_hack_url=portal_url(ip),
            anti_hack_password="Marks@5971",
            uuid=str(uuid.uuid4()),
            cdr_panel_url=f"http://{ip}/cdr",
            web_panel_url=f"http://{ip}/",
            notes="Routing gateway from master inventory",
        )
        db.add(portal)
        rtng_portals[name] = portal
    for name, ip in DID_PORTALS.items():
        db.add(VOSPortal(vos_version="V2.1.8.05", portal_type=name, server_ip=ip, status="Active", username="admin", password="demo only", anti_hack_url=portal_url(ip), anti_hack_password="Marks@5971", uuid=str(uuid.uuid4()), cdr_panel_url=f"http://{ip}/cdr", web_panel_url=f"http://{ip}/"))
    db.flush()
    return rdp_portals, rtng_portals


def create_clusters(db, clients, rdp_portals):
    clusters = {}
    for number in range(1, 16):
        rdp_name = CLUSTER_RDPS.get(number)
        rdp = rdp_portals.get(rdp_name) if rdp_name else None
        cluster = DialerCluster(
            cluster_no=number,
            account_name=CLUSTER_NAMES[number],
            db_ip=f"172.16.{number}.10",
            web_ips=f"172.16.{number}.20, 172.16.{number}.21",
            asterisk_ips=f"172.16.{number}.30, 172.16.{number}.31",
            inbound_ip=f"172.16.{number}.40",
            client_id=clients[CLUSTER_CLIENTS[number]].id,
            dids_patch=f"DID-PATCH-{number:02d}",
            in_id=f"IN-{1000 + number}",
            assigned_rdp=rdp.portal_type if rdp else None,
            assigned_rdp_ip=rdp.server_ip if rdp else None,
            rdp_vos_id=rdp.id if rdp else None,
            status="Active" if number <= 10 else "Pending",
        )
        db.add(cluster)
        clusters[number] = cluster
    db.flush()
    return clusters


def create_routing(db, clients, rdp_portals, rtng_portals):
    for gateway_name, (client_name, media1_name, media2_name, carrier_ip, ports, vendor, status) in ROUTING_MAPPINGS.items():
        gateway = rtng_portals[gateway_name]
        media1 = rdp_portals.get(media1_name) if media1_name else None
        media2 = rdp_portals.get(media2_name) if media2_name else None
        db.add(
            RoutingGateway(
                gateway_name=gateway.portal_type,
                gateway_ip=gateway.server_ip,
                rtng_vos_id=gateway.id,
                client_id=clients[client_name].id if client_name else None,
                media1_name=media1.portal_type if media1 else None,
                media1_ip=media1.server_ip if media1 else None,
                media1_vos_id=media1.id if media1 else None,
                media2_name=media2.portal_type if media2 else None,
                media2_ip=media2.server_ip if media2 else None,
                media2_vos_id=media2.id if media2 else None,
                carrier_ip=carrier_ip,
                ports=ports,
                vendor_name=vendor,
                status=status,
            )
        )


def create_ledger(db, clients):
    today = date.today()
    daily_profiles = {
        "IM1": (128, 24, 12),
        "IM2": (154, 31, 16),
        "IM3": (142, 27, 14),
        "ROLEX": (238, 68, 34),
        "Apex Telecom": (205, 52, 24),
        "BlueWave Connect": (188, 46, 22),
    }
    payments = {
        "IM1": 260,
        "IM2": 310,
        "IM3": 240,
        "ROLEX": 220,
        "Apex Telecom": 450,
        "BlueWave Connect": 390,
    }
    for client_index, name in enumerate(CLIENTS):
        client = clients[name]
        usage_base, data_base, did_base = daily_profiles[name]
        balance = 0
        for offset in range(14, -1, -1):
            day = today - timedelta(days=offset)
            usage = round(min(280, usage_base + ((14 - offset) % 5) * 11 + client_index * 3), 2)
            data_charge = round(min(75, data_base + ((14 - offset) % 4) * 4.5), 2)
            did_charge = round(min(35, did_base + ((14 - offset) % 3) * 2.5), 2)
            for category, amount in [
                ("Usage Charges", usage),
                ("Data Charges", data_charge),
                ("DID Charges", did_charge),
            ]:
                balance += amount
                db.add(ledger_entry(client.id, day, "Debit", category, f"{category} for {day.isoformat()}", amount, balance))
            if offset in {12, 8, 4, 1}:
                payment = round(min(500, payments[name] + ((14 - offset) % 3) * 35), 2)
                balance -= payment
                db.add(ledger_entry(client.id, day, "Credit", "Payment", f"Customer payment received {day.isoformat()}", payment, balance))


def create_data_costs(db, clients):
    today = date.today()
    for client_index, name in enumerate(CLIENTS):
        client = clients[name]
        for offset in range(14, -1, -1):
            day = today - timedelta(days=offset)
            quantity = round(12 + client_index * 5 + (14 - offset) * 1.7, 2)
            rate = round(0.52 + client_index * 0.055 + (0.015 if offset < 5 else 0), 4)
            db.add(
                DataCost(
                    client_id=client.id,
                    entry_date=day,
                    quantity=quantity,
                    rate=rate,
                    rate_usd=rate,
                    total_cost=round(quantity * rate, 2),
                    total_cost_usd=round(quantity * rate, 2),
                    exchange_rate=USD_TO_INR,
                    total_cost_inr=round(quantity * rate * USD_TO_INR, 2),
                    description=f"Daily bandwidth cost {day.isoformat()}",
                )
            )


def create_cdr(db, clients):
    dispositions = ["ANSWERED", "NO ANSWER", "BUSY"]
    routes = ["INTL-A", "INTL-B"]
    gateways = ["RTNG01", "RTNG02", "RTNG03", "RTNG04"]
    client_list = [clients[name] for name in CLIENTS]
    for index in range(100):
        client = client_list[index % len(client_list)]
        disposition = dispositions[index % len(dispositions)]
        duration = 0 if disposition != "ANSWERED" else 35 + (index * 17) % 266
        db.add(CDR(client_id=client.id, cluster_id=None, call_date=datetime.utcnow() - timedelta(hours=index * 2), caller_id=f"91{9000000000 + index}", destination=f"1{7000000000 + index}", duration=duration, disposition=disposition, cost=round(0.01 + (index % 20) * 0.01, 4), route=routes[index % 2], gateway=gateways[index % 4], cdr_source="seed"))


def seed_database(clear=True, db=None):
    owns_session = db is None
    if clear:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = db or SessionLocal()
    try:
        if not clear and db.query(Client).first():
            return {"seeded": False, "reason": "database already has clients"}
        clients = create_clients(db)
        create_users(db, clients)
        db.add(BillingSetting(id=1, usd_to_inr_rate=USD_TO_INR))
        rdp_portals, rtng_portals = create_vos_portals(db)
        create_clusters(db, clients, rdp_portals)
        create_routing(db, clients, rdp_portals, rtng_portals)
        create_ledger(db, clients)
        create_data_costs(db, clients)
        create_cdr(db, clients)
        db.commit()
        return {
            "seeded": True,
            "clients": len(CLIENTS),
            "rdp_portals": len(RDP_PORTALS),
            "routing_gateways": len(RTNG_PORTALS),
            "clusters": 15,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        if owns_session:
            db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed NOC360 demo data")
    parser.add_argument("--reset", action="store_true", help="Drop and rebuild the database before seeding")
    args = parser.parse_args()
    result = seed_database(clear=args.reset)
    print(f"NOC360 seed complete: {result}")
