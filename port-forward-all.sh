#!/bin/bash
# WSL2 재시작 후 또는 포트포워딩이 끊겼을 때 실행
# bash /home/devops/claude-test/port-forward-all.sh

echo "기존 포트포워딩 정리..."
pkill -f "kubectl port-forward" 2>/dev/null
sleep 2

echo "포트포워딩 시작..."

# ── 대시보드/UI ─────────────────────────────────────────
nohup kubectl port-forward svc/harbor          -n harbor             --address=0.0.0.0 30002:80    >/tmp/pf-harbor.log 2>&1 &
nohup kubectl port-forward svc/argocd-server   -n argocd             --address=0.0.0.0 30008:443   >/tmp/pf-argocd.log 2>&1 &
nohup kubectl port-forward svc/kubero          -n kubero             --address=0.0.0.0 30010:2000  >/tmp/pf-kubero.log 2>&1 &
nohup kubectl port-forward svc/tekton-dashboard -n tekton-pipelines  --address=0.0.0.0 30011:9097  >/tmp/pf-tekton.log 2>&1 &
nohup kubectl port-forward svc/kiali           -n istio-system       --address=0.0.0.0 30001:20001 >/tmp/pf-kiali.log 2>&1 &
nohup kubectl port-forward svc/skywalking-ui   -n skywalking         --address=0.0.0.0 31899:80    >/tmp/pf-skywalking.log 2>&1 &

# ── Grafana 데이터소스 ────────────────────────────────────
nohup kubectl port-forward svc/prometheus      -n istio-system       --address=0.0.0.0 9090:9090   >/tmp/pf-prometheus.log 2>&1 &
nohup kubectl port-forward svc/loki            -n logging            --address=0.0.0.0 3100:3100   >/tmp/pf-loki.log 2>&1 &
nohup kubectl port-forward svc/alertmanager    -n monitoring         --address=0.0.0.0 9093:9093   >/tmp/pf-alertmanager.log 2>&1 &

sleep 4

WSL_IP=$(ip addr show eth0 | grep "inet " | awk '{print $2}' | cut -d/ -f1)

echo ""
echo "======================================"
echo " Windows 브라우저 접속 URL"
echo "======================================"
echo "  Harbor         http://${WSL_IP}:30002    admin / Harbor12345"
echo "  ArgoCD         https://${WSL_IP}:30008   admin / kQM8qSNjSptp2fr7"
echo "  Kubero         http://${WSL_IP}:30010    admin / admin1234"
echo "  Tekton         http://${WSL_IP}:30011"
echo "  Kiali          http://${WSL_IP}:30001"
echo "  Grafana        http://${WSL_IP}:3000     admin / admin"
echo "  SkyWalking     http://${WSL_IP}:31899"
echo "======================================"
echo ""
echo "  Prometheus     http://localhost:9090"
echo "  Loki           http://localhost:3100"
echo "  Alertmanager   http://localhost:9093"
echo ""

# 상태 확인
echo "=== 연결 상태 ==="
declare -A checks=(
  ["Harbor:30002"]="http://localhost:30002"
  ["ArgoCD:30008"]="https://localhost:30008"
  ["Kubero:30010"]="http://localhost:30010"
  ["Tekton:30011"]="http://localhost:30011"
  ["Prometheus:9090"]="http://localhost:9090/-/ready"
  ["Loki:3100"]="http://localhost:3100/ready"
)
for name in "Harbor:30002" "ArgoCD:30008" "Kubero:30010" "Tekton:30011" "Prometheus:9090" "Loki:3100"; do
  url="${checks[$name]}"
  code=$(curl -sk -o /dev/null -w "%{http_code}" --max-time 3 "$url" 2>/dev/null)
  ok=$([ "$code" -ge 200 ] && [ "$code" -lt 400 ] 2>/dev/null && echo "✅" || echo "⏳")
  echo "  $ok ${name}: HTTP ${code}"
done
