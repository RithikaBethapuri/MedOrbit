"""
Publish hospital transactional events to Event Hub medorbit-hospital-events.
Event types: PRESCRIPTION, CONSUMPTION, STOCK_ADJUST

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

random.seed(int(os.getenv("MEDORBIT_SEED", "42")) + 3)


def main():
    dims = load_shared_dims()
    hospitals = facilities_by_type(dims, "HOSPITAL")
    pharmacies = facilities_by_type(dims, "PHARMACY")
    drugs = dims["drug"]
    batches = dims["batch"]
    n = int(os.getenv("MEDORBIT_HOSPITAL_EVENTS", "50000"))
    dirty_rate = float(os.getenv("MEDORBIT_DIRTY_RATE", "0.03"))

    batches_by_drug = {}
    for b in batches:
        batches_by_drug.setdefault(b["drug_id"], []).append(b)

    events = []
    dirty_counts = {
        "missing_qty": 0,
        "bad_event_ts": 0,
        "missing_drug_id": 0,
        "missing_hospital_id": 0,
        "bad_event_type": 0,
        "wrong_location_type": 0,
        "pharmacy_id_as_hospital": 0,
        "zero_or_negative_rx_qty": 0,
    }
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    departments = ["ER", "ICU", "General", "Pediatrics", "Cardiology", "Oncology"]

    for _ in range(n):
        hsp = random.choice(hospitals)
        drug = random.choice(drugs)
        batch_list = batches_by_drug.get(drug["drug_id"], batches)
        batch = random.choice(batch_list)
        ts = start + timedelta(minutes=random.randint(0, 60 * 24 * 400))
        etype = random.choices(
            ["PRESCRIPTION", "CONSUMPTION", "STOCK_ADJUST"],
            weights=[45, 45, 10],
        )[0]
        rx_id = new_id("RX") if etype in ("PRESCRIPTION", "CONSUMPTION") else ""
        event = {
            "event_id": new_id("HEVT"),
            "event_ts": iso(ts),
            "event_type": etype,
            "hospital_facility_id": hsp["facility_id"],
            "patient_id": new_id("PAT"),
            "drug_id": drug["drug_id"],
            "batch_id": batch["batch_id"],
            "qty": random.randint(1, 60),
            "rx_id": rx_id,
            "department": random.choice(departments) if etype != "STOCK_ADJUST" else "",
            "source_system": "HIS_SIM",
            "ingest_channel": "eventhub",
            "location_type": "HOSPITAL",
        }

        if random.random() < dirty_rate:
            fault = random.choice(list(dirty_counts.keys()))
            dirty_counts[fault] += 1
            if fault == "missing_qty":
                event["qty"] = None
            elif fault == "bad_event_ts":
                event["event_ts"] = "yesterday-afternoon"
            elif fault == "missing_drug_id":
                event["drug_id"] = ""
            elif fault == "missing_hospital_id":
                event["hospital_facility_id"] = ""
            elif fault == "bad_event_type":
                event["event_type"] = "ADMISSION_PARTY"
            elif fault == "wrong_location_type":
                event["location_type"] = "PHARMACY"
            elif fault == "pharmacy_id_as_hospital":
                event["hospital_facility_id"] = random.choice(pharmacies)["facility_id"]
            elif fault == "zero_or_negative_rx_qty":
                event["event_type"] = "PRESCRIPTION"
                event["qty"] = random.choice([0, -5, -10])

        events.append(event)

    random.shuffle(events)
    result = publish_json_events("hospital", events)
    result["dirty_rate"] = dirty_rate
    result["dirty_counts"] = dirty_counts
    result["dirty_total"] = sum(dirty_counts.values())
    print(result)


if __name__ == "__main__":
    main()
