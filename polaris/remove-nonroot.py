#!/usr/bin/env python3
import subprocess, json

targets = [
    ("deployment",  "default",             "fortio-deploy",         "fortio"),
    ("deployment",  "default",             "httpbin",               "httpbin"),
    ("deployment",  "default",             "kafka-consumer",        "kafka-consumer"),
    ("deployment",  "default",             "kafka-producer",        "kafka-producer"),
    ("deployment",  "default",             "productpage-v1",        "productpage"),
    ("deployment",  "local-path-storage",  "local-path-provisioner","local-path-provisioner"),
    ("deployment",  "skywalking",          "banyandb",              "banyandb"),
    ("deployment",  "skywalking",          "otel-collector",        "otel-collector"),
    ("deployment",  "skywalking",          "skywalking-oap",        "oap"),
    ("deployment",  "skywalking",          "skywalking-ui",         "ui"),
    ("deployment",  "vm-nginx",            "vm-nginx",              "nginx"),
    ("deployment",  "vm-nginx",            "vm-nginx",              "kafka-producer"),
    ("statefulset", "kafka",               "kafka",                 "kafka"),
    ("deployment",  "kube-system",         "kube-state-metrics",    "kube-state-metrics"),
    ("deployment",  "kube-system",         "metrics-server",        "metrics-server"),
]

for kind, ns, deploy, cname in targets:
    r = subprocess.run(
        f"kubectl get {kind} {deploy} -n {ns} -o json",
        shell=True, capture_output=True, text=True
    )
    if r.returncode != 0:
        print(f"SKIP: {ns}/{deploy}/{cname} (not found)")
        continue

    d = json.loads(r.stdout)
    containers = d['spec']['template']['spec']['containers']
    idx = next((i for i, c in enumerate(containers) if c['name'] == cname), None)
    if idx is None:
        print(f"SKIP: {ns}/{deploy}/{cname} (container not found)")
        continue

    sc = containers[idx].get('securityContext', {})
    if 'runAsNonRoot' not in sc:
        print(f"SKIP: {ns}/{deploy}/{cname} (runAsNonRoot not set)")
        continue

    patch = json.dumps([{"op": "remove",
                          "path": f"/spec/template/spec/containers/{idx}/securityContext/runAsNonRoot"}])
    r2 = subprocess.run(
        f"kubectl patch {kind} {deploy} -n {ns} --type=json -p '{patch}'",
        shell=True, capture_output=True, text=True
    )
    if r2.returncode == 0:
        print(f"OK: {ns}/{deploy}/{cname}")
    else:
        print(f"FAIL: {ns}/{deploy}/{cname}: {r2.stderr.strip()[:80]}")
