#!/usr/bin/python -tt
# Project: ac5_applying_naf_framework
# Filename: webhook_receiver.py
# claudiadeluna
# PyCharm

from __future__ import absolute_import, division, print_function

__author__ = "Claudia de Luna (claudia@indigowire.net)"
__version__ = ": 1.0 $"
__date__ = "6/9/26"
__copyright__ = "Copyright (c) 2023 Claudia"
__license__ = "Python"

"""
FastAPI webhook receiver for Infrahub events.

Listens for Infrahub outbound webhooks.  When an
'infrahub.proposed_change.merged' event arrives, creates a Prefect flow
run for the 'acl-lifecycle' deployment.

Run:
    uv run uvicorn lowcode_solution.webhook_receiver:app --port 8000 --reload

Configure in Infrahub UI:
    Webhook URL  : http://<your-host>:8000/webhook/infrahub
    Events       : proposed_change.merged
    Shared secret: set INFRAHUB_WEBHOOK_SECRET in .env (leave blank to skip validation)

Test without Infrahub:
    curl -X POST http://localhost:8000/test/trigger
"""

import hashlib
import hmac
import json
import logging
import os

import httpx
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request

load_dotenv()

PREFECT_API_URL = os.getenv("PREFECT_API_URL", "http://127.0.0.1:4200/api")
WEBHOOK_SECRET = os.getenv("INFRAHUB_WEBHOOK_SECRET", "")
# Deployment is registered as <flow-name>/<serve-name> in Prefect
DEPLOYMENT_FLOW_NAME = "acl-lifecycle"
DEPLOYMENT_NAME = "acl-lifecycle"

log = logging.getLogger("webhook_receiver")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(title="Infrahub → Prefect Webhook Receiver")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _verify_signature(body: bytes, header: str, secret: str) -> bool:
    """Return True if the HMAC-SHA256 signature matches, or if no secret is set."""
    if not secret:
        return True
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    candidate = header.removeprefix("sha256=")
    return hmac.compare_digest(expected, candidate)


def _create_prefect_run() -> str:
    """Look up the deployment by name and create a flow run. Returns the run ID."""
    with httpx.Client(base_url=PREFECT_API_URL, timeout=10) as client:
        # Resolve deployment name → ID
        resp = client.get(f"/deployments/name/{DEPLOYMENT_FLOW_NAME}/{DEPLOYMENT_NAME}")
        if resp.status_code == 404:
            raise RuntimeError(
                f"Deployment '{DEPLOYMENT_FLOW_NAME}/{DEPLOYMENT_NAME}' not found. "
                "Is 'acl_lifecycle_flow.py' running with flow.serve()?"
            )
        resp.raise_for_status()
        deployment_id = resp.json()["id"]

        # Create the flow run
        run_resp = client.post(f"/deployments/{deployment_id}/create_flow_run", json={})
        run_resp.raise_for_status()
        run_id = run_resp.json()["id"]

    log.info("Prefect flow run created: %s (deployment: %s/%s)", run_id, DEPLOYMENT_FLOW_NAME, DEPLOYMENT_NAME)
    return run_id


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/webhook/infrahub")
async def infrahub_webhook(request: Request, background_tasks: BackgroundTasks):
    """Receive Infrahub outbound webhook events."""
    body = await request.body()
    signature = request.headers.get("webhook-signature", "")

    if WEBHOOK_SECRET and not _verify_signature(body, signature, WEBHOOK_SECRET):
        log.warning("Webhook signature validation failed")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # Infrahub sends event_type at the top level or nested under 'event'
    event_type = payload.get("event_type") or payload.get("event", {}).get("type", "")
    log.info("Received Infrahub event: %s", event_type)

    if event_type != "infrahub.proposed_change.merged":
        return {"status": "ignored", "event_type": event_type}

    background_tasks.add_task(_create_prefect_run)
    return {"status": "accepted", "event_type": event_type}


@app.post("/test/trigger")
async def test_trigger(background_tasks: BackgroundTasks):
    """Trigger the Prefect flow without HMAC validation — for local testing."""
    log.info("Test trigger invoked — creating Prefect flow run")
    background_tasks.add_task(_create_prefect_run)
    return {"status": "triggered", "deployment": f"{DEPLOYMENT_FLOW_NAME}/{DEPLOYMENT_NAME}"}


@app.get("/health")
async def health():
    return {"status": "ok", "prefect_api": PREFECT_API_URL}
