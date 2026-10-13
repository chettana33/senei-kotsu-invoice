import json, urllib.parse, urllib.request, sys
CRED = r"C:\Users\chett\.google_workspace_mcp\credentials\kimonoland.jp1@gmail.com.sheets.json"
c = json.load(open(CRED))
body = urllib.parse.urlencode({"client_id": c["client_id"], "client_secret": c["client_secret"],
    "refresh_token": c["refresh_token"], "grant_type": "refresh_token"}).encode()
req = urllib.request.Request("https://oauth2.googleapis.com/token", data=body)
tok = json.load(urllib.request.urlopen(req, timeout=20))["access_token"]
for name, sid in [("AI/ฝึก", "1LSQqblDx6ZdumxvrETbP1TBQOKsVAODeSeOu2KaujXQ"),
                  ("MASTER", "1H2WE2D8ZXrAI4jdOUm2N6DYGCWVD1SrYy9BqAfRFdC0")]:
    u = f"https://sheets.googleapis.com/v4/spreadsheets/{sid}?fields=properties.title,sheets.properties"
    r = urllib.request.Request(u, headers={"Authorization": "Bearer " + tok})
    d = json.load(urllib.request.urlopen(r, timeout=20))
    print("==", name, ":", d["properties"]["title"])
    for s in d["sheets"]:
        p = s["properties"]
        print(f"   tab: {p['title']!r} rows={p['gridProperties'].get('rowCount')} cols={p['gridProperties'].get('columnCount')}")
