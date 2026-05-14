# Claude-Test: Kubernetes DevOps 실습 환경

kind 클러스터 기반의 완전한 DevOps 파이프라인 구성 실습 레포지토리.

---

## 구성 환경

| 항목 | 내용 |
|---|---|
| 클러스터 | kind (myk8s), 단일 노드 |
| OS | Ubuntu on WSL2 (Windows) |
| Kubernetes | v1.32.2 |
| Istio | v1.27.1 |

---

## 배포 파이프라인 아키텍처

```
Developer Push
      │
      ▼
GitHub (taekou/claude-test)
      │
      ▼
Tekton Pipeline (CI Build)
  ├─ git-clone Task   : 소스코드 클론
  └─ kaniko-build Task: 이미지 빌드 & Harbor Push
      │
      ▼
Harbor Registry  (http://172.19.16.32:30002)
  └─ apps/demo-app: v1, v2, v3, latest
      │
      ▼
ArgoCD Sync  (https://172.19.16.32:30008)
  └─ demo-gitops/deployment.yaml 감시 → 자동 배포
      │
      ▼
Kubernetes Deploy  (namespace: demo)
      │
      ▼
Istio Sidecar Injection
  └─ containers: demo-app + istio-proxy
      │
      ▼
Traffic Control / Security / Metrics
  └─ Grafana Istio 대시보드로 모니터링
```

---

## 설치된 솔루션

### CI/CD 파이프라인
| 솔루션 | 네임스페이스 | 용도 |
|---|---|---|
| **Harbor** | harbor | 컨테이너 이미지 레지스트리 |
| **Tekton Pipelines** | tekton-pipelines | CI 빌드 엔진 (git-clone + kaniko) |
| **Kubero** | kubero | 파이프라인 관리 UI (PaaS) |
| **ArgoCD** | argocd | GitOps CD (자동 배포) |

### 서비스 메시
| 솔루션 | 네임스페이스 | 용도 |
|---|---|---|
| **Istio** | istio-system | 서비스 메시 (mTLS, 트래픽 관리) |
| **Kiali** | istio-system | Istio 시각화 대시보드 |

### 모니터링 & 관측성
| 솔루션 | 네임스페이스 | 용도 |
|---|---|---|
| **Prometheus** | istio-system | 메트릭 수집 |
| **Grafana** | 호스트 서비스 | 메트릭 시각화 (Istio 전용 대시보드 포함) |
| **Loki + Promtail** | logging | 로그 수집 및 조회 |
| **SkyWalking** | skywalking | APM (분산 추적) |
| **Alertmanager** | monitoring | 알림 관리 |

### 샘플 애플리케이션 (Bookinfo + Kafka)
| 앱 | 네임스페이스 | 설명 |
|---|---|---|
| productpage, details, reviews, ratings | default | Istio Bookinfo 데모 |
| kafka-producer, kafka-consumer | default | Kafka 메시징 데모 |
| demo-app | demo | GitOps 파이프라인 테스트용 Flask 앱 |

---

## Windows 브라우저 접속 URL

> WSL2 IP는 재시작 시 변경될 수 있음. `port-forward-all.sh` 재실행 필요.

| 솔루션 | URL | 계정 |
|---|---|---|
| **Harbor** | http://172.19.16.32:30002 | admin / Harbor12345 |
| **ArgoCD** | https://172.19.16.32:30008 | admin / kQM8qSNjSptp2fr7 |
| **Kubero** | http://172.19.16.32:30010 | admin / admin1234 |
| **Tekton Dashboard** | http://172.19.16.32:30011 | - |
| **Kiali** | http://172.19.16.32:30001 | - |
| **Grafana** | http://172.19.16.32:3000 | admin / admin |
| **SkyWalking** | http://172.19.16.32:31899 | - |

---

## 레포지토리 구조

```
claude-test/
│
├── README.md                         # 이 파일
├── port-forward-all.sh               # 포트포워딩 복원 스크립트
│
├── demo-app/                         # GitOps 테스트 샘플 앱 (Flask)
│   ├── Dockerfile
│   └── src/app.py
│
├── demo-gitops/                      # ArgoCD가 감시하는 K8s 매니페스트
│   └── deployment.yaml              # demo-app Deployment + Service
│
├── cicd/                             # CI/CD 파이프라인 설정
│   ├── tekton/
│   │   └── tekton-pipeline.yaml     # Pipeline, Task, PipelineRun 정의
│   ├── argocd/
│   │   └── argocd-application.yaml  # ArgoCD Application 매니페스트
│   └── kubero/
│       └── kubero-deploy.yaml       # Kubero UI Deployment
│
├── polaris/                          # Polaris 보안 점검 & 수정 스크립트
│   ├── polaris-fix.py               # 1차 수정 (Danger 53건)
│   ├── polaris-fix2.py              # 2차 수정 (Warning 265건)
│   ├── remove-nonroot.py            # runAsNonRoot 제거 (root 실행 컨테이너)
│   ├── polaris-audit.json           # 전체 감사 결과 (JSON)
│   └── polaris-audit-report.txt     # 감사 리포트 (텍스트)
│
└── monitoring/
    └── grafana-dashboards/
        └── import-istio-dashboards.py  # Istio 공식 대시보드 7종 임포트 스크립트
```

---

## 주요 작업 이력

### 1. 클러스터 보안 강화 (Polaris)
- Polaris v10.2.0으로 전체 클러스터 감사
- Danger 53건 → 28건 (-47%), Warning 265건 → 78건 (-71%)
- 보안 컨텍스트 설정: `allowPrivilegeEscalation: false`, `capabilities: drop ALL`, `seccompProfile: RuntimeDefault`
- PodDisruptionBudget 25개 생성
- 리소스 requests/limits 전체 설정

### 2. Grafana Istio 전용 대시보드 설치
- Istio 설치 패키지 내장 공식 대시보드 7종 임포트
  - Istio Mesh Dashboard
  - Istio Service Dashboard
  - Istio Workload Dashboard
  - Istio Control Plane Dashboard
  - Istio Performance Dashboard
  - Istio Wasm Extension Dashboard
  - Istio Ztunnel Dashboard

### 3. CI/CD 파이프라인 구축
- **Harbor**: 로컬 컨테이너 레지스트리 설치 (NodePort 30002)
- **Tekton Pipelines**: git-clone + kaniko 빌드 파이프라인 구성
- **Kubero**: 파이프라인 관리 UI 배포 (CRD + operator)
- **ArgoCD**: GitOps CD 설치, demo-app 자동 배포 설정

### 4. 로그 수집 (Loki + Promtail)
- Loki 2.9.4 → logging 네임스페이스 배포
- Promtail DaemonSet → 전체 파드 로그 수집
- Grafana Explore에서 LogQL로 조회 가능

---

## 자주 쓰는 명령어

### 포트포워딩 복원 (WSL2 재시작 후)
```bash
bash ~/claude-test/port-forward-all.sh
```

### Tekton 빌드 트리거
```bash
cat <<EOF | kubectl apply -f -
apiVersion: tekton.dev/v1
kind: PipelineRun
metadata:
  name: demo-build-v4
  namespace: tekton-pipelines
spec:
  pipelineRef:
    name: build-and-deploy
  taskRunTemplate:
    serviceAccountName: tekton-build-sa
  params:
  - name: git-url
    value: https://github.com/taekou/claude-test
  - name: image
    value: 172.18.0.2:30002/apps/demo-app
  - name: image-tag
    value: v4
  - name: context
    value: demo-app
  workspaces:
  - name: source
    persistentVolumeClaim:
      claimName: tekton-workspace-pvc
EOF
```

### Polaris 재점검
```bash
polaris audit --kubernetes --format=pretty 2>/dev/null | tail -20
```

### ArgoCD 수동 Sync
```bash
argocd app sync demo-app --server 172.18.0.2:30008 --insecure
```

### Istio 메트릭 확인
```bash
curl -sG "http://localhost:9090/api/v1/query" \
  --data-urlencode 'query=sum(rate(istio_requests_total[1m])) by (destination_service_name)' | \
  python3 -c "import json,sys; [print(f'{r[\"metric\"][\"destination_service_name\"]}: {float(r[\"value\"][1]):.2f} rps') for r in json.load(sys.stdin)['data']['result']]"
```
