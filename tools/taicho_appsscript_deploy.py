#!/usr/bin/env python3
"""king-bus-taicho — deploy Apps Script Web App (1 ก.ย. 69).

อ่าน tools/appsscript_taicho/{Code.gs,appsscript.json} → updateContent → version → deployment
(executeAs=USER_DEPLOYING, access=ANYONE_ANONYMOUS) → print web app URL.

Token: kimonoland.jp1@gmail.com.script.json (scopes: drive, script.projects,
script.deployments, spreadsheets) — สร้างด้วย oauth flow 1 ก.ย. 69.

Usage:
  python tools/taicho_appsscript_deploy.py            # deploy ใหม่ (version ใหม่ + deployment ใหม่)
  python tools/taicho_appsscript_deploy.py --list     # ดู deployments ที่มี
"""
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

SCRIPT_ID = "149sWUXG6uQxIlH-NMSpKdHgbVEMhchDyo85kjoiFUY6JjjjKWn1yJ-n8"  # สร้างใหม่ผ่าน Scripts API projects.create 1 ก.ย. 69 (Drive API สร้าง ghost 404 — ใช้ไม่ได้)
CRED = r"C:\Users\chett\.google_workspace_mcp\credentials\kimonoland.jp1@gmail.com.script.json"
HERE = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(HERE, "appsscript_taicho")
API = "https://script.googleapis.com/v1"


def get_token():
    with open(CRED, encoding="utf-8") as f:
        c = json.load(f)
    body = urllib.parse.urlencode({
        "client_id": c["client_id"],
        "client_secret": c["client_secret"],
        "refresh_token": c["refresh_token"],
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=body)
    return json.load(urllib.request.urlopen(req, timeout=20))["access_token"]


def api(method, path, token, body=None, timeout=60):
    url = API + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        print(f"HTTP {e.code} {method} {path}: {detail}", file=sys.stderr)
        raise


def update_content(token):
    files = []
    for name in ("Code.gs", "appsscript.json"):
        with open(os.path.join(SRC_DIR, name), encoding="utf-8") as f:
            src = f.read()
        # manifest ต้อง name="appsscript" (ไม่มี .json — ตาม API docs)
        fname = "appsscript" if name == "appsscript.json" else name
        ftype = "SERVER_JS" if name.endswith(".gs") else "JSON"
        files.append({"name": fname, "type": ftype, "source": src})
    return api("PUT", f"/projects/{SCRIPT_ID}/content", token, {"files": files})


def create_version(token, description):
    return api("POST", f"/projects/{SCRIPT_ID}/versions", token, {"description": description})


def list_deployments(token):
    return api("GET", f"/projects/{SCRIPT_ID}/deployments", token)


def create_deployment(token, version_number):
    body = {
        "versionNumber": version_number,
        "description": f"taicho web app v{version_number}",
    }
    return api("POST", f"/projects/{SCRIPT_ID}/deployments", token, body)


def update_deployment(token, dep_id, version_number):
    """PUT deployment เดิม → version ใหม่ (URL เดิมไม่เปลี่ยน — LINE ลิงก์คงเดิม).
    discovery: httpMethod=PUT, request=UpdateDeploymentRequest {deploymentConfig: {...}}"""
    body = {"deploymentConfig": {
        "versionNumber": version_number,
        "description": f"taicho web app v{version_number}",
    }}
    return api("PUT", f"/projects/{SCRIPT_ID}/deployments/{dep_id}", token, body)


def _webapp_url(dep):
    for ep in dep.get("entryPoints", []):
        if ep.get("entryPointType") == "WEB_APP":
            return ep.get("webApp", {}).get("url", "")
    return ""


def main():
    ap = argparse.ArgumentParser(description="deploy taicho Apps Script web app")
    ap.add_argument("--list", action="store_true", help="แสดง deployments ที่มี")
    ap.add_argument("--new", action="store_true",
                    help="สร้าง deployment ใหม่ (default: PATCH deployment เดิม — URL คงที่)")
    args = ap.parse_args()

    tok = get_token()
    if args.list:
        d = list_deployments(tok)
        for dep in d.get("deployments", []):
            print(f"{dep['deploymentId']}  {dep.get('updateTime', '')}  {_webapp_url(dep)}")
        return

    print("1/3 updateContent ...")
    update_content(tok)
    print("2/3 create version ...")
    v = create_version(tok, f"taicho web app (1 ก.ย. 69)")
    vnum = v["versionNumber"]
    print(f"    version {vnum}")

    deps = list_deployments(tok).get("deployments", [])
    web_deps = [d for d in deps if _webapp_url(d)]
    if args.new or not web_deps:
        print("3/3 create deployment (new) ...")
        d = create_deployment(tok, vnum)
    else:
        # เลือก deployment ล่าสุด (updateTime สูงสุด) — URL เดิมคงที่
        web_deps.sort(key=lambda x: x.get("updateTime", ""))
        dep_id = web_deps[-1]["deploymentId"]
        print(f"3/3 update deployment {dep_id} (URL เดิมคงที่) ...")
        d = update_deployment(tok, dep_id, vnum)
    dep_id = d["deploymentId"]
    url = _webapp_url(d)
    print(f"DEPLOYMENT_ID={dep_id}")
    print(f"URL={url}")
    if url:
        print("TEST: เปิด URL ในเบราว์เซอร์ ดู emoji 🟡🟢🔷 + ปุ่ม print")


if __name__ == "__main__":
    main()
