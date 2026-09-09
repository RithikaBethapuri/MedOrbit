# MedOrbit Phase 1 — Azure Portal setup (UI)

Event Hubs + Azure Function App to run sim scripts.

**Do not configure Databricks streaming yet** (next phase).

## Your existing resources

- RG: MedOrbit_rg (Central India)
- ADLS: medorbitadls6666
- Containers: medorbit-landing, medorbit-checkpoints, medorbit-exports
- Databricks: MedOrbit_databricks (later)

Scripts live at:

`C:\Users\VamshiKrishnaVaddemp\Data projects\MedOrbit\phase1_ingest\`

---

## A) Create Event Hubs (separate hubs for Hospital and Pharmacy)

### A1. Event Hubs Namespace

1. Portal: **Create a resource** then search **Event Hubs** then **Create**.
2. **Subscription:** your Free Trial sub (vskymt3).
3. **Resource group:** MedOrbit_rg.
4. **Namespace name:** MedOrbit_eventhubs (must be globally unique; if taken, add your initials, e.g. MedOrbit_eventhubs_vk).
5. **Location:** Central India.
6. **Pricing tier:** Basic (enough for demos) or Standard if Basic is unavailable in region.
7. **Throughput / TU:** leave default minimum.
8. Tags: project=MedOrbit.
9. **Review + create** then **Create**. Wait until deployment succeeds then **Go to resource**.

### A2. Create two Event Hubs

Inside the namespace: **Event Hubs** (left) then **+ Event Hub**.

| Name | Partition count | Retention |
| --- | --- | --- |
| medorbit-hospital-events | 2 | 1 day (Basic max may apply) |
| medorbit-pharmacy-events | 2 | 1 day |

Create each, then OK.

### A3. Get connection strings (for Function App settings)

1. Namespace: **Shared access policies**.
2. Click **RootManageSharedAccessKey** (or create MedOrbit_SendListen with **Send** + **Listen**).
3. Copy **Connection string-primary key** (namespace-level).

You will also need per-hub entity connection strings:

1. Open hub medorbit-hospital-events, **Shared access policies**, add policy MedOrbit_Hospital_Send with **Send**, copy connection string.
2. Same for medorbit-pharmacy-events: policy MedOrbit_Pharmacy_Send, copy connection string.

Keep these in Notepad temporarily. Do not commit them to GitHub.

---

## B) Confirm ADLS landing folders (already created earlier)

Portal: Storage account medorbitadls6666, **Containers**, medorbit-landing.

You should see folders: manufacturer, warehouse, hospital, pharmacy, shared-dims.

Sims will write under:

- shared-dims/*.csv
- manufacturer/RUN_ID/manufacturer_production.csv
- warehouse/RUN_ID/warehouse_stock_movements.csv
- warehouse/RUN_ID/warehouse_shipments.csv

Get storage key:

1. Storage account: **Access keys**, **key1**, **Show**, copy **Key** and/or **Connection string**.

---

## C) Create Azure Function App (Python) from Portal UI

### C1. Create Function App

1. **Create a resource** then **Function App** then **Create**.
2. **Basics**
   - Resource group: MedOrbit_rg
   - Function App name: MedOrbit_funcs (must be unique; add digits if needed)
   - **Code** (not Container)
   - Runtime stack: **Python**
   - Version: **3.11** (or 3.10 if 3.11 missing)
   - Region: **Central India**
   - OS: **Linux**
3. **Storage:** create new or use existing (Functions needs its own storage; can be a small new account like medorbitfuncstg1234 in same RG).
4. **Networking:** defaults (public).
5. **Monitoring:** Application Insights On (optional but useful).
6. Tags: project=MedOrbit
7. **Review + create** then **Create** then **Go to resource**.

### C2. Application settings (connection config)

Function App: **Settings** then **Environment variables** / **Configuration** then **App settings** then **+ Add**.

| Name | Value |
| --- | --- |
| MEDORBIT_STORAGE_CONNECTION_STRING | Storage connection string for medorbitadls6666 |
| MEDORBIT_LANDING_FILESYSTEM | medorbit-landing |
| MEDORBIT_EH_HOSPITAL_CONNECTION | Hospital hub Send connection string |
| MEDORBIT_EH_PHARMACY_CONNECTION | Pharmacy hub Send connection string |
| MEDORBIT_EH_HOSPITAL_NAME | medorbit-hospital-events |
| MEDORBIT_EH_PHARMACY_NAME | medorbit-pharmacy-events |
| MEDORBIT_MFG_ROWS | 25000 (optional; lower to 5000 for first test) |
| MEDORBIT_WHS_MOVEMENT_ROWS | 40000 (or 8000 for test) |
| MEDORBIT_WHS_SHIPMENT_ROWS | 20000 (or 5000 for test) |
| MEDORBIT_HOSPITAL_EVENTS | 50000 (or 5000 for test) |
| MEDORBIT_PHARMACY_EVENTS | 50000 (or 5000 for test) |
| MEDORBIT_SCRIPT_TIMEOUT_SEC | 900 |

**Apply** / **Save** and wait for restart.

Hosting plan: on Free Trial, **Consumption (Serverless)** is fine. First cold start can be slow.

### C3. Deploy code from VS Code / Cursor (simplest for students)

Portal-only zip deploy is painful for Python packages; recommended student path:

1. Install **Azure Functions** extension in VS Code/Cursor.
2. Open folder: `...\MedOrbit\phase1_ingest\azure_function`
3. Copy scripts into the Function package:
   - Copy entire folder `phase1_ingest\scripts`
   - Into `phase1_ingest\azure_function\scripts`
   - So function_app.py and scripts\ are siblings.
4. In VS Code: Azure icon, Function App MedOrbit_funcs, **Deploy to Function App**.
5. Wait for deploy success.

**Alternative (Azure Cloud Shell zip):**

Zip function_app.py, host.json, requirements.txt, and scripts\, then Function App **Deployment Center** / **Advanced Tools (Kudu)** zip deploy. Portal "Create function" wizard alone will not upload our multi-file package.

### C4. Verify functions exist

Function App: **Overview** then **Functions** should list HTTP routes like:

- generate_shared_dims : `/api/medorbit/shared-dims`
- generate_manufacturer : `/api/medorbit/manufacturer`
- generate_warehouse : `/api/medorbit/warehouse`
- publish_hospital : `/api/medorbit/hospital-events`
- publish_pharmacy : `/api/medorbit/pharmacy-events`
- health : `/api/medorbit/health`

Get function key: any function, **Function Keys**, default, copy.

### C5. Run order (from browser or Portal Test/Run)

**Always run shared-dims FIRST (once).**

1. Open function generate_shared_dims, **Test/Run**, Method **POST**, **Run**  
   OR browser/Postman:  
   `POST https://YOUR_FUNCTION_APP.azurewebsites.net/api/medorbit/shared-dims?code=YOUR_FUNCTION_KEY`  
   Replace YOUR_FUNCTION_APP with MedOrbit_funcs (or your actual name) and YOUR_FUNCTION_KEY with the key you copied.
2. Check ADLS medorbit-landing/shared-dims/ for 6 CSVs.
3. Then POST (one by one):
   - `/api/medorbit/manufacturer`
   - `/api/medorbit/warehouse`
   - `/api/medorbit/hospital-events`
   - `/api/medorbit/pharmacy-events`
4. Verify:
   - ADLS manufacturer + warehouse folders have new RUN_ID CSVs
   - Event Hubs: each hub Messages / metrics show incoming messages

---

## D) Local run option (if Functions deploy is delayed)

On your laptop (PowerShell):

```powershell
cd "C:\Users\VamshiKrishnaVaddemp\Data projects\MedOrbit\phase1_ingest"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# set env vars (same names as App Settings), then:
cd scripts
python generate_shared_dims.py
python generate_manufacturer_csv.py
python generate_warehouse_csv.py
python publish_hospital_events.py
python publish_pharmacy_events.py
```

If EH connection strings are missing, hospital/pharmacy scripts write **local JSONL fallback** under `scripts/output/eventhub_fallback/` (good for dry-run).

---

## E) What we are NOT doing yet

- Databricks Auto Loader / Volume external location
- Databricks Structured Streaming from Event Hubs
- Pharmacy one-sale UI

Those come after this landing data exists.

---

## F) Cost hygiene

- Stop Function App or leave on Consumption (idle is usually cheap).
- Do not leave Event Hub Standard with high TUs.
- After bulk publish, you can pause further POSTs until Databricks consumer is ready.
