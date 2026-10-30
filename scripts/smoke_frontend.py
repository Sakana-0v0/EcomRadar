"""Frontend 挂载验证 smoke test."""
import sys
sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

r = client.get("/")
has_root = 'id="root"' in r.text
print(f"GET /            -> {r.status_code} | react root div: {has_root}")

r2 = client.get("/api/v1/meta")
print(f"GET /api/v1/meta -> {r2.status_code} | {r2.json()}")

r3 = client.get("/api/v1/health")
print(f"GET /api/v1/health -> {r3.status_code} | {r3.json()}")

# assets 挂载
import re
m = re.search(r'/assets/[A-Za-z0-9_\-]+\.js', r.text)
if m:
    ra = client.get(m.group(0))
    print(f"GET {m.group(0)[:28]}... -> {ra.status_code} | {len(ra.content)} bytes")
