import json, urllib.parse, urllib.request
CRED = r"C:\Users\chett\.google_workspace_mcp\credentials\kimonoland.jp1@gmail.com.sheets.json"
c = json.load(open(CRED))
body = urllib.parse.urlencode({"client_id": c["client_id"], "client_secret": c["client_secret"],
    "refresh_token": c["refresh_token"], "grant_type": "refresh_token"}).encode()
tok = json.load(urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token", data=body), timeout=20))["access_token"]
u = "https://sheets.googleapis.com/v4/spreadsheets/1LSQqblDx6ZdumxvrETbP1TBQOKsVAODeSeOu2KaujXQ/values/" + urllib.parse.quote("千栄1568 7月-10月(2026)!A48:AF54")
r = urllib.request.Request(u, headers={"Authorization": "Bearer " + tok})
vals = json.load(urllib.request.urlopen(r, timeout=25)).get("values", [])
for i,row in enumerate(vals, start=48):
    cells = [(k+1, str(v)[:18]) for k, v in enumerate(row) if str(v).strip()]
    print(f"row {i}: {cells}")
