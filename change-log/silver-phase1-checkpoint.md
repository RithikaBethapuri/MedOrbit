# MedOrbit Checkpoint — Continue on Another Device

**Date:** 2026-09-09  
**Goal:** Build Silver layer step-by-step in a personal Databricks sandbox (not the shared team workspace).  
**Mode:** Teaching / step-by-step. Do not jump ahead. Do not change team Azure/Databricks.

---

## 1. Project understanding (locked)

MedOrbit = pharmaceutical supply-chain lakehouse.

Flow:
Sources → ADLS / Event Hubs → Bronze (raw + dirty) → Silver (clean + quarantine) → ref dims / SCD2 → Gold facts + marts → SQL → dashboards + alerts

Chain rule: **MFG → WHS → HSP/PHM → patient**

`phase1_ingest` scripts: **not using for now**. Come back later.

Catalog (team): `medorbit_databricks`  
Catalog (personal practice): `medorbit_practice`

---

## 2. Silver decisions (locked)

| Decision | Choice |
|---|---|
| Price mismatch tolerance | `abs(line_total - qty * unit_price) <= 0.01` INR |
| Duplicates | Keep latest `_ingest_ts` per business key |
| Rebuild style | Full overwrite first; MERGE later |
| SCD2 | Separate step after transactional Silver (not mixed into tx cleaning) |
| Build order | Manufacturer first, then warehouse, then hospital/pharmacy |

Manufacturer quarantine reason codes:
- `MISSING_QTY`
- `BAD_EVENT_TS`
- `MISSING_DRUG_ID`
- `INVALID_TO_FACILITY`
- `NEGATIVE_QTY`
- `BAD_PLANT_ID`

---

## 3. Personal Databricks sandbox (completed)

Account: **personal** (not shared team workspace)

| Item | Value |
|---|---|
| Catalog | `medorbit_practice` |
| Workspace folder | `/Workspace/Users/rithikabethapuri@gmail.com/medorbit/` |
| Seed path | `/Workspace/Users/rithikabethapuri@gmail.com/medorbit/landing_seed` |
| Bootstrap notebook | `01_bootstrap_load_bronze` (edited CATALOG + seed path) |
| Silver notebook | `05_silver_manufacturer` / `S1_silver_manufacturer` |

Bootstrap counts (success):

```
ref:
  dim_date 1096
  dim_supplier 12
  dim_facility 32
  dim_drug 80
  dim_batch 400
  bridge_warehouse_serves 24

bronze:
  bronze_manufacturer_production 1200
  bronze_warehouse_stock_movements 1500
  bronze_warehouse_shipments 900
  bronze_hospital_events 1000
  bronze_pharmacy_events 1000
```

Schemas present: `ref`, `bronze`, `silver`, `gold`  
`silver.quarantine_events` existed as empty shell before manufacturer write.

Local seed source used:
- `C:\Users\rithika\Downloads\medorbit (4)\medorbit\landing_seed\`
- Do **not** upload dated `20260909T095025Z` folders for bootstrap

---

## 4. Silver Phase 1 progress (manufacturer)

### Completed steps

| Step | What | Status |
|---|---|---|
| 1 | Create Silver notebook | Done |
| 2 | Read Bronze manufacturer | Done |
| 3 | Inspect dirty rows (exploration only) | Done |
| 4 | Blank/`""` → null (`df_nulls`) | Done |
| 5 | Dedup by `production_id`, keep latest `_ingest_ts` (`df_dedup`) | Done |
| 6 | Type cast with SQL `try_to_timestamp` / `try_cast` (`df_typed`) | Done |
| 7 | Apply 6 reason codes + join `ref.dim_facility` manufacturers (`good`/`bad`) | Done |
| 8 | Write Silver + quarantine tables | **Confirm if run** — cell was provided; resume here if tables not yet written |

### Next step if Step 8 not finished

Write tables with overwrite:

- Good → `medorbit_practice.silver.silver_manufacturer_production`
- Bad → `medorbit_practice.silver.quarantine_events` (overwrite OK while manufacturer-only)

Then validate:
`bronze count ≈ silver good + quarantine`

### Step 8 write cell (copy if needed)

```python
from pyspark.sql import functions as F

silver_out = good.select(
    "production_id",
    F.col("event_ts_typed").alias("event_ts"),
    "plant_facility_id",
    "drug_id",
    "batch_id",
    "supplier_id",
    F.col("qty_produced_typed").alias("qty_produced"),
    "to_warehouse_id",
    "release_status",
    "source_system",
    "ingest_channel",
    "_ingest_ts",
    "_source_file",
)

quarantine_out = bad.select(
    F.lit("bronze_manufacturer_production").alias("source_table"),
    F.col("reason_code"),
    F.col("reason_code").alias("reason_detail"),
    F.to_json(F.struct([c for c in bad.columns if c not in ("valid_plant_id", "reason_code")])).alias("raw_payload"),
    F.current_timestamp().alias("quarantined_ts"),
)

silver_out.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(
    f"{CATALOG}.silver.silver_manufacturer_production"
)
quarantine_out.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(
    f"{CATALOG}.silver.quarantine_events"
)

print("silver rows:", spark.table(f"{CATALOG}.silver.silver_manufacturer_production").count())
print("quarantine rows:", spark.table(f"{CATALOG}.silver.quarantine_events").count())
```

### Important Spark note

On this Databricks runtime:
- `F.to_timestamp` / hard cast **fails** on dirty timestamps
- `F.try_cast` Python helper may be missing
- Use:

```python
F.expr("try_to_timestamp(event_ts)")
F.expr("try_cast(qty_produced as int)")
```

### Teaching notes already covered

- Step 3 dirty filter = inspection only, not final cleaning
- Step 4 = first real transformation (still in memory)
- “Clean” means: good → Silver, bad → quarantine, Bronze untouched
- Join to `ref.dim_facility` is for `BAD_PLANT_ID` only

---

## 5. Variable chain in notebook

```
df
→ df_nulls
→ df_dedup
→ df_typed
→ df_rules / good / bad
→ silver_out / quarantine_out
```

`CATALOG = "medorbit_practice"`

---

## 6. Not started yet

- Warehouse movements Silver
- Warehouse shipments Silver
- Hospital / pharmacy Silver (includes 0.01 price rule)
- SCD2 on `ref.dim_drug` / `ref.dim_facility`
- Gold
- Event Hub / `phase1_ingest`
- Team workspace changes

---

## 7. How to resume on another device

1. Open personal Databricks.
2. Open notebook under:
   `/Workspace/Users/rithikabethapuri@gmail.com/medorbit/`
3. Confirm Catalog tables under `medorbit_practice`.
4. If Step 8 not done: run the write cell, then count check.
5. Tell the assistant:  
   “Continue from Silver Phase 1 Step 8/9 using checkpoint.”

---

## 8. Change-log files (personal tracking)

- `change-log/change.md` — user-requested changes
- `change-log/recommendations.md` — Cursor suggestions
- `change-log/silver-phase1-checkpoint.md` — this file

Do not mix this checkpoint into main MedOrbit product docs unless asked.
