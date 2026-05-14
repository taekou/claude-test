#!/usr/bin/env python3
"""Istio 공식 Grafana 대시보드 설치 스크립트
grafana.com 에서 Istio 전용 대시보드 5종을 다운로드하여 Grafana에 임포트
"""
import urllib.request, json, time

GRAFANA_URL  = "http://admin:admin@localhost:3000"
FOLDER_UID   = "istio-dashboards"
PROM_DS_UID  = "PBFA97CFB590B2093"   # Prometheus (istio-system)

# grafana.com 공식 Istio 대시보드 목록
DASHBOARDS = [
    (7639, "Istio Mesh Dashboard"),
    (7636, "Istio Service Dashboard"),
    (7630, "Istio Workload Dashboard"),
    (7645, "Istio Control Plane Dashboard"),
    (11829, "Istio Performance Dashboard"),
]

def download(uid):
    url = f"https://grafana.com/api/dashboards/{uid}/revisions/latest/download"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read())

def import_dashboard(dash_json, title):
    # datasource 참조를 현재 Prometheus UID로 교체
    raw = json.dumps(dash_json)
    raw = raw.replace('"${DS_PROMETHEUS}"', f'"{PROM_DS_UID}"')
    raw = raw.replace('"${DS_PROMETHEUS_ISTIO}"', f'"{PROM_DS_UID}"')
    raw = raw.replace('"Prometheus"', f'"{PROM_DS_UID}"')
    dash = json.loads(raw)

    dash.pop("id", None)   # id 제거 → Grafana가 자동 할당

    payload = {
        "dashboard":  dash,
        "folderUid":  FOLDER_UID,
        "overwrite":  True,
    }
    body = json.dumps(payload).encode()
    req  = urllib.request.Request(
        f"{GRAFANA_URL}/api/dashboards/import",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

for gid, name in DASHBOARDS:
    print(f"[{gid}] {name} ...", end=" ", flush=True)
    try:
        dash = download(gid)
        result = import_dashboard(dash, name)
        print(f"OK  → {result.get('importedUrl','')}")
    except Exception as e:
        print(f"FAIL: {e}")
    time.sleep(0.5)

print("\n완료! http://localhost:3000/dashboards/f/istio-dashboards/istio")
