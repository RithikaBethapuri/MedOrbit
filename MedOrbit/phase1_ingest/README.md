# MedOrbit Phase 1 — Ingest simulations

## What’s in this folder
| Path | Purpose |
|---|---|
| `docs/01_DATA_CONTRACT.md` | Tables/columns Bronze→Dims→Facts→Marts |
| `docs/02_AZURE_PORTAL_SETUP.md` | **UI steps**: Event Hubs + Function App |
| `scripts/` | Python simulators |
| `azure_function/` | HTTP triggers that run those scripts |
| `requirements.txt` | Python deps |

## Scripts
1. `generate_shared_dims.py` — **once** (masters + warehouse_serves)
2. `generate_manufacturer_csv.py` — MFG → **Warehouse only** CSVs → ADLS
3. `generate_warehouse_csv.py` — WHS → **HSP/PHM** CSVs → ADLS
4. `publish_hospital_events.py` — Rx/consumption → **Event Hub hospital**
5. `publish_pharmacy_events.py` — sales → **Event Hub pharmacy**

## Default volumes (env-overridable)
~80 drugs, ~32 facilities, ~25k MFG + ~60k WHS + ~50k hospital + ~50k pharmacy ≈ **~185k** events/rows.

## Next after Portal setup
Configure Databricks Volume (external on ADLS) + Auto Loader + Event Hub streaming → Bronze.
