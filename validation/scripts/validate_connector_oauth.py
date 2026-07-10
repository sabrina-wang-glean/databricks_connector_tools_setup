#!/usr/bin/env python3
"""
Databricks Connector OAuth Validation

Validates the M2M (service principal) OAuth credentials used by the
Databricks connector in Glean. Runs two checks:
  1. OIDC Discovery  - confirms workspace OAuth endpoints are reachable
  2. Client Credentials Token - confirms the service principal credentials are valid

Usage:
    python validate_connector_oauth.py \\
        --workspace-host https://dbc-xxxx.cloud.databricks.com \\
        --client-id YOUR_CLIENT_ID \\
        --client-secret YOUR_CLIENT_SECRET

Requirements:
    pip install requests

Note: This validates the *connector* (M2M) credentials only.
For tools (U2M / App Connection), use validate_tools_oauth.py.

Questions? Ping sabrina.wang@glean.com
"""

import argparse
import json
import sys
import requests


SEP = "=" * 65


def check_oidc_discovery(workspace_host: str) -> dict:
    url = f"{workspace_host}/oidc/.well-known/oauth-authorization-server"
    print(f"\n[1/2] OIDC Discovery")
    print(f"      {url}")
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        config = resp.json()
        print(f"      Status : {resp.status_code} OK")
        print(f"      authorization_endpoint : {config.get('authorization_endpoint')}")
        print(f"      token_endpoint         : {config.get('token_endpoint')}")
        scopes = config.get("scopes_supported", [])
        for s in ["all-apis", "offline_access"]:
            print(f"      scope '{s}': {'found' if s in scopes else 'MISSING'}")
        print("      Result : PASS")
        return config
    except Exception as e:
        print(f"      Result : FAIL")
        print(f"      Error  : {e}")
        print("      Fix    : verify --workspace-host is correct and reachable.")
        return {}


def check_client_credentials(workspace_host: str, client_id: str, client_secret: str) -> bool:
    url = f"{workspace_host}/oidc/v1/token"
    print(f"\n[2/2] Client Credentials Token Test")
    print(f"      {url}")
    try:
        resp = requests.post(
            url,
            data={"grant_type": "client_credentials", "scope": "all-apis"},
            auth=(client_id, client_secret),
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            print(f"      Result     : PASS")
            print(f"      Token type : {data.get('token_type')}")
            print(f"      Expires in : {data.get('expires_in')} seconds")
            print(f"      Scope      : {data.get('scope')}")
            return True
        else:
            print(f"      Result : FAIL (HTTP {resp.status_code})")
            try:
                err = resp.json()
                print(f"      error             : {err.get('error')}")
                print(f"      error_description : {err.get('error_description')}")
                if "not available in Databricks account" in (err.get("error_description") or ""):
                    print()
                    print("      Note: this Client ID looks like a Databricks App Connection credential,")
                    print("      not a service principal. For connector validation, use a service principal")
                    print("      Client ID. For tools (U2M) validation, use validate_tools_oauth.py.")
            except Exception:
                print(f"      Raw: {resp.text[:300]}")
            return False
    except Exception as e:
        print(f"      Result : FAIL")
        print(f"      Error  : {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Validate Databricks connector (M2M) OAuth credentials for Glean"
    )
    parser.add_argument(
        "--workspace-host",
        required=True,
        help="Databricks workspace URL (e.g. https://dbc-xxxx.cloud.databricks.com)",
    )
    parser.add_argument("--client-id", required=True, help="Service principal Client ID")
    parser.add_argument("--client-secret", required=True, help="Service principal Client Secret")
    args = parser.parse_args()

    host = args.workspace_host.rstrip("/")

    print(SEP)
    print("Databricks Connector OAuth Validation")
    print(SEP)
    print(f"Workspace Host : {host}")
    print(f"Client ID      : {args.client_id}")

    oidc_config = check_oidc_discovery(host)
    creds_ok = check_client_credentials(host, args.client_id, args.client_secret)

    oidc_ok = bool(oidc_config.get("authorization_endpoint"))

    print()
    print(SEP)
    print("Summary")
    print(SEP)
    print(f"  OIDC Discovery     : {'PASS' if oidc_ok else 'FAIL'}")
    print(f"  Client Credentials : {'PASS' if creds_ok else 'FAIL'}")

    if oidc_ok and creds_ok:
        print()
        print("  All checks passed. Connector credentials are valid.")
        print("  To validate Databricks tools credentials, run validate_tools_oauth.py.")
    else:
        print()
        print("  One or more checks failed. See details above.")

    print(SEP)
    sys.exit(0 if (oidc_ok and creds_ok) else 1)


if __name__ == "__main__":
    main()
