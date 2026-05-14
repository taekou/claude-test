#!/usr/bin/env python3
"""Polaris 2차 수정 - 남은 Warning 항목"""

import subprocess, json

def run(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return r.returncode, r.stdout.strip(), r.stderr.strip()

def patch(kind, name, ns, data, ptype='strategic'):
    p = json.dumps(data)
    code, out, err = run(f"kubectl patch {kind} {name} -n {ns} --type={ptype} -p '{p}'")
    print(f"  {'OK' if code==0 else 'FAIL'}: {ns}/{kind}/{name}" + (f" - {err[:80]}" if code!=0 else ""))
    return code == 0

def apply(yaml_str):
    r = subprocess.run(['kubectl', 'apply', '-f', '-'], input=yaml_str, capture_output=True, text=True)
    status = r.stdout.strip() or r.stderr.strip()[:80]
    print(f"  {'OK' if r.returncode==0 else 'FAIL'}: {status}")
    return r.returncode == 0

def container_patch_minimal(name, pull="Always", resources=None, liveness=None, readiness=None, sc=None):
    c = {"name": name, "imagePullPolicy": pull}
    if resources: c["resources"] = resources
    if liveness:  c["livenessProbe"] = liveness
    if readiness: c["readinessProbe"] = readiness
    if sc:        c["securityContext"] = sc
    return c

def tcp_probe(port, delay=10, period=15):
    return {"tcpSocket": {"port": port}, "initialDelaySeconds": delay,
            "periodSeconds": period, "failureThreshold": 3}

def http_probe(path, port, delay=10, period=15):
    return {"httpGet": {"path": path, "port": port}, "initialDelaySeconds": delay,
            "periodSeconds": period, "failureThreshold": 3}

def pdb_yaml(name, ns, selector_key, selector_val, min_available=1):
    return f"""apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: {name}-pdb
  namespace: {ns}
spec:
  minAvailable: {min_available}
  selector:
    matchLabels:
      {selector_key}: {selector_val}
"""

print("\n[1/5] metadataAndInstanceMismatched 레이블 수정")

label_targets = [
    # (kind, name, ns, instance-value)
    ("deployment",  "details-v1",            "default",            "details-v1"),
    ("deployment",  "fortio-deploy",          "default",            "fortio-deploy"),
    ("deployment",  "httpbin",                "default",            "httpbin"),
    ("deployment",  "kafka-consumer",         "default",            "kafka-consumer"),
    ("deployment",  "kafka-producer",         "default",            "kafka-producer"),
    ("deployment",  "productpage-v1",         "default",            "productpage-v1"),
    ("deployment",  "ratings-v1",             "default",            "ratings-v1"),
    ("deployment",  "reviews-v1",             "default",            "reviews-v1"),
    ("deployment",  "reviews-v2",             "default",            "reviews-v2"),
    ("deployment",  "reviews-v3",             "default",            "reviews-v3"),
    ("statefulset", "kafka",                  "kafka",              "kafka"),
    ("deployment",  "banyandb",               "skywalking",         "banyandb"),
    ("deployment",  "otel-collector",         "skywalking",         "otel-collector"),
    ("deployment",  "skywalking-oap",         "skywalking",         "skywalking-oap"),
    ("deployment",  "skywalking-ui",          "skywalking",         "skywalking-ui"),
    ("deployment",  "vm-nginx",               "vm-nginx",           "vm-nginx"),
    ("deployment",  "local-path-provisioner", "local-path-storage", "local-path-provisioner"),
    ("deployment",  "coredns",                "kube-system",        "coredns"),
    ("deployment",  "kube-state-metrics",     "kube-system",        "kube-state-metrics"),
    ("deployment",  "metrics-server",         "kube-system",        "metrics-server"),
    ("deployment",  "istio-egressgateway",    "istio-system",       "istio-egressgateway"),
    ("deployment",  "istio-ingressgateway",   "istio-system",       "istio-ingressgateway"),
    ("deployment",  "istiod",                 "istio-system",       "istiod"),
    ("deployment",  "kiali",                  "istio-system",       "kiali"),
    ("deployment",  "prometheus",             "istio-system",       "prometheus"),
]

for kind, name, ns, inst in label_targets:
    patch(kind, name, ns, {
        "spec": {"template": {"metadata": {
            "labels": {"app.kubernetes.io/instance": inst}
        }}}
    })

print("\n[2/5] 남은 deploymentMissingReplicas - replicas=2 설정")

replica_targets = [
    ("deployment",  "fortio-deploy",          "default"),
    ("deployment",  "kafka-producer",         "default"),
    ("deployment",  "istio-egressgateway",    "istio-system"),
    ("deployment",  "istio-ingressgateway",   "istio-system"),
    ("deployment",  "istiod",                 "istio-system"),
    ("deployment",  "kiali",                  "istio-system"),
    ("deployment",  "prometheus",             "istio-system"),
    ("deployment",  "kube-state-metrics",     "kube-system"),
    ("deployment",  "metrics-server",         "kube-system"),
    ("deployment",  "banyandb",               "skywalking"),
    ("deployment",  "otel-collector",         "skywalking"),
    ("deployment",  "skywalking-oap",         "skywalking"),
    ("deployment",  "skywalking-ui",          "skywalking"),
    ("deployment",  "local-path-provisioner", "local-path-storage"),
]

for kind, name, ns in replica_targets:
    patch(kind, name, ns, {"spec": {"replicas": 2}})

print("\n[3/5] 남은 PodDisruptionBudget 생성")

apply(pdb_yaml("kiali", "istio-system", "app", "kiali"))
apply(pdb_yaml("prometheus", "istio-system", "app", "prometheus"))
apply(pdb_yaml("coredns", "kube-system", "k8s-app", "kube-dns"))
apply(pdb_yaml("kube-state-metrics", "kube-system", "app.kubernetes.io/name", "kube-state-metrics"))
apply(pdb_yaml("metrics-server", "kube-system", "k8s-app", "metrics-server"))
apply(pdb_yaml("skywalking-oap", "skywalking", "app", "skywalking-oap"))
apply(pdb_yaml("skywalking-ui", "skywalking", "app", "skywalking-ui"))

print("\n[4/5] istio-system imagePullPolicy + 리소스 + probe 추가")

istiod_res = {"requests": {"cpu": "50m", "memory": "100Mi"},
              "limits":   {"cpu": "1",   "memory": "512Mi"}}
prom_res   = {"requests": {"cpu": "100m", "memory": "256Mi"},
              "limits":   {"cpu": "500m", "memory": "1Gi"}}
prom_reload_res = {"requests": {"cpu": "20m", "memory": "32Mi"},
                   "limits":   {"cpu": "100m", "memory": "128Mi"}}

patch("deployment", "istiod", "istio-system", {"spec": {"template": {"spec": {"containers": [
    container_patch_minimal("discovery", pull="Always",
        resources=istiod_res,
        liveness=http_probe("/ready", 8080, delay=30, period=30))
]}}}})

patch("deployment", "istio-egressgateway", "istio-system", {"spec": {"template": {"spec": {"containers": [
    container_patch_minimal("istio-proxy", pull="Always",
        liveness=tcp_probe(8080, delay=10, period=30))
]}}}})

patch("deployment", "istio-ingressgateway", "istio-system", {"spec": {"template": {"spec": {"containers": [
    container_patch_minimal("istio-proxy", pull="Always",
        liveness=tcp_probe(8080, delay=10, period=30))
]}}}})

patch("deployment", "kiali", "istio-system", {"spec": {"template": {"spec": {"containers": [
    container_patch_minimal("kiali", pull="Always",
        resources={"requests": {"cpu": "10m", "memory": "64Mi"},
                   "limits":   {"cpu": "500m", "memory": "1Gi"}})
]}}}})

patch("deployment", "prometheus", "istio-system", {"spec": {"template": {"spec": {"containers": [
    container_patch_minimal("prometheus-server", pull="Always",
        resources=prom_res,
        sc={"allowPrivilegeEscalation": False,
            "capabilities": {"drop": ["ALL"]},
            "seccompProfile": {"type": "RuntimeDefault"}}),
    container_patch_minimal("prometheus-server-configmap-reload", pull="Always",
        resources=prom_reload_res,
        sc={"allowPrivilegeEscalation": False,
            "capabilities": {"drop": ["ALL"]},
            "seccompProfile": {"type": "RuntimeDefault"}}),
]}}}})

print("\n[5/5] kube-system imagePullPolicy 추가")

patch("deployment", "coredns", "kube-system", {"spec": {"template": {"spec": {"containers": [
    container_patch_minimal("coredns", pull="Always",
        resources={"requests": {"cpu": "100m", "memory": "70Mi"},
                   "limits":   {"cpu": "500m", "memory": "170Mi"}})
]}}}})

print("\n완료!")
