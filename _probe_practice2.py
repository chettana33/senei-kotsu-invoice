import json, urllib.parse, urllib.request
CRED = r"C:\Users\chett\.google_workspace_mcp\credentials\kimonoland.jp1@gmail.com.sheets.json"
c = json.load(open(CRED))
body = urllib.parse.urlencode({"client_id": c["client_id"], "client_secret": c["client_secret"],
    "refresh_token": c["refresh_token"], "grant_type": "refresh_token"}).encode()
tok = json.load(urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token", data=body), timeout=20))["access_token"]
def get(sid, rng):
    u = f"https://sheets.googleapis.com/v4/spreadsheets/{sid}/values/{urllib.parse.quote(rng)}"
    r = urllib.request.Request(u, headers={"Authorization": "Bearer " + tok})
    return json.load(urllib.request.urlopen(r, timeout=30)).get("values", [])
AI="1LSQqblDx6ZdumxvrETbP1TBQOKsVAODeSeOu2KaujXQ"
vals = get(AI, "千栄1568 7月-10月(2026)!A1:BZ120")
print("rows:", len(vals), "max cols:", max((len(r) for r in vals), default=0))
# หาหัวเดือนทั้งหมด
for i,row in enumerate(vals,1):
    for j,cell in enumerate(row,1):
        if "2026年" in str(cell):
            print(f"  หัวเดือน: row {i} col {j} = {cell!r}")
# แสดงคอลัมน์ท้าย ๆ ของแถวที่มี 千栄1568
for i,row in enumerate(vals,1):
    if row and str(row[0]).strip()=="千栄1568":
        tail=[(k+1,str(v)[:26]) for k,v in enumerate(row) if str(v).strip()]
        print(f"แถว {i} 千栄1568 · เซลล์ที่ไม่ว่าง {len(tail)} ช่อง · ท้ายสุด: {tail[-8:]}")
