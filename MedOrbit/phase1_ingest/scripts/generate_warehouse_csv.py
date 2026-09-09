"""
Warehouse transaction CSVs:
- stock movements (receipts from MFG, shipments to HSP/PHM)
- shipments detail to hospitals/pharmacies only

Also injects a small % of intentional bad rows for Silver quarantine demos.
"""
from __future__ import annotations

import os
import random
from collections import defaultdict
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

random.seed(int(os.getenv("MEDORBIT_SEED", "42")) + 2)


def main():
    dims = load_shared_dims()
    warehouses = facilities_by_type(dims, "WAREHOUSE")
    manufacturers = facilities_by_type(dims, "MANUFACTURER")
    batches = dims["batch"]
    serves = dims["serves"]
    dirty_rate = float(os.getenv("MEDORBIT_DIRTY_RATE", "0.03"))

    serves_map = defaultdict(list)
    for s in serves:
        serves_map[s["warehouse_id"]].append(s["served_facility_id"])

    n_move = int(os.getenv("MEDORBIT_WHS_MOVEMENT_ROWS", "40000"))
    n_ship = int(os.getenv("MEDORBIT_WHS_SHIPMENT_ROWS", "20000"))

    movements = []
    shipments = []
    move_dirty = {
        "missing_qty": 0,
        "bad_event_ts": 0,
        "missing_warehouse_id": 0,
        "bad_movement_type": 0,
        "ship_without_to_facility": 0,
    }
    ship_dirty = {
        "missing_qty": 0,
        "bad_status": 0,
        "missing_to_facility": 0,
        "bad_event_ts": 0,
        "ship_to_manufacturer": 0,
    }
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)

    for _ in range(n_move):
        wh = random.choice(warehouses)
        batch = random.choice(batches)
        ts = start + timedelta(minutes=random.randint(0, 60 * 24 * 400))
        mtype = random.choices(
            ["RECEIPT_FROM_MFG", "SHIP_TO_FACILITY", "ADJUSTMENT"],
            weights=[35, 55, 10],
        )[0]
        from_fac = ""
        to_fac = ""
        qty = random.randint(10, 2000)
        if mtype == "RECEIPT_FROM_MFG":
            from_fac = random.choice(manufacturers)["facility_id"]
            qty = abs(qty)
        elif mtype == "SHIP_TO_FACILITY":
            options = serves_map.get(wh["facility_id"]) or []
            if not options:
                continue
            to_fac = random.choice(options)
            qty = -abs(qty)
        else:
            qty = random.choice([-1, 1]) * random.randint(1, 50)

        row = {
            "movement_id": new_id("MOV"),
            "event_ts": iso(ts),
            "warehouse_id": wh["facility_id"],
            "drug_id": batch["drug_id"],
            "batch_id": batch["batch_id"],
            "movement_type": mtype,
            "qty": qty,
            "from_facility_id": from_fac,
            "to_facility_id": to_fac,
            "source_system": "WMS_SIM",
            "ingest_channel": "adls_csv",
        }

        if random.random() < dirty_rate:
            fault = random.choice(list(move_dirty.keys()))
            move_dirty[fault] += 1
            if fault == "missing_qty":
                row["qty"] = ""
            elif fault == "bad_event_ts":
                row["event_ts"] = "not-a-timestamp"
            elif fault == "missing_warehouse_id":
                row["warehouse_id"] = ""
            elif fault == "bad_movement_type":
                row["movement_type"] = "TELEPORT"
            elif fault == "ship_without_to_facility":
                row["movement_type"] = "SHIP_TO_FACILITY"
                row["to_facility_id"] = ""
                row["qty"] = -abs(int(row["qty"]) if str(row["qty"]).lstrip("-").isdigit() else 10)

        movements.append(row)

    for _ in range(n_ship):
        wh = random.choice(warehouses)
        options = serves_map.get(wh["facility_id"]) or []
        if not options:
            continue
        to_fac = random.choice(options)
        batch = random.choice(batches)
        ts = start + timedelta(minutes=random.randint(0, 60 * 24 * 400))
        status = random.choices(
            ["DISPATCHED", "DELIVERED", "DELAYED"], weights=[20, 70, 10]
        )[0]
        row = {
            "shipment_id": new_id("SHIP"),
            "event_ts": iso(ts),
            "warehouse_id": wh["facility_id"],
            "to_facility_id": to_fac,
            "drug_id": batch["drug_id"],
            "batch_id": batch["batch_id"],
            "qty_shipped": random.randint(20, 1500),
            "shipment_status": status,
            "expected_delivery_ts": iso(ts + timedelta(hours=random.randint(6, 72))),
            "source_system": "WMS_SIM",
            "ingest_channel": "adls_csv",
        }

        if random.random() < dirty_rate:
            fault = random.choice(list(ship_dirty.keys()))
            ship_dirty[fault] += 1
            if fault == "missing_qty":
                row["qty_shipped"] = ""
            elif fault == "bad_status":
                row["shipment_status"] = "FLYING"
            elif fault == "missing_to_facility":
                row["to_facility_id"] = ""
            elif fault == "bad_event_ts":
                row["event_ts"] = "2025-99-99T25:61:00Z"
            elif fault == "ship_to_manufacturer":
                row["to_facility_id"] = random.choice(manufacturers)["facility_id"]

        shipments.append(row)

    random.shuffle(movements)
    random.shuffle(shipments)

    run_id = utc_now().strftime("%Y%m%dT%H%M%SZ")
    local_dir = OUTPUT_ROOT / "warehouse" / run_id
    mov_path = write_csv(local_dir / "warehouse_stock_movements.csv", movements)
    ship_path = write_csv(local_dir / "warehouse_shipments.csv", shipments)
    mov_uri = upload_csv_file(mov_path, f"warehouse/{run_id}/warehouse_stock_movements.csv")
    ship_uri = upload_csv_file(ship_path, f"warehouse/{run_id}/warehouse_shipments.csv")
    print(
        {
            "movements": {
                "local": str(mov_path),
                "adls": mov_uri,
                "rows": len(movements),
                "dirty_counts": move_dirty,
                "dirty_total": sum(move_dirty.values()),
            },
            "shipments": {
                "local": str(ship_path),
                "adls": ship_uri,
                "rows": len(shipments),
                "dirty_counts": ship_dirty,
                "dirty_total": sum(ship_dirty.values()),
            },
            "dirty_rate": dirty_rate,
        }
    )


if __name__ == "__main__":
    main()
