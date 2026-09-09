"""MedOrbit Phase-1 shared helpers for simulation scripts."""
from __future__ import annotations

import csv
import io
import json
import os
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from faker import Faker

fake = Faker()
Faker.seed(42)

# Defaults (override with env)
DEFAULT_SEED = int(os.getenv("MEDORBIT_SEED", "42"))
OUTPUT_ROOT = Path(os.getenv("MEDORBIT_OUTPUT_ROOT", str(Path(__file__).resolve().parent / "output")))
SHARED_DIMS_DIR = Path(os.getenv("MEDORBIT_SHARED_DIMS_DIR", str(OUTPUT_ROOT / "shared-dims")))

DRUG_CATALOG = [
    ("Paracetamol", "Acetaminophen", "tablet", "650mg", "Analgesic", 12.0),
    ("Amoxicillin", "Amoxicillin", "capsule", "500mg", "Antibiotic", 28.0),
    ("Atorvastatin", "Atorvastatin", "tablet", "20mg", "Cardio", 45.0),
    ("Metformin", "Metformin", "tablet", "500mg", "Diabetes", 18.0),
    ("Omeprazole", "Omeprazole", "capsule", "20mg", "GI", 22.0),
    ("Amlodipine", "Amlodipine", "tablet", "5mg", "Cardio", 16.0),
    ("Cetirizine", "Cetirizine", "tablet", "10mg", "Antihistamine", 8.0),
    ("Azithromycin", "Azithromycin", "tablet", "500mg", "Antibiotic", 55.0),
    ("Pantoprazole", "Pantoprazole", "tablet", "40mg", "GI", 24.0),
    ("Losartan", "Losartan", "tablet", "50mg", "Cardio", 30.0),
    ("Ibuprofen", "Ibuprofen", "tablet", "400mg", "Analgesic", 14.0),
    ("Ciprofloxacin", "Ciprofloxacin", "tablet", "500mg", "Antibiotic", 40.0),
    ("Salbutamol", "Salbutamol", "inhaler", "100mcg", "Respiratory", 120.0),
    ("Insulin Glargine", "Insulin Glargine", "injection", "100IU/ml", "Diabetes", 650.0),
    ("Ondansetron", "Ondansetron", "tablet", "4mg", "Anti-emetic", 35.0),
    ("Doxycycline", "Doxycycline", "capsule", "100mg", "Antibiotic", 32.0),
    ("Telmisartan", "Telmisartan", "tablet", "40mg", "Cardio", 38.0),
    ("Montelukast", "Montelukast", "tablet", "10mg", "Respiratory", 42.0),
    ("Clopidogrel", "Clopidogrel", "tablet", "75mg", "Cardio", 48.0),
    ("Levothyroxine", "Levothyroxine", "tablet", "50mcg", "Endocrine", 20.0),
]

CITIES = [
    ("HYD", "Hyderabad", "Telangana", "South"),
    ("BLR", "Bengaluru", "Karnataka", "South"),
    ("CHN", "Chennai", "Tamil Nadu", "South"),
    ("MUM", "Mumbai", "Maharashtra", "West"),
    ("PUN", "Pune", "Maharashtra", "West"),
    ("DEL", "New Delhi", "Delhi", "North"),
    ("JAI", "Jaipur", "Rajasthan", "North"),
    ("KOL", "Kolkata", "West Bengal", "East"),
    ("BHU", "Bhubaneswar", "Odisha", "East"),
    ("NAG", "Nagpur", "Maharashtra", "Central"),
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(ts: datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12].upper()}"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: Optional[List[str]] = None) -> Path:
    ensure_dir(path.parent)
    if not rows:
        raise ValueError(f"No rows to write for {path}")
    cols = fieldnames or list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return path


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def season_for_month(month: int) -> str:
    if month in (12, 1, 2):
        return "Winter"
    if month in (3, 4):
        return "Spring"
    if month in (5, 6):
        return "Summer"
    if month in (7, 8, 9):
        return "Monsoon"
    return "Autumn"


def get_adls_clients():
    """Return (file_system_client, filesystem_name) or (None, None) if not configured."""
    conn = os.getenv("MEDORBIT_STORAGE_CONNECTION_STRING", "").strip()
    account = os.getenv("MEDORBIT_STORAGE_ACCOUNT", "").strip()
    key = os.getenv("MEDORBIT_STORAGE_KEY", "").strip()
    filesystem = os.getenv("MEDORBIT_LANDING_FILESYSTEM", "medorbit-landing")
    if not conn and not (account and key):
        return None, filesystem
    try:
        from azure.storage.filedatalake import DataLakeServiceClient
    except ImportError as e:
        raise RuntimeError("Install azure-storage-file-datalake to upload to ADLS") from e
    if conn:
        svc = DataLakeServiceClient.from_connection_string(conn)
    else:
        svc = DataLakeServiceClient(
            account_url=f"https://{account}.dfs.core.windows.net",
            credential=key,
        )
    return svc.get_file_system_client(filesystem), filesystem


def upload_bytes_to_adls(relative_path: str, data: bytes, overwrite: bool = True) -> str:
    fs, filesystem = get_adls_clients()
    if fs is None:
        return f"(local-only) {relative_path}"
    # relative_path like manufacturer/run_id/file.csv
    parts = relative_path.replace("\\", "/").strip("/").split("/")
    directory = "/".join(parts[:-1]) if len(parts) > 1 else ""
    file_name = parts[-1]
    if directory:
        try:
            fs.create_directory(directory)
        except Exception:
            pass
        dir_client = fs.get_directory_client(directory)
        file_client = dir_client.get_file_client(file_name)
    else:
        file_client = fs.get_file_client(file_name)
    file_client.upload_data(data, overwrite=overwrite)
    return f"abfs://{filesystem}/{relative_path}"


def upload_csv_file(local_path: Path, adls_relative_path: str) -> str:
    return upload_bytes_to_adls(adls_relative_path, local_path.read_bytes())


def upload_csv_rows(adls_relative_path: str, rows: List[Dict[str, Any]], fieldnames: List[str]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    return upload_bytes_to_adls(adls_relative_path, buf.getvalue().encode("utf-8"))


def get_event_hub_producer(kind: str):
    """kind: hospital | pharmacy"""
    try:
        from azure.eventhub import EventHubProducerClient
    except ImportError as e:
        raise RuntimeError("Install azure-eventhub to publish events") from e

    if kind == "hospital":
        conn = os.getenv("MEDORBIT_EH_HOSPITAL_CONNECTION", "").strip()
        hub = os.getenv("MEDORBIT_EH_HOSPITAL_NAME", "medorbit-hospital-events")
    elif kind == "pharmacy":
        conn = os.getenv("MEDORBIT_EH_PHARMACY_CONNECTION", "").strip()
        hub = os.getenv("MEDORBIT_EH_PHARMACY_NAME", "medorbit-pharmacy-events")
    else:
        raise ValueError(kind)

    if not conn:
        return None, hub
    # Connection string may already include EntityPath; if not, pass eventhub_name
    if "EntityPath=" in conn:
        producer = EventHubProducerClient.from_connection_string(conn)
    else:
        producer = EventHubProducerClient.from_connection_string(conn, eventhub_name=hub)
    return producer, hub


def publish_json_events(kind: str, events: Iterable[Dict[str, Any]], batch_size: int = 100) -> Dict[str, Any]:
    from azure.eventhub import EventData

    producer, hub = get_event_hub_producer(kind)
    events_list = list(events)
    if producer is None:
        # Local fallback: write JSONL
        out = ensure_dir(OUTPUT_ROOT / "eventhub_fallback" / kind)
        path = out / f"{kind}_{utc_now().strftime('%Y%m%dT%H%M%SZ')}.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for e in events_list:
                f.write(json.dumps(e) + "\n")
        return {"mode": "local_jsonl", "hub": hub, "count": len(events_list), "path": str(path)}

    with producer:
        batch = producer.create_batch()
        for e in events_list:
            payload = EventData(json.dumps(e))
            try:
                batch.add(payload)
            except ValueError:
                producer.send_batch(batch)
                batch = producer.create_batch()
                batch.add(payload)
            if len(batch) >= batch_size:
                producer.send_batch(batch)
                batch = producer.create_batch()
        if len(batch) > 0:
            producer.send_batch(batch)
    return {"mode": "eventhub", "hub": hub, "count": len(events_list)}


def load_shared_dims() -> Dict[str, List[Dict[str, str]]]:
    required = [
        "dim_facility.csv",
        "dim_drug.csv",
        "dim_supplier.csv",
        "dim_batch.csv",
        "bridge_warehouse_serves.csv",
    ]
    missing = [n for n in required if not (SHARED_DIMS_DIR / n).exists()]
    if missing:
        raise FileNotFoundError(
            f"Shared dims not found in {SHARED_DIMS_DIR}. Missing: {missing}. "
            "Run generate_shared_dims.py first."
        )
    return {
        "facility": read_csv(SHARED_DIMS_DIR / "dim_facility.csv"),
        "drug": read_csv(SHARED_DIMS_DIR / "dim_drug.csv"),
        "supplier": read_csv(SHARED_DIMS_DIR / "dim_supplier.csv"),
        "batch": read_csv(SHARED_DIMS_DIR / "dim_batch.csv"),
        "serves": read_csv(SHARED_DIMS_DIR / "bridge_warehouse_serves.csv"),
    }


def facilities_by_type(dims: Dict[str, List[Dict[str, str]]], ftype: str) -> List[Dict[str, str]]:
    return [f for f in dims["facility"] if f["facility_type"] == ftype and f.get("is_current", "true").lower() == "true"]
