"""
Publish pharmacy transactional events to Event Hub medorbit-pharmacy-events.
Event types: SALE, RETURN

Injects ~3% intentional bad events for Silver quarantine demos.
"""
from __future__ import annotations

import os
import random
from datetime import datetime, timedelta, timezone

from medorbit_common import (
    facilities_by_type,
    iso,
    load_shared_dims,
    new_id,
    publish_json_events,
)

random.seed(int(os.getenv("MEDORBIT_SEED", "42")) + 4)


def main():
    dims = load_shared_dims()
    pharmacies = facilities_by_type(dims, "PHARMACY")
    hospitals = facilities_by_type(dims, "HOSPITAL")
    drugs = [d for d in dims["drug"] if d.get("is_current", "true").lower() == "true"]
    batches = dims["batch"]
    n = int(os.getenv("MEDORBIT_PHARMACY_EVENTS", "50000"))
    dirty_rate = float(os.getenv("MEDORBIT_DIRTY_RATE", "0.03"))

    price_map = {d["drug_id"]: float(d["unit_price_inr"]) for d in drugs}
    batches_by_drug = {}
    for b in batches:
        batches_by_drug.setdefault(b["drug_id"], []).append(b)

    events = []
    dirty_counts = {
        "missing_qty": 0,
        "bad_event_ts": 0,
        "missing_drug_id": 0,
        "missing_pharmacy_id": 0,
        "bad_payment_mode": 0,
        "bad_event_type": 0,
        "hospital_id_as_pharmacy": 0,
        "price_mismatch": 0,
        "sale_with_negative_qty": 0,
    }
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)

    for _ in range(n):
        phm = random.choice(pharmacies)
        drug = random.choice(drugs)
        batch_list = batches_by_drug.get(drug["drug_id"], batches)
        batch = random.choice(batch_list)
        ts = start + timedelta(minutes=random.randint(0, 60 * 24 * 400))
        etype = random.choices(["SALE", "RETURN"], weights=[94, 6])[0]
        qty = random.randint(1, 20)
        unit_price = price_map.get(drug["drug_id"], 25.0)
        sign = 1 if etype == "SALE" else -1
        event = {
            "event_id": new_id("PEVT"),
            "event_ts": iso(ts),
            "event_type": etype,
            "pharmacy_facility_id": phm["facility_id"],
            "customer_id": new_id("CUST"),
            "drug_id": drug["drug_id"],
            "batch_id": batch["batch_id"],
            "qty": sign * qty,
            "unit_price_inr": round(unit_price, 2),
            "line_total_inr": round(sign * qty * unit_price, 2),
            "payment_mode": random.choice(["UPI", "CASH", "CARD"]),
            "source_system": "POS_SIM",
            "ingest_channel": "eventhub",
            "location_type": "PHARMACY",
        }

        if random.random() < dirty_rate:
            fault = random.choice(list(dirty_counts.keys()))
            dirty_counts[fault] += 1
            if fault == "missing_qty":
                event["qty"] = None
            elif fault == "bad_event_ts":
                event["event_ts"] = "13/40/2025"
            elif fault == "missing_drug_id":
                event["drug_id"] = ""
            elif fault == "missing_pharmacy_id":
                event["pharmacy_facility_id"] = ""
            elif fault == "bad_payment_mode":
                event["payment_mode"] = "BITCOIN_BARTER"
            elif fault == "bad_event_type":
                event["event_type"] = "LOYALTY_SPIN"
            elif fault == "hospital_id_as_pharmacy":
                event["pharmacy_facility_id"] = random.choice(hospitals)["facility_id"]
            elif fault == "price_mismatch":
                # line_total does not equal qty * unit_price
                event["line_total_inr"] = round(unit_price * qty + 999.99, 2)
            elif fault == "sale_with_negative_qty":
                event["event_type"] = "SALE"
                event["qty"] = -abs(qty)
                event["line_total_inr"] = round(-abs(qty) * unit_price, 2)

        events.append(event)

    random.shuffle(events)
    result = publish_json_events("pharmacy", events)
    result["dirty_rate"] = dirty_rate
    result["dirty_counts"] = dirty_counts
    result["dirty_total"] = sum(dirty_counts.values())
    print(result)


if __name__ == "__main__":
    main()
