#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""เทสต์ cgman-monitor: กัน "เมลเดิมถูกสแกนซ้ำ → ไฟล์ซ้ำ + แจ้งเตือนซ้ำ" (13 พ.ย. 69 · มติพี่เจ "ลุย A")

ครอบสิ่งที่ review มุมคนนอกจับได้: ① state อัปเดตต้องเป็น PATCH ② md5Checksum ขาด = fail-closed
③ attachment ซ้อนชั้น multipart ④ attachment ชื่อซ้ำในรอบเดียว

รัน: python tools\\test_cgman_monitor_state.py
ไม่ยิงเน็ต/ไม่แตะ Drive จริง — แทนที่ฟังก์ชันชั้นล่างด้วยของปลอมในหน่วยความจำ
"""
import base64
import datetime
import hashlib
import importlib.util
import json
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(HERE, "..", "cloud-functions", "cgman-monitor", "main.py")
RESULTS = []


def install_firebase_stubs():
    """firebase_functions ไม่ได้ติดตั้งในเครื่องนี้ — ใส่ stub ให้ import ผ่าน"""
    pkg = types.ModuleType("firebase_functions")
    pkg.https_fn = types.SimpleNamespace(on_request=lambda **kw: (lambda f: f),
                                         Response=lambda *a, **k: None)
    opt = types.ModuleType("firebase_functions.options")
    opt.SupportedRegion = types.SimpleNamespace(ASIA_SOUTHEAST1="asia-southeast1")
    pkg.options = opt
    sys.modules["firebase_functions"] = pkg
    sys.modules["firebase_functions.options"] = opt


def load_module():
    install_firebase_stubs()
    spec = importlib.util.spec_from_file_location("cgman_main", MAIN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Fake:
    """Drive + Gmail ปลอม: drive = {folder: {name: bytes}} · msgs = {msg_id: (internalDate_ms, [parts])}"""

    def __init__(self, mod, msgs, drive=None, state=None, no_md5=False, meta_no_size=False):
        self.m = mod
        self.msgs = msgs
        self.drive = drive if drive is not None else {}
        self.state = state if state is not None else {}
        self.no_md5 = no_md5
        self.meta_no_size = meta_no_size
        self.uploads = []
        self.lines = []

        mod.refresh_access_token = lambda: "TOKEN"
        mod.resolve_folder = lambda parts, token: "FOLDER"
        mod._get = self.fake_get
        mod.drive_file_meta = self.fake_meta
        mod.drive_file_exists = lambda folder, name, tok: name in self.drive.get(folder, {})
        mod.drive_file_id = lambda folder, name, tok: (
            f"id-{name}" if name in self.drive.get(folder, {}) else None)
        mod.load_state = lambda folder, tok: dict(self.state)
        mod.save_state = self.fake_save_state
        mod.upload_to_drive = self.fake_upload
        mod.send_line = lambda text: self.lines.append(text)

    # ---- fakes ----
    def fake_get(self, url, token):
        if "/messages?" in url:
            return {"messages": [{"id": k} for k in self.msgs]}
        for mid, (dt_ms, parts) in self.msgs.items():
            if url.endswith(f"/messages/{mid}?format=full"):
                return {"internalDate": str(dt_ms), "payload": {"parts": parts}}
            for p in walk(parts):
                if url.endswith(f"/messages/{mid}/attachments/{p['body']['attachmentId']}"):
                    return {"data": base64.urlsafe_b64encode(p["bytes"]).decode()}
        raise AssertionError(f"unexpected GET {url}")

    def fake_meta(self, folder, name, token):
        data = self.drive.get(folder, {}).get(name)
        if data is None:
            return None
        return {"id": f"id-{name}",
                "size": None if self.meta_no_size else str(len(data)),
                "md5Checksum": None if self.no_md5 else hashlib.md5(data).hexdigest()}

    def fake_save_state(self, folder, state, token):
        self.state = dict(state)
        return True

    def fake_upload(self, folder, name, data, token):
        self.drive.setdefault(folder, {})[name] = data
        self.uploads.append(name)
        return {"name": name, "id": f"new-{name}"}


def walk(parts):
    for p in parts:
        if p.get("parts"):
            yield from walk(p["parts"])
        else:
            yield p


FORM = "1113_千栄交通㈱_貸切バス手配依頼書.xlsx"


def parts_for(data, name=FORM):
    return [{"filename": name, "body": {"attachmentId": "A1", "size": len(data)}, "bytes": data}]


def nested_parts_for(data, name=FORM):
    """เมลจริงมักซ้อน multipart/mixed → multipart/related (โค้ดเดิมอ่านชั้นเดียว = ใบหาย)"""
    inner = {"filename": name, "body": {"attachmentId": "A2", "size": len(data)}, "bytes": data}
    return [{"filename": "", "parts": [{"filename": "", "parts": [inner]}]}]


def msg_dt(y=2026, mo=11, d=13):
    return int(datetime.datetime(y, mo, d, 16, 40).timestamp() * 1000)


def check(label, cond, extra=""):
    RESULTS.append(bool(cond))
    print(f"{'PASS' if cond else 'FAIL'} {label} {extra}".rstrip())
    return cond


def main() -> int:
    mod = load_module()
    SAVE_STATE = mod.save_state      # เก็บของจริงไว้ก่อน Fake จะทับ
    REAL_META = mod.drive_file_meta  # ใช้ทดสอบ URL จริงใน T13 (Fake ทับฟังก์ชันนี้)
    content = b"xlsx-v1-content"
    later = b"xlsx-v2-content-longer"
    alt_name = "1113_千栄交通㈱_貸切バス手配依頼書(1113).xlsx"

    # T1: เมลใหม่ → อัปโหลด 1 ไฟล์ + แจ้ง 1 ครั้ง + จด state
    f = Fake(mod, {"M1": (msg_dt(), parts_for(content))})
    n = f.m.run()
    check("T1 รอบแรก: อัปโหลด 1 ไฟล์", n == 1 and f.uploads == [FORM], str(f.uploads))
    check("T1 แจ้ง LINE 1 ครั้ง", len(f.lines) == 1)
    check("T1 จด state = วันนี้", f.state.get("M1") == datetime.date.today().isoformat(), str(f.state))

    # T2: รอบที่ 2 ของเมลเดิม (เคสจริง 16:40 → 16:45) → ต้องไม่เกิดไฟล์/ข้อความใหม่
    n2 = f.m.run()
    check("T2 สแกนซ้ำ: อัปโหลดเพิ่ม 0", n2 == 0, str(f.uploads))
    check("T2 สแกนซ้ำ: ไม่แจ้ง LINE ซ้ำ", len(f.lines) == 1)

    # T3: Drive มีไฟล์ชื่อนี้ เนื้อเดียวกัน แต่ state ว่าง → ต้องข้าม (size+md5Checksum guard)
    f3 = Fake(mod, {"M9": (msg_dt(), parts_for(content))}, drive={"FOLDER": {FORM: content}})
    n3 = f3.m.run()
    check("T3 เนื้อเหมือนเดิม: อัปโหลด 0", n3 == 0, str(f3.uploads))
    check("T3 ไม่แจ้ง LINE", len(f3.lines) == 0)
    check("T3 ยังจด state กันวนซ้ำ", f3.state.get("M9") == datetime.date.today().isoformat())

    # T4: 千栄 ส่งชื่อเดิมแต่เนื้อใหม่จริง (ขนาดต่าง) → เก็บเป็น alt + แจ้ง 1 ครั้ง
    f4 = Fake(mod, {"M2": (msg_dt(), parts_for(later))}, drive={"FOLDER": {FORM: content}})
    n4 = f4.m.run()
    check("T4 เนื้อใหม่: อัปโหลด 1 ไฟล์เป็น alt", n4 == 1 and f4.uploads == [alt_name], str(f4.uploads))
    check("T4 แจ้ง LINE 1 ครั้ง", len(f4.lines) == 1)

    # T5: md5Checksum ขาด + ขนาดเท่า ⇒ fail-closed (ข้ามรอบนี้ ไม่จด state ไม่แจ้ง)
    f5 = Fake(mod, {"M5": (msg_dt(), parts_for(content))}, drive={"FOLDER": {FORM: content}}, no_md5=True)
    n5 = f5.m.run()
    check("T5 md5 ขาด: ไม่สร้างสำเนา", n5 == 0 and f5.uploads == [])
    check("T5 md5 ขาด: ไม่จด state (ลองใหม่รอบหน้า)", "M5" not in f5.state, str(f5.state))

    # T6: attachment ซ้อน multipart 2 ชั้น → ต้องเห็นและอัปโหลด (เดิมอ่านชั้นเดียว = ใบหาย)
    f6 = Fake(mod, {"M6": (msg_dt(), nested_parts_for(content))})
    n6 = f6.m.run()
    check("T6 attachment ซ้อนชั้น: อัปโหลด 1 ไฟล์", n6 == 1 and f6.uploads == [FORM], str(f6.uploads))

    # T7: save_state อัปเดตไฟล์เดิม = PATCH (Critical จาก review) + ตัด entry เก่า > 60 วัน
    today = datetime.date.today()
    stale = (today - datetime.timedelta(days=90)).isoformat()
    fresh = today.isoformat()
    sent = {}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b""

    def fake_urlopen(req, timeout=0):
        body = req.data.decode("utf-8")
        cand = body.split("\r\n\r\n")[-1].rsplit("\r\n--", 1)[0]
        sent.update(json.loads(cand))
        sent["_method"] = req.get_method()
        sent["_url"] = req.full_url
        return _Resp()

    real_drive_id, real_urlopen = mod.drive_file_id, mod.urlopen
    mod.drive_file_id = lambda folder, name, tok: "id-STATE"   # มีไฟล์เดิม = ทางอัปเดต
    mod.urlopen = fake_urlopen
    ok_ret = SAVE_STATE("FOLDER", {"OLD": stale, "NEW": fresh}, "TOKEN")
    mod.drive_file_id, mod.urlopen = real_drive_id, real_urlopen
    check("T7 state อัปเดตใช้ PATCH", sent.get("_method") == "PATCH", str(sent.get("_method")))
    check("T7 state อัปเดตยิงไป upload/files/{id}", "/upload/drive/v3/files/id-STATE" in sent.get("_url", ""),
          str(sent.get("_url")))
    check("T7 state ตัดของเก่า > 60 วัน", ok_ret and "NEW" in sent and "OLD" not in sent,
          str({k: v for k, v in sent.items() if not k.startswith("_")}))

    # T8: attachment ชื่อซ้ำในเมลเดียว เนื้อต่าง → อัปโหลดได้ตัวเดียว ไม่จด state (ให้คนตรวจ)
    f8 = Fake(mod, {"M8": (msg_dt(), parts_for(content) + [
        {"filename": FORM, "body": {"attachmentId": "A9", "size": len(later)}, "bytes": later}])})
    n8 = f8.m.run()
    check("T8 ชื่อซ้ำในเมลเดียว: อัปโหลดแค่ 1", n8 == 1, str(f8.uploads))
    check("T8 ชื่อซ้ำในเมลเดียว: ไม่จด state", "M8" not in f8.state, str(f8.state))

    # T9: ขนาดเท่ากันแต่เนื้อต่าง (md5Checksum ต่าง) → ต้องเก็บเป็น alt (ทาง md5 จริง)
    same_len = b"xlsx-v1-contenX"          # ยาวเท่า content (15 B) แต่เนื้อต่าง
    assert len(same_len) == len(content)
    f9 = Fake(mod, {"MA": (msg_dt(), parts_for(same_len))}, drive={"FOLDER": {FORM: content}})
    n9 = f9.m.run()
    check("T9 ขนาดเท่า/เนื้อต่าง: อัปโหลดเป็น alt", n9 == 1 and f9.uploads == [alt_name], str(f9.uploads))

    # T10: metadata ของ Drive ไม่มี size → fail-closed (ห้ามเดาว่าเนื้อใหม่)
    f10 = Fake(mod, {"MB": (msg_dt(), parts_for(content))},
               drive={"FOLDER": {FORM: content}}, meta_no_size=True)
    n10 = f10.m.run()
    check("T10 size ของไฟล์เดิมหาย: ไม่สร้างสำเนา", n10 == 0 and f10.uploads == [])
    check("T10 size ของไฟล์เดิมหาย: ไม่จด state", "MB" not in f10.state)

    # T11: load_state พัง (JSON เสีย) → run() ต้องหยุด ไม่สแกน/ไม่อัปโหลด
    f11 = Fake(mod, {"MC": (msg_dt(), parts_for(content))})
    real_load, real_send = mod.load_state, mod.send_line
    mod.load_state = lambda folder, tok: (_ for _ in ()).throw(RuntimeError("state corrupt"))
    mod.send_line = lambda text: f11.lines.append(text)
    raised = False
    try:
        f11.m.run()
    except RuntimeError:
        raised = True
    mod.load_state, mod.send_line = real_load, real_send
    check("T11 state เสีย: โยน error ไม่สแกนต่อ", raised and f11.uploads == [])
    check("T11 state เสีย: มีแจ้งเตือน LINE", len(f11.lines) == 1, str(f11.lines))

    # T12: 2 เมลในรอบเดียว ชื่อฐานเดียวกัน เนื้อต่าง → ห้ามได้ 2 ไฟล์ชื่อเดียวกัน
    f12 = Fake(mod, {"MD": (msg_dt(), parts_for(content)), "ME": (msg_dt(), parts_for(later))})
    n12 = f12.m.run()
    check("T12 ชื่อชนกันในรอบเดียว: ได้ไฟล์เดียว", n12 == 1 and len(f12.uploads) == 1, str(f12.uploads))
    check("T12 ชื่อชนกันในรอบเดียว: เมลที่ 2 ไม่ถูกจด state", "ME" not in f12.state, str(f12.state))

    # T13: URL ของ drive_file_meta ต้องไม่มีช่องว่างดิบ ๆ — บั๊กจริงที่เจอ "หลัง deploy" 13 พ.ย. 69
    # (เทสต์เดิมจับไม่ได้เพราะ Fake ทับ drive_file_meta ทั้งฟังก์ชัน ⇒ รอบนี้ยิงฟังก์ชันจริงแต่ดัก _get)
    real_get = mod._get
    seen_url = {}

    def fake_get_url(url, token):
        seen_url["url"] = url
        return {"files": []}

    mod._get = fake_get_url
    REAL_META("FOLDER", "x.xlsx", "T")
    mod._get = real_get
    u = seen_url.get("url", "")
    check("T13 drive_file_meta: URL ไม่มีช่องว่าง/อักขระควบคุม",
          bool(u) and not any(ch.isspace() for ch in u), u[:90])
    check("T13 drive_file_meta: orderBy ถูก encode",
          "orderBy=modifiedTime%20desc" in u, u[-40:])
    check("T13 drive_file_meta: ขอ size+md5Checksum ด้วย",
          "md5Checksum" in u and "size" in u, "")

    passed = sum(1 for r in RESULTS if r)
    print(f"\n{'ALL PASS' if passed == len(RESULTS) else 'มีข้อตก'} · {passed}/{len(RESULTS)} ข้อ")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
