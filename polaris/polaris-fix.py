#!/usr/bin/env python3
"""Polaris Danger/Warning 항목 일괄 수정 스크립트"""

import subprocess, json, sys

OK = []; FAIL = []

def run(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return r.returncode, r.stdout.strip(), r.stderr.strip()

def patch(kind, name, ns, data, ptype='strategic'):
    p = json.dumps(data)
    code, out, err = run(f"kubectl patch {kind} {name} -n {ns} --type={ptype} -p '{p}'")
    label = f"{ns}/{kind}/{name}"
    if code == 0:
        print(f"  [OK] {label}")
        OK.append(label)
    else:
        print(f"  [FAIL] {label}: {err[:120]}")
        FAIL.append(f"{label}: {err[:80]}")
    return code == 0

def apply(yaml_str):
    r = subprocess.run(['kubectl', 'apply', '-f', '-'], input=yaml_str,
                       capture_output=True, text=True)
    if r.returncode == 0:
        print(f"  [OK] apply: {r.stdout.strip()}")
    else:
        print(f"  [FAIL] apply: {r.stderr.strip()[:120]}")
    return r.returncode == 0

def sec_ctx(allow_esc=False, nonroot=True, drop_caps=True, seccomp=True):
    ctx = {"allowPrivilegeEscalation": allow_esc}
    if nonroot:
        ctx["runAsNonRoot"] = True
    if drop_caps:
        ctx["capabilities"] = {"drop": ["ALL"]}
    if seccomp:
        ctx["seccompProfile"] = {"type": "RuntimeDefault"}
    return ctx

def tcp_probe(port, delay=10, period=15):
    return {"tcpSocket": {"port": port},
            "initialDelaySeconds": delay, "periodSeconds": period,
            "failureThreshold": 3}

def http_probe(path, port, delay=10, period=15):
    return {"httpGet": {"path": path, "port": port},
            "initialDelaySeconds": delay, "periodSeconds": period,
            "failureThreshold": 3}

def container_patch(name, sec, resources=None, liveness=None, readiness=None, pull="Always"):
    c = {"name": name, "imagePullPolicy": pull, "securityContext": sec}
    if resources:
        c["resources"] = resources
    if liveness:
        c["livenessProbe"] = liveness
    if readiness:
        c["readinessProbe"] = readiness
    return c

def deployment_patch(containers, replicas=None, labels=None):
    spec = {"containers": containers}
    tmpl = {"spec": spec}
    if labels:
        tmpl["metadata"] = {"labels": labels}
    p = {"spec": {"template": tmpl}}
    if replicas is not None:
        p["spec"]["replicas"] = replicas
    return p

def pdb_yaml(name, ns, app_label, min_available=1):
    return f"""apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: {name}-pdb
  namespace: {ns}
spec:
  minAvailable: {min_available}
  selector:
    matchLabels:
      app: {app_label}
"""

# ─────────────────────────────────────────────
# 1. Sensitive Env Var → Kubernetes Secret
# ─────────────────────────────────────────────
print("\n[1/8] Sensitive Env Var → Secret 변환")

apply("""apiVersion: v1
kind: Secret
metadata:
  name: skywalking-es-credentials
  namespace: skywalking
type: Opaque
stringData:
  username: "xxx"
  password: "xxx"
""")

oap_secret_patch = {
    "spec": {"template": {"spec": {"containers": [{
        "name": "oap",
        "env": [
            {"name": "SW_ES_USER",
             "valueFrom": {"secretKeyRef": {"name": "skywalking-es-credentials", "key": "username"}}},
            {"name": "SW_ES_PASSWORD",
             "valueFrom": {"secretKeyRef": {"name": "skywalking-es-credentials", "key": "password"}}}
        ]
    }]}}}
}
patch("deployment", "skywalking-oap", "skywalking", oap_secret_patch)

# ─────────────────────────────────────────────
# 2. default namespace - Bookinfo
# ─────────────────────────────────────────────
print("\n[2/8] default namespace - Bookinfo 보안 강화")

bookinfo_res = {"requests": {"cpu": "50m", "memory": "64Mi"},
                "limits":   {"cpu": "200m", "memory": "256Mi"}}

for deploy, cname, port, replicas in [
    ("details-v1",    "details",     9080, 2),
    ("productpage-v1","productpage", 9080, 2),
    ("ratings-v1",    "ratings",     9080, 2),
    ("reviews-v1",    "reviews",     9080, 2),
    ("reviews-v2",    "reviews",     9080, 2),
    ("reviews-v3",    "reviews",     9080, 2),
]:
    p = deployment_patch(
        containers=[container_patch(
            cname, sec_ctx(),
            resources=bookinfo_res,
            liveness=tcp_probe(port),
            readiness=tcp_probe(port, delay=5, period=10),
        )],
        replicas=replicas,
        labels={"app.kubernetes.io/instance": deploy}
    )
    patch("deployment", deploy, "default", p)

# httpbin
patch("deployment", "httpbin", "default", deployment_patch(
    containers=[container_patch(
        "httpbin", sec_ctx(),
        resources=bookinfo_res,
        liveness=http_probe("/status/200", 8080),
        readiness=http_probe("/status/200", 8080, delay=5),
    )],
    replicas=2,
    labels={"app.kubernetes.io/instance": "httpbin"}
))

# fortio
patch("deployment", "fortio-deploy", "default", deployment_patch(
    containers=[container_patch(
        "fortio", sec_ctx(),
        resources=bookinfo_res,
        liveness=http_probe("/fortio/", 8080),
        readiness=http_probe("/fortio/", 8080, delay=5),
    )],
    labels={"app.kubernetes.io/instance": "fortio-deploy"}
))

# ─────────────────────────────────────────────
# 3. default namespace - Kafka producer/consumer
# ─────────────────────────────────────────────
print("\n[3/8] default namespace - Kafka producer/consumer")

for deploy, cname in [("kafka-consumer", "kafka-consumer"), ("kafka-producer", "kafka-producer")]:
    patch("deployment", deploy, "default", deployment_patch(
        containers=[container_patch(cname, sec_ctx())],
        labels={"app.kubernetes.io/instance": deploy}
    ))

# ─────────────────────────────────────────────
# 4. kafka namespace
# ─────────────────────────────────────────────
print("\n[4/8] kafka namespace")

patch("statefulset", "kafka", "kafka", {
    "spec": {"template": {"spec": {"containers": [
        container_patch("kafka", sec_ctx(nonroot=False))  # kafka may need root
    ]}}}
})

# ─────────────────────────────────────────────
# 5. skywalking namespace
# ─────────────────────────────────────────────
print("\n[5/8] skywalking namespace")

sw_res = {"requests": {"cpu": "50m", "memory": "128Mi"},
          "limits":   {"cpu": "500m", "memory": "512Mi"}}

patch("deployment", "banyandb", "skywalking", deployment_patch(
    containers=[container_patch(
        "banyandb", sec_ctx(),
        liveness=tcp_probe(17913),
        readiness=tcp_probe(17913, delay=15),
    )],
    labels={"app.kubernetes.io/instance": "banyandb"}
))

patch("deployment", "otel-collector", "skywalking", deployment_patch(
    containers=[container_patch(
        "otel-collector", sec_ctx(),
        liveness=tcp_probe(4317, delay=15),
        readiness=tcp_probe(4317, delay=10),
    )],
    labels={"app.kubernetes.io/instance": "otel-collector"}
))

patch("deployment", "skywalking-oap", "skywalking", deployment_patch(
    containers=[container_patch(
        "oap", sec_ctx(),
        resources={"requests": {"cpu": "250m", "memory": "512Mi"},
                   "limits":   {"cpu": "2",    "memory": "2Gi"}},
    )],
    labels={"app.kubernetes.io/instance": "skywalking-oap"}
))

patch("deployment", "skywalking-ui", "skywalking", deployment_patch(
    containers=[container_patch(
        "ui", sec_ctx(),
        resources=sw_res,
        liveness=http_probe("/", 8080, delay=20),
        readiness=http_probe("/", 8080, delay=15),
    )],
    labels={"app.kubernetes.io/instance": "skywalking-ui"}
))

# ─────────────────────────────────────────────
# 6. vm-nginx namespace
# ─────────────────────────────────────────────
print("\n[6/8] vm-nginx namespace")

patch("deployment", "vm-nginx", "vm-nginx", deployment_patch(
    containers=[
        container_patch(
            "nginx", sec_ctx(nonroot=False),  # nginx needs root for port 80
            liveness=http_probe("/", 80, delay=10),
            readiness=http_probe("/", 80, delay=5),
        ),
        container_patch("kafka-producer", sec_ctx()),
    ],
    labels={"app.kubernetes.io/instance": "vm-nginx"}
))

# ─────────────────────────────────────────────
# 7. kube-system (user-managed addons)
# ─────────────────────────────────────────────
print("\n[7/8] kube-system addons")

patch("deployment", "kube-state-metrics", "kube-system", deployment_patch(
    containers=[container_patch(
        "kube-state-metrics", sec_ctx(),
        resources={"requests": {"cpu": "50m", "memory": "64Mi"},
                   "limits":   {"cpu": "200m", "memory": "256Mi"}},
    )],
    labels={"app.kubernetes.io/instance": "kube-state-metrics"}
))

patch("deployment", "metrics-server", "kube-system", deployment_patch(
    containers=[container_patch(
        "metrics-server", sec_ctx(),
        resources={"requests": {"cpu": "100m", "memory": "200Mi"},
                   "limits":   {"cpu": "500m", "memory": "512Mi"}},
    )],
    labels={"app.kubernetes.io/instance": "metrics-server"}
))

patch("deployment", "local-path-provisioner", "local-path-storage", deployment_patch(
    containers=[container_patch(
        "local-path-provisioner", sec_ctx(),
        resources={"requests": {"cpu": "50m", "memory": "64Mi"},
                   "limits":   {"cpu": "200m", "memory": "256Mi"}},
        liveness=None, readiness=None,
    )],
    labels={"app.kubernetes.io/instance": "local-path-provisioner"}
))

# ─────────────────────────────────────────────
# 8. PodDisruptionBudget 생성
# ─────────────────────────────────────────────
print("\n[8/8] PodDisruptionBudget 생성")

pdb_targets = [
    ("details-v1",            "default",         "details"),
    ("productpage-v1",        "default",         "productpage"),
    ("ratings-v1",            "default",         "ratings"),
    ("reviews-v1",            "default",         "reviews"),
    ("reviews-v2",            "default",         "reviews"),
    ("reviews-v3",            "default",         "reviews"),
    ("httpbin",               "default",         "httpbin"),
    ("fortio-deploy",         "default",         "fortio"),
    ("kafka-consumer",        "default",         "kafka-consumer"),
    ("kafka-producer",        "default",         "kafka-producer"),
    ("banyandb",              "skywalking",      "banyandb"),
    ("otel-collector",        "skywalking",      "otel-collector"),
    ("skywalking-oap",        "skywalking",      "skywalking-oap"),
    ("skywalking-ui",         "skywalking",      "skywalking-ui"),
    ("vm-nginx",              "vm-nginx",        "vm-nginx"),
    ("kube-state-metrics",    "kube-system",     "kube-state-metrics"),
    ("metrics-server",        "kube-system",     "metrics-server"),
    ("local-path-provisioner","local-path-storage","local-path-provisioner"),
]

for name, ns, app in pdb_targets:
    apply(pdb_yaml(name, ns, app))

# ─────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────
print(f"\n{'='*50}")
print(f"완료: {len(OK)}건 성공 / {len(FAIL)}건 실패")
if FAIL:
    print("실패 목록:")
    for f in FAIL:
        print(f"  - {f}")
