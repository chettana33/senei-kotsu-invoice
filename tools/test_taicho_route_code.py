"""เทสต์ route_code/d2_text — รหัสทิศทาง ホ/空 (มติพี่เจ 5 พ.ย. 69)

เคสจริงที่ทำให้ต้องแก้: ใบ 1104/1105 行先 = `湯楽城HTL` (ชื่อโรงแรม) ⇒ เดิมแปลงไม่ได้
→ ทิ้งทั้ง 2 รหัส → ช่อง 11月14 กลายเป็น `13:35 2H` ไม่มี 空/ホ
รัน: python tools/test_taicho_route_code.py
"""
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import taicho_gsheets as tg

ok = fail = 0


def check(name, got, want):
    global ok, fail
    if got == want:
        ok += 1
    else:
        fail += 1
        print(f"FAIL {name}: got {got!r} want {want!r}")


# --- route_code ---
for v, want in [("HTL", "ホ"), ("AP1", "空"), ("AP2", "空"),
                ("ap2", "空"), (" HTL ", "ホ"),
                ("湯楽城HTL", "ホ"), ("ゆらくじょうホテル", "ホ"),
                ("アパホテル成田", "ホ"), ("NARITA HOTEL", "ホ"),
                ("湯楽城", None), ("", None), (None, None), ("東京駅", None)]:
    check(f"route_code({v!r})", tg.route_code(v), want)

# --- d2_text ---
cases = [
    ("เคสจริง 11/14 (AP2 → 湯楽城HTL)", {"t": "13:35", "h": "2H", "D": "AP2", "G": "湯楽城HTL"},
     "空 13:35 2H ホ"),
    ("HTL → AP2", {"t": "06:00", "h": None, "D": "HTL", "G": "AP2"}, "ホ 06:00 空"),
    ("AP2 → HTL + 1H", {"t": "13:00", "h": "1H", "D": "AP2", "G": "HTL"}, "空 13:00 1H ホ"),
    ("ไม่มีรหัสทั้งคู่ = คงแบบเดิม", {"t": "10:00", "h": "2H", "D": "", "G": ""}, "10:00 2H"),
    ("ชื่อที่ไม่รู้จักข้างเดียว", {"t": "10:00", "h": "2H", "D": "東京駅", "G": "AP2"}, "10:00 2H"),
]
for name, entry, want in cases:
    check("d2_text " + name, tg.d2_text(entry), want)

print(f"\n{'PASS' if fail == 0 else 'FAIL'} {ok}/{ok + fail}")
sys.exit(1 if fail else 0)
