# MedOrbit Phase 1 — Data Contract

Bronze sources to Dimensions to Facts to Gold marts.

**Chain rule:** Manufacturer to Warehouse only to Hospital/Pharmacy to Patient. No MFG to HSP/PHM.

## Ingest summary

| Source | Produced by | Landing | Databricks ingest (later) |
| --- | --- | --- | --- |
| Shared dims | generate_shared_dims.py (seed once) | ADLS medorbit-landing/shared-dims/ (+ UC Volume) | Auto Loader / batch to dim tables |
| Manufacturer txs | generate_manufacturer_csv.py | ADLS medorbit-landing/manufacturer/ | Auto Loader to Bronze |
| Warehouse txs | generate_warehouse_csv.py | ADLS medorbit-landing/warehouse/ | Auto Loader to Bronze |
| Hospital events | publish_hospital_events.py | Event Hub medorbit-hospital-events | Structured Streaming to Bronze |
| Pharmacy events | publish_pharmacy_events.py | Event Hub medorbit-pharmacy-events | Structured Streaming to Bronze |

---

## 1) Shared-dimension seed files (CSV)

### dim_date.csv

| Column | Type | Notes |
| --- | --- | --- |
| date_key | int | yyyymmdd |
| full_date | date | |
| year, month, day, quarter | int | |
| month_name | string | |
| week_of_year | int | |
| is_weekend | boolean | |
| season | string | Winter / Spring / Summer / Monsoon / Autumn |

### dim_supplier.csv

| Column | Type | Notes |
| --- | --- | --- |
| supplier_id | string | SUP_0001 |
| supplier_name | string | |
| country | string | |
| city | string | |
| contact_email | string | |
| status | string | Active / Inactive |
| effective_start | date | SCD2-ready |
| effective_end | date or null | |
| is_current | boolean | |

### dim_facility.csv

| Column | Type | Notes |
| --- | --- | --- |
| facility_id | string | MFG_ / WHS_ / HSP_ / PHM_ |
| facility_name | string | |
| facility_type | string | MANUFACTURER / WAREHOUSE / HOSPITAL / PHARMACY |
| city | string | |
| state | string | |
| region | string | North / South / East / West / Central |
| bed_count | int or null | hospitals only |
| status | string | Active |
| effective_start | date | SCD2-ready |
| effective_end | date or null | |
| is_current | boolean | |

### dim_drug.csv

| Column | Type | Notes |
| --- | --- | --- |
| drug_id | string | DRUG_0001 |
| drug_name | string | |
| generic_name | string | |
| form | string | tablet / syrup / injection |
| strength | string | e.g. 500mg |
| therapeutic_class | string | |
| unit_price_inr | decimal | for expiry dollar KPIs later |
| status | string | Active |
| effective_start | date | SCD2 |
| effective_end | date or null | |
| is_current | boolean | |

### dim_batch.csv

| Column | Type | Notes |
| --- | --- | --- |
| batch_id | string | BATCH_######## |
| drug_id | string | FK to dim_drug |
| manufacturer_facility_id | string | FK to MFG facility |
| supplier_id | string | FK to dim_supplier |
| mfg_date | date | |
| expiry_date | date | |
| status | string | Released / Quarantined |

### bridge_warehouse_serves.csv

| Column | Type | Notes |
| --- | --- | --- |
| warehouse_id | string | WHS_* |
| served_facility_id | string | HSP_* or PHM_* |
| is_primary | boolean | |
| effective_start | date | |

---

## 2) Manufacturer Bronze source (CSV)

### manufacturer_production.csv (Bronze: bronze_manufacturer_production)

| Column | Type | Notes |
| --- | --- | --- |
| production_id | string | PK |
| event_ts | timestamp | UTC |
| plant_facility_id | string | MFG_* only |
| drug_id | string | |
| batch_id | string | |
| supplier_id | string | |
| qty_produced | int | |
| to_warehouse_id | string | WHS_* only (no HSP/PHM) |
| release_status | string | Released / Hold |
| source_system | string | MFG_ERP_SIM |
| ingest_channel | string | adls_csv |

---

## 3) Warehouse Bronze sources (CSV)

### warehouse_stock_movements.csv (Bronze: bronze_warehouse_stock_movements)

| Column | Type | Notes |
| --- | --- | --- |
| movement_id | string | PK |
| event_ts | timestamp | |
| warehouse_id | string | WHS_* |
| drug_id | string | |
| batch_id | string | |
| movement_type | string | RECEIPT_FROM_MFG / SHIP_TO_FACILITY / ADJUSTMENT |
| qty | int | signed: +in / -out |
| from_facility_id | string or null | MFG_* when receipt |
| to_facility_id | string or null | HSP_*/PHM_* when ship; never MFG |
| source_system | string | WMS_SIM |
| ingest_channel | string | adls_csv |

### warehouse_shipments.csv (Bronze: bronze_warehouse_shipments)

| Column | Type | Notes |
| --- | --- | --- |
| shipment_id | string | PK |
| event_ts | timestamp | |
| warehouse_id | string | |
| to_facility_id | string | HSP_* or PHM_* only |
| drug_id | string | |
| batch_id | string | |
| qty_shipped | int | |
| shipment_status | string | DISPATCHED / DELIVERED / DELAYED |
| expected_delivery_ts | timestamp | |
| source_system | string | WMS_SIM |
| ingest_channel | string | adls_csv |

---

## 4) Hospital Event Hub JSON (Bronze: bronze_hospital_events)

Hub name: medorbit-hospital-events

Envelope fields always present; meaning varies by event_type.

| Field | Type | Notes |
| --- | --- | --- |
| event_id | string | PK |
| event_ts | timestamp | |
| event_type | string | PRESCRIPTION / CONSUMPTION / STOCK_ADJUST |
| hospital_facility_id | string | HSP_* |
| patient_id | string | synthetic |
| drug_id | string | |
| batch_id | string or null | |
| qty | int | |
| rx_id | string or null | for PRESCRIPTION / linked CONSUMPTION |
| department | string or null | |
| source_system | string | HIS_SIM |
| ingest_channel | string | eventhub |
| location_type | string | HOSPITAL |

---

## 5) Pharmacy Event Hub JSON (Bronze: bronze_pharmacy_events)

Hub name: medorbit-pharmacy-events

| Field | Type | Notes |
| --- | --- | --- |
| event_id | string | PK |
| event_ts | timestamp | |
| event_type | string | SALE / RETURN |
| pharmacy_facility_id | string | PHM_* |
| customer_id | string | synthetic walk-in |
| drug_id | string | |
| batch_id | string or null | |
| qty | int | |
| unit_price_inr | decimal | |
| line_total_inr | decimal | |
| payment_mode | string | CASH / UPI / CARD |
| source_system | string | POS_SIM |
| ingest_channel | string | eventhub |
| location_type | string | PHARMACY |

---

## 6) Target Gold model (for later)

Sims already support these KPI shapes.

### Dimensions (SCD2 on drug and facility)

dim_date, dim_drug, dim_facility, dim_supplier, dim_batch

### Facts

fact_production, fact_stock_movements, fact_shipments, fact_prescriptions, fact_hospital_consumption, fact_pharmacy_sales

### Marts

mart_exec_summary, mart_days_of_cover, mart_expiry_risk, mart_warehouse_velocity, mart_pharmacy_top_sellers, mart_projected_need, mart_seasonal_demand

---

## ID rules

- Facilities: MFG_ / WHS_ / HSP_ / PHM_ + city code + seq
- Drugs: DRUG_####
- Batches: BATCH_########
- Timestamps: UTC ISO-8601
- Chain rule: MFG to WHS to HSP/PHM to patient only
