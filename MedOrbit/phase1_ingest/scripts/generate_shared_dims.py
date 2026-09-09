"""
Generate MedOrbit shared dimension CSVs (run once to seed; re-run only for SCD2 demos).
Writes locally and optionally uploads to ADLS medorbit-landing/shared-dims/
"""
from __future__ import annotations

import os
import random
from datetime import date, timedelta
from pathlib import Path

from medorbit_common import (
    CITIES,
    DRUG_CATALOG,
    SHARED_DIMS_DIR,
    ensure_dir,
    season_for_month,
    upload_csv_file,
    write_csv,
)

random.seed(int(os.getenv("MEDORBIT_SEED", "42")))


def build_dim_date(start: date, end: date):
    rows = []
    d = start
    while d <= end:
        rows.append(
            {
                "date_key": int(d.strftime("%Y%m%d")),
                "full_date": d.isoformat(),
                "year": d.year,
                "month": d.month,
                "day": d.day,
                "quarter": (d.month - 1) // 3 + 1,
                "month_name": d.strftime("%B"),
                "week_of_year": int(d.strftime("%U")),
                "is_weekend": str(d.weekday() >= 5).lower(),
                "season": season_for_month(d.month),
            }
        )
        d += timedelta(days=1)
    return rows


def build_suppliers(n: int = 12):
    rows = []
    for i in range(1, n + 1):
        rows.append(
            {
                "supplier_id": f"SUP_{i:04d}",
                "supplier_name": f"{random.choice(['Auro', 'Cipla', 'Sun', 'DrReddy', 'Lupin', 'Biocon', 'Torrent', 'Alkem'])} Supply {i}",
                "country": "India",
                "city": random.choice(CITIES)[1],
                "contact_email": f"supplier{i}@medorbit.example",
                "status": "Active",
                "effective_start": "2024-01-01",
                "effective_end": "",
                "is_current": "true",
            }
        )
    return rows


def build_facilities():
    rows = []
    # 4 manufacturers, 6 warehouses, 10 hospitals, 12 pharmacies
    specs = [
        ("MANUFACTURER", "MFG", 4),
        ("WAREHOUSE", "WHS", 6),
        ("HOSPITAL", "HSP", 10),
        ("PHARMACY", "PHM", 12),
    ]
    for ftype, prefix, count in specs:
        for i in range(1, count + 1):
            code, city, state, region = CITIES[(i - 1) % len(CITIES)]
            fid = f"{prefix}_{code}_{i:02d}"
            name = {
                "MANUFACTURER": f"MedOrbit Plant {city} {i}",
                "WAREHOUSE": f"MedOrbit DC {city} {i}",
                "HOSPITAL": f"MedOrbit Hospital {city} {i}",
                "PHARMACY": f"MedOrbit Pharmacy {city} {i}",
            }[ftype]
            rows.append(
                {
                    "facility_id": fid,
                    "facility_name": name,
                    "facility_type": ftype,
                    "city": city,
                    "state": state,
                    "region": region,
                    "bed_count": str(random.randint(100, 800)) if ftype == "HOSPITAL" else "",
                    "status": "Active",
                    "effective_start": "2024-01-01",
                    "effective_end": "",
                    "is_current": "true",
                }
            )
    return rows


def build_drugs(n: int = 80):
    rows = []
    for i in range(1, n + 1):
        base = DRUG_CATALOG[(i - 1) % len(DRUG_CATALOG)]
        name, generic, form, strength, tclass, price = base
        # slight variants for volume
        suffix = "" if i <= len(DRUG_CATALOG) else f" V{(i - 1) // len(DRUG_CATALOG)}"
        rows.append(
            {
                "drug_id": f"DRUG_{i:04d}",
                "drug_name": f"{name}{suffix}",
                "generic_name": generic,
                "form": form,
                "strength": strength,
                "therapeutic_class": tclass,
                "unit_price_inr": f"{price + (i % 7) * 1.5:.2f}",
                "status": "Active",
                "effective_start": "2024-01-01",
                "effective_end": "",
                "is_current": "true",
            }
        )
    return rows


def build_batches(drugs, manufacturers, suppliers, n: int = 400):
    rows = []
    start = date(2024, 6, 1)
    for i in range(1, n + 1):
        drug = random.choice(drugs)
        plant = random.choice(manufacturers)
        supplier = random.choice(suppliers)
        mfg = start + timedelta(days=random.randint(0, 400))
        exp = mfg + timedelta(days=random.choice([180, 365, 540, 720]))
        rows.append(
            {
                "batch_id": f"BATCH_{i:08d}",
                "drug_id": drug["drug_id"],
                "manufacturer_facility_id": plant["facility_id"],
                "supplier_id": supplier["supplier_id"],
                "mfg_date": mfg.isoformat(),
                "expiry_date": exp.isoformat(),
                "status": "Released",
            }
        )
    return rows


def build_warehouse_serves(warehouses, hospitals, pharmacies):
    rows = []
    served = hospitals + pharmacies
    for wh in warehouses:
        # each warehouse serves 3-5 facilities
        picks = random.sample(served, k=min(len(served), random.randint(3, 5)))
        for j, fac in enumerate(picks):
            rows.append(
                {
                    "warehouse_id": wh["facility_id"],
                    "served_facility_id": fac["facility_id"],
                    "is_primary": str(j == 0).lower(),
                    "effective_start": "2024-01-01",
                }
            )
    return rows


def main():
    ensure_dir(SHARED_DIMS_DIR)
    suppliers = build_suppliers()
    facilities = build_facilities()
    drugs = build_drugs(int(os.getenv("MEDORBIT_NUM_DRUGS", "80")))
    manufacturers = [f for f in facilities if f["facility_type"] == "MANUFACTURER"]
    warehouses = [f for f in facilities if f["facility_type"] == "WAREHOUSE"]
    hospitals = [f for f in facilities if f["facility_type"] == "HOSPITAL"]
    pharmacies = [f for f in facilities if f["facility_type"] == "PHARMACY"]
    batches = build_batches(drugs, manufacturers, suppliers, int(os.getenv("MEDORBIT_NUM_BATCHES", "400")))
    serves = build_warehouse_serves(warehouses, hospitals, pharmacies)
    dates = build_dim_date(date(2024, 1, 1), date(2026, 12, 31))

    files = {
        "dim_date.csv": (dates, None),
        "dim_supplier.csv": (suppliers, None),
        "dim_facility.csv": (facilities, None),
        "dim_drug.csv": (drugs, None),
        "dim_batch.csv": (batches, None),
        "bridge_warehouse_serves.csv": (serves, None),
    }

    uploaded = []
    for name, (rows, _) in files.items():
        local = write_csv(SHARED_DIMS_DIR / name, rows)
        adls_path = f"shared-dims/{name}"
        uri = upload_csv_file(local, adls_path)
        uploaded.append({"local": str(local), "adls": uri, "rows": len(rows)})

    print("SHARED DIMS GENERATED")
    for u in uploaded:
        print(u)


if __name__ == "__main__":
    main()
