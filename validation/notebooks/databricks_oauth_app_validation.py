# Databricks notebook source
# DBTITLE 1,Overview
# MAGIC %md
# MAGIC # Databricks Connector OAuth Validation
# MAGIC
# MAGIC This notebook validates the **service principal (M2M) OAuth credentials** used by the **Databricks connector** in Glean.
# MAGIC
# MAGIC ## What you need
# MAGIC
# MAGIC | What | Where to find it |
# MAGIC |---|---|
# MAGIC | Workspace Host URL | Your Databricks workspace URL, e.g. `https://dbc-xxxx.cloud.databricks.com` |
# MAGIC | Client ID | The service principal's OAuth Client ID |
# MAGIC | Client Secret | The service principal's OAuth Client Secret |
# MAGIC
# MAGIC ## What this notebook tests
# MAGIC
# MAGIC 1. **OIDC Discovery** — confirms the workspace OAuth endpoints are reachable
# MAGIC 2. **Client Credentials Token** — requests a token using your service principal credentials
# MAGIC
# MAGIC > **Scope:** This validates the Databricks **connector** (M2M) credentials only.
# MAGIC > If you are setting up the Databricks **tools** (Genie/SQL in Assistant), use the companion notebook: `notebooks/databricks_tools_oauth_validation`.
# MAGIC
# MAGIC ---
# MAGIC *Questions? Ping sabrina.wang@glean.com*

# COMMAND ----------

# DBTITLE 1,Widget Inputs
dbutils.widgets.text("WORKSPACE_HOST", "", "Workspace Host URL")
dbutils.widgets.text("CLIENT_ID", "", "Client ID")
dbutils.widgets.text("CLIENT_SECRET", "", "Client Secret")

WORKSPACE_HOST = dbutils.widgets.get("WORKSPACE_HOST").rstrip("/")
CLIENT_ID      = dbutils.widgets.get("CLIENT_ID").strip()
CLIENT_SECRET  = dbutils.widgets.get("CLIENT_SECRET").strip()

if not WORKSPACE_HOST:
    print("[!] Please enter your Workspace Host URL (e.g. https://dbc-xxxx.cloud.databricks.com)")
else:
    print(f"Workspace Host : {WORKSPACE_HOST}")
    print(f"Client ID      : {'set' if CLIENT_ID else 'NOT SET'}")
    print(f"Client Secret  : {'set' if CLIENT_SECRET else 'NOT SET'}")

# COMMAND ----------

# DBTITLE 1,Step 2 - OIDC Discovery
# MAGIC %md
# MAGIC ## Step 2 — OIDC Discovery
# MAGIC
# MAGIC Hits the OIDC discovery endpoint and returns the full OAuth server configuration.
# MAGIC
# MAGIC - `authorization_endpoint` — **Authorization URL** to use in Glean
# MAGIC - `token_endpoint` — **Token URL** to use in Glean
# MAGIC - Confirms `all-apis` and `offline_access` are in `scopes_supported`
# MAGIC
# MAGIC If this fails, the workspace host URL is likely incorrect.

# COMMAND ----------

import requests
import json

OIDC_DISCOVERY_URL = f"{WORKSPACE_HOST}/oidc/.well-known/oauth-authorization-server"

try:
    resp = requests.get(OIDC_DISCOVERY_URL, timeout=10)
    resp.raise_for_status()
    oidc_config = resp.json()
    print(f"[PASS] OIDC discovery endpoint reachable")
    print(f"  URL    : {OIDC_DISCOVERY_URL}")
    print(f"  Status : {resp.status_code}")
    print()
    print(f"  authorization_endpoint : {oidc_config.get('authorization_endpoint')}")
    print(f"  token_endpoint         : {oidc_config.get('token_endpoint')}")
    print()
    scopes = oidc_config.get('scopes_supported', [])
    for s in ['all-apis', 'offline_access']:
        print(f"  scope '{s}': {'found' if s in scopes else 'MISSING'}")
except Exception as e:
    oidc_config = {}
    print(f"[FAIL] Could not reach OIDC discovery endpoint")
    print(f"  URL   : {OIDC_DISCOVERY_URL}")
    print(f"  Error : {e}")
    print("  Check that WORKSPACE_HOST is correct and reachable.")

# COMMAND ----------

# DBTITLE 1,Step 3 - Client Credentials Token Test
# MAGIC %md
# MAGIC ## Step 3 — Client Credentials Token Test
# MAGIC
# MAGIC **PASS:** Service principal credentials are valid and the token endpoint is reachable.
# MAGIC
# MAGIC **Common failures:**
# MAGIC - `invalid_client` — wrong Client ID or Secret
# MAGIC - `not available in Databricks account` — Client ID belongs to an App Connection, not a service principal.
# MAGIC   For the connector, you need a **service principal** credential. Use `databricks_tools_oauth_validation` for App Connection testing.

# COMMAND ----------

TOKEN_URL = f"{WORKSPACE_HOST}/oidc/v1/token"

if not CLIENT_ID or not CLIENT_SECRET:
    print("[SKIP] CLIENT_ID or CLIENT_SECRET not set.")
else:
    try:
        token_resp = requests.post(
            TOKEN_URL,
            data={"grant_type": "client_credentials", "scope": "all-apis"},
            auth=(CLIENT_ID, CLIENT_SECRET),
            timeout=10,
        )
        if token_resp.status_code == 200:
            token_data = token_resp.json()
            print("[PASS] Client credentials are valid.")
            print(f"  Token type : {token_data.get('token_type')}")
            print(f"  Expires in : {token_data.get('expires_in')} seconds")
            print(f"  Scope      : {token_data.get('scope')}")
        else:
            print(f"[FAIL] HTTP {token_resp.status_code}")
            try:
                err = token_resp.json()
                print(f"  error             : {err.get('error')}")
                print(f"  error_description : {err.get('error_description')}")
            except Exception:
                print(f"  Raw: {token_resp.text}")
    except Exception as e:
        token_resp = None
        print(f"[FAIL] Request error: {e}")

# COMMAND ----------

# DBTITLE 1,Step 4 - Summary
oidc_ok  = bool(oidc_config.get("authorization_endpoint") and oidc_config.get("token_endpoint"))
creds_ok = 'token_resp' in dir() and token_resp is not None and token_resp.status_code == 200

SEP = "=" * 60
print(SEP)
print("Databricks Connector OAuth Validation Summary")
print(SEP)
print(f"\nWorkspace Host : {WORKSPACE_HOST}")
print(f"\n1. OIDC Discovery     : {'PASS' if oidc_ok else 'FAIL'}")
if oidc_ok:
    print(f"     authorization_endpoint : {oidc_config.get('authorization_endpoint')}")
    print(f"     token_endpoint         : {oidc_config.get('token_endpoint')}")
else:
    print("     Fix: verify WORKSPACE_HOST is correct and reachable.")
print(f"\n2. Client Credentials : {'PASS' if creds_ok else 'FAIL'}")
if not creds_ok and CLIENT_ID and CLIENT_SECRET:
    try:
        err = token_resp.json()
        print(f"     {err.get('error')}: {err.get('error_description')}")
    except Exception:
        pass
print()
print("Note: this validates M2M (connector) credentials only.")
print("For Databricks tools (Genie/SQL in Glean), use databricks_tools_oauth_validation.")
print(SEP)
print("\nQuestions? Ping sabrina.wang@glean.com")
