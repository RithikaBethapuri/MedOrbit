"""
Azure Functions (Python v2) HTTP triggers to run MedOrbit Phase-1 sims.
Deploy this folder as the Function App content root (with scripts/ sibling copied in).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

# In deployment we copy scripts next to function_app.py under ./scripts
SCRIPTS_DIR = Path(os.getenv("MEDORBIT_SCRIPTS_DIR", str(Path(__file__).resolve().parent / "scripts")))


def _run_script(script_name: str) -> dict:
    script = SCRIPTS_DIR / script_name
    if not script.exists():
        return {"ok": False, "error": f"Script not found: {script}"}
    env = os.environ.copy()
    # Ensure shared dims path defaults under /home/site/wwwroot/output when on Functions
    env.setdefault("MEDORBIT_OUTPUT_ROOT", str(Path(__file__).resolve().parent / "output"))
    env.setdefault("MEDORBIT_SHARED_DIMS_DIR", str(Path(env["MEDORBIT_OUTPUT_ROOT"]) / "shared-dims"))
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(SCRIPTS_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=int(os.getenv("MEDORBIT_SCRIPT_TIMEOUT_SEC", "900")),
    )
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": proc.stdout[-8000:],
        "stderr": proc.stderr[-8000:],
        "script": script_name,
    }


@app.route(route="medorbit/shared-dims", methods=["POST"])
def generate_shared_dims(req: func.HttpRequest) -> func.HttpResponse:
    result = _run_script("generate_shared_dims.py")
    return func.HttpResponse(json.dumps(result), mimetype="application/json", status_code=200 if result["ok"] else 500)


@app.route(route="medorbit/manufacturer", methods=["POST"])
def generate_manufacturer(req: func.HttpRequest) -> func.HttpResponse:
    result = _run_script("generate_manufacturer_csv.py")
    return func.HttpResponse(json.dumps(result), mimetype="application/json", status_code=200 if result["ok"] else 500)


@app.route(route="medorbit/warehouse", methods=["POST"])
def generate_warehouse(req: func.HttpRequest) -> func.HttpResponse:
    result = _run_script("generate_warehouse_csv.py")
    return func.HttpResponse(json.dumps(result), mimetype="application/json", status_code=200 if result["ok"] else 500)


@app.route(route="medorbit/hospital-events", methods=["POST"])
def publish_hospital(req: func.HttpRequest) -> func.HttpResponse:
    result = _run_script("publish_hospital_events.py")
    return func.HttpResponse(json.dumps(result), mimetype="application/json", status_code=200 if result["ok"] else 500)


@app.route(route="medorbit/pharmacy-events", methods=["POST"])
def publish_pharmacy(req: func.HttpRequest) -> func.HttpResponse:
    result = _run_script("publish_pharmacy_events.py")
    return func.HttpResponse(json.dumps(result), mimetype="application/json", status_code=200 if result["ok"] else 500)


@app.route(route="medorbit/health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps({"ok": True, "scripts_dir": str(SCRIPTS_DIR), "scripts": [p.name for p in SCRIPTS_DIR.glob('*.py')]}),
        mimetype="application/json",
    )
