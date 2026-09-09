# MedOrbit — Teammate Handoff (Bronze / Silver / Gold)

**Audience:** teammates (+ their AI assistants) working from the Databricks Lakehouse stage onward.  
**Owner account:** vskymt3@gmail.com · RG `MedOrbit_rg` · Central India  
**Workspace:** https://adb-7405618208716207.7.azuredatabricks.net  
**Catalog (use this):** `medorbit_databricks`  
**Do not create a new catalog named `medorbit`** (metastore needs managed location; workspace catalog already exists).

Architecture reference image: `MedOrbit_Architecture_Latest.png` (same folder tree under Data projects/MedOrbit).

---

## 1) Project in one paragraph

MedOrbit is a pharmaceutical supply-chain lakehouse. Data flows **Manufacturer to Warehouse to Hospital/Pharmacy to Patient** (never MFG directly to HSP/PHM). Masters live in **dimensions** (clean). Transactions land in **Bronze** (includes intentional dirty rows). **Silver** cleans and **quarantines** bad rows. **Gold** builds star facts + KPI marts for dashboards and alerts. Ingest modes: CSV + Auto Loader for MFG/WHS; Event Hubs + Structured Streaming for HSP/PHM (EH/Functions may still be wiring; Bronze already seeded).

---

## 2) What is already bootstrapped (start here)

### ADLS landing (`medorbitadls6666` / container `medorbit-landing`)
- `shared-dims/*.csv` (clean)
- `manufacturer/<run_id>/manufacturer_production.csv` (~1200 rows, ~3% dirty)
- `warehouse/<run_id>/warehouse_stock_movements.csv` (~1500), `warehouse_shipments.csv` (~900)
- `hospital/<run_id>/hospital_events.csv` (~1000) bootstrap seed (same schema as Event Hub)
- `pharmacy/<run_id>/pharmacy_events.csv` (~1000) bootstrap seed

### Databricks workspace seed files
`/Workspace/Shared/medorbit/landing_seed/...` (same CSVs)

### Unity Catalog schemas
| Schema | Purpose |
| --- | --- |
| `medorbit_databricks.ref` | Clean shared dimensions / bridge |
| `medorbit_databricks.bronze` | Raw transactional + mirrored dims |
| `medorbit_databricks.silver` | Build cleaned tables; `quarantine_events` placeholder exists |
| `medorbit_databricks.gold` | Build facts + marts (empty schema ready) |

### Loaded row counts (bootstrap)
| Table | Rows |
| --- | --- |
| bronze.bronze_manufacturer_production | 1200 |
| bronze.bronze_warehouse_stock_movements | 1500 |
| bronze.bronze_warehouse_shipments | 900 |
| bronze.bronze_hospital_events | 1000 |
| bronze.bronze_pharmacy_events | 1000 |
| ref.dim_facility | 32 |
| ref.dim_drug | 80 |
| ref.dim_batch | 400 |
| ref.dim_supplier | 12 |
| ref.dim_date | 1096 |
| ref.bridge_warehouse_serves | 24 |
| silver.quarantine_events | 0 (empty shell) |

Bronze also mirrors dim_* / bridge_* for browsing one schema.

**SQL Warehouse:** Serverless Starter Warehouse id `dc303f2e2b2bdd83` (stop when idle).

**Notebook used for load:** `/Shared/medorbit/01_bootstrap_load_bronze`

---

## 3) Dimensions vs facts (what is what)

### Dimensions / reference (masters — clean)
Descriptive entities. Prefer reading from `medorbit_databricks.ref.*`.

| Table | Kind | Grain |
| --- | --- | --- |
| dim_date | Dimension | One day |
| dim_drug | Dimension (SCD2 later) | Drug (current + history) |
| dim_facility | Dimension (SCD2 later) | MFG / WHS / HSP / PHM place |
| dim_supplier | Dimension | Supplier |
| dim_batch | Dimension | Lot/batch |
| bridge_warehouse_serves | Bridge | Which warehouse serves which HSP/PHM |

### Bronze transactional (events — include dirty rows)
These become **facts** after Silver cleaning.

| Bronze table | Becomes Gold fact (later) |
| --- | --- |
| bronze_manufacturer_production | fact_production |
| bronze_warehouse_stock_movements | fact_stock_movements |
| bronze_warehouse_shipments | fact_shipments |
| bronze_hospital_events | fact_prescriptions / fact_hospital_consumption (split by event_type) |
| bronze_pharmacy_events | fact_pharmacy_sales |

### Gold business marts (dashboard KPIs — build after facts)
mart_exec_summary, mart_days_of_cover, mart_expiry_risk, mart_warehouse_velocity, mart_pharmacy_top_sellers, mart_projected_need, mart_seasonal_demand

---

## 4) Column contracts

### ref.dim_date
date_key, full_date, year, month, day, quarter, month_name, week_of_year, is_weekend, season (+ _ingest_ts, _source_file)

### ref.dim_supplier
supplier_id, supplier_name, country, city, contact_email, status, effective_start, effective_end, is_current

### ref.dim_facility
facility_id, facility_name, facility_type (MANUFACTURER/WAREHOUSE/HOSPITAL/PHARMACY), city, state, region, bed_count, status, effective_start, effective_end, is_current

### ref.dim_drug
drug_id, drug_name, generic_name, form, strength, therapeutic_class, unit_price_inr, status, effective_start, effective_end, is_current

### ref.dim_batch
batch_id, drug_id, manufacturer_facility_id, supplier_id, mfg_date, expiry_date, status

### ref.bridge_warehouse_serves
warehouse_id, served_facility_id, is_primary, effective_start

### bronze.bronze_manufacturer_production
production_id, event_ts, plant_facility_id, drug_id, batch_id, supplier_id, qty_produced, to_warehouse_id, release_status, source_system, ingest_channel

**Rule:** to_warehouse_id must be WHS_* only.

### bronze.bronze_warehouse_stock_movements
movement_id, event_ts, warehouse_id, drug_id, batch_id, movement_type (RECEIPT_FROM_MFG / SHIP_TO_FACILITY / ADJUSTMENT), qty, from_facility_id, to_facility_id, source_system, ingest_channel

### bronze.bronze_warehouse_shipments
shipment_id, event_ts, warehouse_id, to_facility_id (HSP_* or PHM_* only), drug_id, batch_id, qty_shipped, shipment_status (DISPATCHED/DELIVERED/DELAYED), expected_delivery_ts, source_system, ingest_channel

### bronze.bronze_hospital_events (Event Hub schema; bootstrap CSV seeded)
event_id, event_ts, event_type (PRESCRIPTION / CONSUMPTION / STOCK_ADJUST), hospital_facility_id, patient_id, drug_id, batch_id, qty, rx_id, department, source_system, ingest_channel, location_type=HOSPITAL

Later streaming should **APPEND** into this same table.

### bronze.bronze_pharmacy_events
event_id, event_ts, event_type (SALE / RETURN), pharmacy_facility_id, customer_id, drug_id, batch_id, qty, unit_price_inr, line_total_inr, payment_mode (CASH/UPI/CARD), source_system, ingest_channel, location_type=PHARMACY

Later streaming should **APPEND** into this same table.

### silver.quarantine_events (placeholder)
source_table, reason_code, reason_detail, raw_payload, quarantined_ts

---

## 5) Faults to clean in Silver (intentional ~3% dirty data)

Do **not** delete from Bronze. Route bad rows to quarantine with reason_code; keep good rows in silver_* tables.

### Manufacturer (bronze_manufacturer_production)
| reason_code | What to detect |
| --- | --- |
| MISSING_QTY | qty_produced null/blank |
| BAD_EVENT_TS | event_ts not parseable as timestamp |
| MISSING_DRUG_ID | drug_id blank |
| INVALID_TO_FACILITY | to_warehouse_id is HSP_* / PHM_* (not WHS_*) |
| NEGATIVE_QTY | qty_produced less than 0 |
| BAD_PLANT_ID | plant_facility_id not in dim_facility / not MFG_* |

### Warehouse movements
| reason_code | What to detect |
| --- | --- |
| MISSING_QTY | qty blank |
| BAD_EVENT_TS | bad timestamp |
| MISSING_WAREHOUSE_ID | warehouse_id blank |
| BAD_MOVEMENT_TYPE | not in allowed set (e.g. TELEPORT) |
| SHIP_WITHOUT_TO_FACILITY | SHIP_TO_FACILITY but to_facility_id blank |

### Warehouse shipments
| reason_code | What to detect |
| --- | --- |
| MISSING_QTY | qty_shipped blank |
| BAD_STATUS | status not DISPATCHED/DELIVERED/DELAYED (e.g. FLYING) |
| MISSING_TO_FACILITY | to_facility_id blank |
| BAD_EVENT_TS | bad timestamp |
| SHIP_TO_MANUFACTURER | to_facility_id is MFG_* |

### Hospital events
| reason_code | What to detect |
| --- | --- |
| MISSING_QTY | qty null/blank |
| BAD_EVENT_TS | unparseable |
| MISSING_DRUG_ID | blank |
| MISSING_HOSPITAL_ID | blank |
| BAD_EVENT_TYPE | not PRESCRIPTION/CONSUMPTION/STOCK_ADJUST |
| WRONG_LOCATION_TYPE | location_type not HOSPITAL |
| PHARMACY_ID_AS_HOSPITAL | hospital_facility_id is PHM_* |
| ZERO_OR_NEGATIVE_RX_QTY | PRESCRIPTION with qty less than or equal to 0 |

### Pharmacy events
| reason_code | What to detect |
| --- | --- |
| MISSING_QTY | qty null/blank |
| BAD_EVENT_TS | unparseable |
| MISSING_DRUG_ID | blank |
| MISSING_PHARMACY_ID | blank |
| BAD_PAYMENT_MODE | not CASH/UPI/CARD |
| BAD_EVENT_TYPE | not SALE/RETURN |
| HOSPITAL_ID_AS_PHARMACY | pharmacy_facility_id is HSP_* |
| PRICE_MISMATCH | line_total_inr not equal qty * unit_price_inr (tolerance) |
| SALE_WITH_NEGATIVE_QTY | SALE with qty less than 0 |

Shared-dims / ref tables are **clean** — no intentional faults there.

---

## 6) Suggested Silver / Gold build order

1. Silver: validate Bronze txs using rules above; write `silver.*` + `silver.quarantine_events`.
2. Promote / harden dims in `ref` (cast types; prepare SCD2 MERGE on dim_drug, dim_facility).
3. Gold facts from clean silver (FK to dims).
4. Gold marts for dashboards.
5. When Event Hubs ready: stream append into bronze_hospital_events / bronze_pharmacy_events (same schema).

---

## 7) Dashboards, cases, KPIs / metrics

Pages: Executive · Hospital · Warehouse · Pharmacy · Manufacturing (+ Alerts panel).

### Executive (mart_exec_summary)
- Total network stock units
- Critical shortage SKU count
- Facilities at risk count
- Expiry risk value (e.g. within 90 days) in INR
- Health / availability score (composite optional)

### Hospital (mart_days_of_cover, mart_projected_need, mart_seasonal_demand)
- On-hand by drug/facility
- Days of cover (on_hand / avg daily use)
- This week projected need vs on-hand (from Rx)
- Gap / surplus
- Last year same season top drug and volume

### Warehouse (mart_warehouse_velocity)
- Top shipped / moved drugs
- Qty on hand now
- Velocity (units/day)
- Linked facilities served (bridge_warehouse_serves)
- Cross-case: hospital shortage coverable from warehouse stock (same drug_id)

### Pharmacy (mart_pharmacy_top_sellers)
- Top sellers this week
- On-hand of top SKUs
- Stock-out / low-stock risk
- Demo story later: one UI sale then refresh

### Manufacturing (production + mart_expiry_risk)
- Batches / qty produced (30d)
- Fill rate into warehouses
- Batches near expiry at source

### Alerts (from mart thresholds — config outside dashboard)
- Critical shortage
- Low days-of-cover
- Expiry soon
- Projected need gap  
Channels target: Email / Teams (implementation later)

---

## 8) Chain and ID rules

- Facility IDs: MFG_ / WHS_ / HSP_ / PHM_ + city + seq
- Drug: DRUG_#### · Batch: BATCH_########
- Timestamps intended UTC ISO-8601 (Bronze may have bad strings to quarantine)
- Supply chain: **MFG → WHS → HSP/PHM → patient only**

---

## 9) What teammates should NOT wait on

- Event Hub / Azure Function wiring can continue in parallel.
- Auto Loader / external Volume can be added later; Bronze tables already exist for Silver/Gold work.
- Pharmacy one-sale UI is later.

---

## 10) Cost hygiene

- Use **Serverless** notebooks/SQL.
- Stop SQL warehouse when idle.
- Avoid classic clusters in Central India unless required.

---

## 11) Quick verify queries

```sql
SHOW SCHEMAS IN medorbit_databricks;
SHOW TABLES IN medorbit_databricks.bronze;
SHOW TABLES IN medorbit_databricks.ref;
SELECT count(*) FROM medorbit_databricks.bronze.bronze_hospital_events;
SELECT * FROM medorbit_databricks.bronze.bronze_manufacturer_production LIMIT 20;
```

Look for dirty examples:

```sql
-- bad timestamps / blank qty samples
SELECT * FROM medorbit_databricks.bronze.bronze_manufacturer_production
WHERE qty_produced = '' OR event_ts NOT LIKE '____-__-__T%';
```

---

## 12) Related local docs / code (owner machine)

- `phase1_ingest/docs/01_DATA_CONTRACT.md`
- `phase1_ingest/docs/02_AZURE_PORTAL_SETUP.md` (EH + Functions UI)
- `phase1_ingest/scripts/` (generators with MEDORBIT_DIRTY_RATE=0.03)

---

*Bootstrap loaded for MedOrbit capstone so Silver/Gold work can start from Databricks without waiting for Event Hub producers.*
