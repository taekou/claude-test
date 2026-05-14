#!/usr/bin/env python3
"""Istio 공식 대시보드를 grafana.yaml에서 추출하여 Grafana에 임포트"""
import yaml, json, urllib.request, urllib.error

GRAFANA_URL  = "http://localhost:3000"
GRAFANA_AUTH = "Basic YWRtaW46YWRtaW4="  # admin:admin base64
FOLDER_UID   = "istio-dashboards"
PROM_DS_UID  = "PBFA97CFB590B2093"   # Prometheus (istio-system)
GRAFANA_YAML = "/home/devops/istio-1.27.1/samples/addons/grafana.yaml"

def import_dashboard(dash_json_str, fname):
    # datasource 변수 → 실제 UID 치환
    raw = dash_json_str
    raw = raw.replace('"${datasource}"', f'{{"type":"prometheus","uid":"{PROM_DS_UID}"}}')
    raw = raw.replace('"${DS_PROMETHEUS}"', f'"{PROM_DS_UID}"')
    try:
        dash = json.loads(raw)
    except json.JSONDecodeError as e:
        return False, f"JSON parse error: {e}"

    dash.pop("id", None)

    payload = json.dumps({
        "dashboard": dash,
        "folderUid": FOLDER_UID,
        "overwrite":  True,
    }).encode()

    req = urllib.request.Request(
        f"{GRAFANA_URL}/api/dashboards/import",
        data=payload,
        headers={"Content-Type": "application/json",
                 "Authorization": GRAFANA_AUTH},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            result = json.loads(r.read())
            return True, result.get("importedUrl", result.get("slug", ""))
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return False, f"HTTP {e.code}: {body[:120]}"

with open(GRAFANA_YAML) as f:
    docs = list(yaml.safe_load_all(f))

dashboard_files = {}
for doc in docs:
    if doc and doc.get("kind") == "ConfigMap" and "dashboard" in doc["metadata"]["name"]:
        for key, val in doc.get("data", {}).items():
            if key.endswith(".json"):
                dashboard_files[key] = val

print(f"추출된 대시보드: {len(dashboard_files)}개\n")

for fname, content in sorted(dashboard_files.items()):
    label = fname.replace(".json", "").replace("-", " ").title()
    print(f"  [{label}] ...", end=" ", flush=True)
    ok, msg = import_dashboard(content, fname)
    print(f"{'OK' if ok else 'FAIL'}  {msg}")

print(f"\n완료! http://localhost:3000/dashboards/f/istio-dashboards/istio")
