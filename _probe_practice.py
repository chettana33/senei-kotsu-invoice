import json, urllib.parse, urllib.request
CRED = r"C:\Users\chett\.google_workspace_mcp\credentials\kimonoland.jp1@gmail.com.sheets.json"
c = json.load(open(CRED))
body = urllib.parse.urlencode({"client_id": c["client_id"], "client_secret": c["client_secret"],
    "refresh_token": c["refresh_token"], "grant_type": "refresh_token"}).encode()
tok = json.load(urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token", data=body), timeout=20))["access_token"]
def get(sid, rng):
    u = f"https://sheets.googleapis.com/v4/spreadsheets/{sid}/values/{urllib.parse.quote(rng)}"
    r = urllib.request.Request(u, headers={"Authorization": "Bearer " + tok})
    return json.load(urllib.request.urlopen(r, timeout=25)).get("values", [])
AI="1LSQqblDx6ZdumxvrETbP1TBQOKsVAODeSeOu2KaujXQ"; M="1H2WE2D8ZXrAI4jdOUm2N6DYGCWVD1SrYy9BqAfRFdC0"
print("=== AI sheet: tab '千栄1568 7月-10月(2026)' แถว 1-12, คอลัมน์ 1-15 ===")
for i,row in enumerate(get(AI, "千栄1568 7月-10月(2026)!A1:O12"),1):
    print(i, [x[:22] for x in row])
print("=== MASTER: tab '千栄1568 10月-1月(2027)' แถว 1-8, คอลัมน์ 1-10 ===")
for i,row in enumerate(get(M, "千栄1568 10月-1月(2027)!A1:J8"),1):
    print(i, [x[:22] for x in row])
