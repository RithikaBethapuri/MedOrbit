"""
Manufacturer transaction CSVs: production released and sent to WAREHOUSES only.

Also injects a small % of intentional bad rows for Silver quarantine demos
(missing required fields, bad formats, invalid destination type).
"""
from __future__ import annotations

import os
import random
from datetime import datetime, timedelta, timezone

from medorbit_common import (
    OUTPUT_ROOT,
    facilities_by_type,
    iso,
    load_shared_dims,
    new_id,
    upload_csv_file,
    utc_now,
    write_csv,
)

random.seed(int(os.getenv("MEDORBIT_SEED", "42")) + 1)


def main():
    dims = load_shared_dims()
    plants = facilities_by_type(dims, "MANUFACTURER")
    warehouses = facilities_by_type(dims, "WAREHOUSE")
    hospitals = facilities_by_type(dims, "HOSPITAL")
    batches = dims["batch"]
    n = int(os.getenv("MEDORBIT_MFG_ROWS", "25000"))
    dirty_rate = float(os.getenv("MEDORBIT_DIRTY_RATE", "0.03"))  # ~3%

    batches_by_plant = {}
    for b in batches:
        batches_by_plant.setdefault(b["manufacturer_facility_id"], []).append(b)

    rows = []
    dirty_counts = {
        "missing_qty": 0,
        "bad_event_ts": 0,
        "missing_drug_id": 0,
        "invalid_to_facility": 0,
        "negative_qty": 0,
        "bad_plant_id": 0,
    }
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)

    for _ in range(n):
        plant = random.choice(plants)
        plant_batches = batches_by_plant.get(plant["facility_id"]) or batches
        batch = random.choice(plant_batches)
        drug_id = batch["drug_id"]
        wh = random.choice(warehouses)
        ts = start + timedelta(minutes=random.randint(0, 60 * 24 * 400))
        row = {
            "production_id": new_id("PROD"),
            "event_ts": iso(ts),
            "plant_facility_id": plant["facility_id"],
            "drug_id": drug_id,
            "batch_id": batch["batch_id"],
            "supplier_id": batch["supplier_id"],
            "qty_produced": random.randint(200, 5000),
            "to_warehouse_id": wh["facility_id"],
            "release_status": random.choices(["Released", "Hold"], weights=[95, 5])[0],
            "source_system": "MFG_ERP_SIM",
            "ingest_channel": "adls_csv",
        }

        if random.random() < dirty_rate:
            fault = random.choice(list(dirty_counts.keys()))
            dirty_counts[fault] += 1
            if fault == "missing_qty":
                row["qty_produced"] = ""
            elif fault == "bad_event_ts":
                row["event_ts"] = "32/13/2025 99:99"  # wrong format
            elif fault == "missing_drug_id":
                row["drug_id"] = ""
            elif fault == "invalid_to_facility":
                # violates MFG -> WHS only rule (Silver should quarantine)
                row["to_warehouse_id"] = random.choice(hospitals)["facility_id"]
            elif fault == "negative_qty":
                row["qty_produced"] = -random.randint(1, 500)
            elif fault == "bad_plant_id":
                row["plant_facility_id"] = "PLANT_UNKNOWN"

        rows.append(row)

    random.shuffle(rows)
    run_id = utc_now().strftime("%Y%m%dT%H%M%SZ")
    local_dir = OUTPUT_ROOT / "manufacturer" / run_id
    local = write_csv(local_dir / "manufacturer_production.csv", rows)
    adls = upload_csv_file(local, f"manufacturer/{run_id}/manufacturer_production.csv")
    print(
        {
            "local": str(local),
            "adls": adls,
            "rows": len(rows),
            "dirty_rate": dirty_rate,
            "dirty_counts": dirty_counts,
            "dirty_total": sum(dirty_counts.values()),
        }
    )


if __name__ == "__main__":
    main()
