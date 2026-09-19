# Manifest 기반 CI/CD Hook Router

GitHub 또는 Perforce webhook을 공통 이벤트로 변환하고, 별도로 관리하는
라우팅 manifest에서 저장소·브랜치·변경 경로를 조회한 뒤 일치하는 Jenkins
job을 모두 실행하는 FastAPI 서비스입니다.

```text
GitHub PR/push webhook ─┐
                       ├─> 정규화 ─> routing manifest 조회 ─> 조건 매칭
Perforce submit hook ──┘                                  ├─> Jenkins job A
                                                         └─> Jenkins job B
```

manifest 저장 위치는 로컬 YAML, SQLite DB, 원격 HTTP/GitHub 저장소 중에서
선택할 수 있습니다. Bitbucket 같은 새 저장소 도구는 source adapter만 추가하면
기존 manifest 판정과 Jenkins 연동을 그대로 사용합니다.

## 빠른 시작

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'

export CICD_ROUTER_CONFIG=config/router.manifest.example.yaml
export CICD_ROUTER_DB=cicd-router-events.db
export GITHUB_WEBHOOK_SECRET='github-webhook에-입력한-secret'
export GITHUB_TOKEN='github-token'
export JENKINS_USERNAME='jenkins-service-account'
export JENKINS_TOKEN='jenkins-api-token'

uvicorn cicd_router.main:app --host 0.0.0.0 --port 8000
```

상태 확인은 `GET /healthz`, OpenAPI 문서는 `GET /docs`에서 할 수 있습니다.

## 실제 처리 흐름

GitHub PR이 열리거나 새 commit이 추가되면 다음 순서로 처리합니다.

1. `X-Hub-Signature-256`으로 webhook 서명을 검증합니다.
2. payload에서 저장소, source branch, target branch, commit SHA, PR 번호를 읽습니다.
3. GitHub Pull Request Files API로 변경 파일을 조회합니다.
4. 현재 routing manifest를 file, SQLite 또는 HTTP provider에서 읽습니다.
5. 저장소·이벤트·브랜치·경로가 모두 맞는 route를 전부 선택합니다.
6. `(source, delivery ID, route ID)`를 SQLite에 선점해 중복 실행을 막습니다.
7. 선택된 Jenkins job 각각에 build parameter를 전달합니다.

manifest 저장소의 PR만 검사하는 구조가 아닙니다. 예를 들어 manifest에
`PSHyeok/payment-api`가 등록돼 있다면, `payment-api`에서 발생한 PR webhook이
들어왔을 때 해당 항목을 조회해 job을 결정합니다.

## Routing manifest

전체 예시는
[`config/routing-manifest.example.yaml`](config/routing-manifest.example.yaml)에
있습니다.

```yaml
version: 1
manifest_version: "2026-09-19.1"

routes:
  - id: payment-backend-pr
    enabled: true
    match:
      sources: [github]
      events: [pull_request]
      repositories: ["acme/payment-api"]
      branches: ["*"]
      source_branches: ["feature/*", "fix/*"]
      target_branches: [main, "release/*"]
      include_paths: ["src/*", "shared/*"]
      exclude_paths: ["**/*.md"]
      on_paths_unavailable: trigger
    trigger:
      provider: jenkins
      base_url: https://jenkins.example.com
      job: payment/backend-pr
      username_env: JENKINS_USERNAME
      token_env: JENKINS_TOKEN
      parameters:
        BUILD_TARGET: backend
```

조건의 의미는 다음과 같습니다.

| 필드 | 의미 |
| --- | --- |
| `repositories` | 허용할 `owner/repository` 패턴입니다. 허용 저장소를 여기서 제한합니다. |
| `events` | `pull_request`, `push`, Perforce의 `submit` 같은 정규화 이벤트입니다. |
| `branches` | 공통/기존 branch 조건입니다. PR에서는 target branch에 적용됩니다. |
| `source_branches` | PR을 올린 쪽 branch 조건입니다. |
| `target_branches` | PR이 병합될 대상 branch 조건입니다. |
| `include_paths` | 이 패턴에 해당하는 변경 파일이 하나라도 있을 때 실행합니다. 생략하면 경로와 관계없이 실행합니다. |
| `exclude_paths` | include된 파일 중 실행 대상에서 제외할 패턴입니다. |
| `on_paths_unavailable` | 변경 파일을 가져오지 못했을 때 `trigger`, `skip`, `error` 중 하나를 선택합니다. |

문자열 패턴은 shell-style glob이고, 서로 다른 조건은 AND, 같은 목록 안의
패턴은 OR로 평가합니다. 여러 route가 일치하면 하나만 고르지 않고 모두
실행합니다.

GitHub PR 파일 API는 PR 하나당 최대 3,000개 파일을 반환합니다. API 오류나
한도 초과 시 `paths_complete=false`가 되고 각 route의
`on_paths_unavailable` 설정이 적용됩니다.

## Manifest 저장 방식

### YAML 파일

[`config/router.manifest.example.yaml`](config/router.manifest.example.yaml):

```yaml
version: 1
manifest_source:
  provider: file
  path: config/routing-manifest.example.yaml
```

요청마다 파일을 다시 읽으므로 파일을 교체하면 라우터 재시작 없이 다음
webhook부터 새 버전이 적용됩니다.

### SQLite DB

[`config/router.manifest-sqlite.example.yaml`](config/router.manifest-sqlite.example.yaml)을
사용하고 YAML을 활성 버전으로 등록합니다.

```bash
python -m cicd_router.manifest_admin import \
  --db routing-manifest.db \
  --file config/routing-manifest.example.yaml
```

동일 명령은 `cicd-manifest import ...`로도 실행할 수 있습니다. 등록은 한
트랜잭션에서 이전 버전을 비활성화하고 새 버전을 활성화합니다.

### 원격 HTTP 또는 GitHub 저장소

[`config/router.manifest-http.example.yaml`](config/router.manifest-http.example.yaml)은
GitHub Contents API의 raw 응답을 읽는 예시입니다. ETag를 사용해 변경되지 않은
manifest를 재사용하고, 일시적인 원격 오류에는 마지막 정상 캐시를 사용할 수
있습니다.

## GitHub webhook 설정

- Payload URL: `https://<외부에서 접근 가능한 주소>/v1/hooks/github`
- Content type: `application/json`
- Secret: 라우터의 `GITHUB_WEBHOOK_SECRET`과 동일한 값
- Events: `Pull requests`, 필요하면 `Pushes`

PR action 중 `opened`, `reopened`, `synchronize`를 처리하고 나머지는 무시합니다.
`X-GitHub-Delivery` 값은 중복 방지 키로 사용합니다. 비공개 저장소의 변경 파일
조회에는 Fine-grained PAT의 해당 저장소 `Pull requests: read` 권한 또는
동등한 GitHub App 권한이 필요합니다.

## Jenkins에 전달하는 값

Jenkins job에는 사용할 parameter를 미리 선언해야 합니다.

| Parameter | 내용 |
| --- | --- |
| `HOOK_EVENT_ID` | GitHub delivery ID 또는 source 이벤트 ID |
| `HOOK_SOURCE` | `github`, `perforce` |
| `HOOK_BRANCH` | 공통 branch. PR에서는 target branch |
| `HOOK_SOURCE_BRANCH` | PR source branch |
| `HOOK_TARGET_BRANCH` | PR target branch |
| `HOOK_PULL_REQUEST` | PR 번호 |
| `HOOK_REVISION` | commit SHA 또는 changelist |
| `HOOK_REPOSITORIES` | 변경 저장소 목록 |
| `ROUTING_MANIFEST_VERSION` | 판정에 사용한 manifest 버전 |

route의 `parameters`에 선언한 고정 값도 함께 전송합니다.

## Minikube Jenkins E2E

개발 전용 Jenkins는 `admin/admin` 계정을 사용합니다. 운영 환경에서는 절대 이
설정을 사용하지 마세요.

```bash
minikube start
kubectl apply -f deploy/minikube/jenkins.yaml
kubectl -n cicd-hook-demo rollout status deployment/jenkins
kubectl -n cicd-hook-demo port-forward service/jenkins 18080:8080

# manifest route용 demo job 두 개 생성
curl -u admin:admin \
  --data-urlencode script@deploy/minikube/create-manifest-demo-jobs.groovy \
  http://127.0.0.1:18080/scriptText

export CICD_ROUTER_CONFIG=config/policies.minikube.yaml
export CICD_ROUTER_DB=cicd-router-events.db
export JENKINS_USERNAME=admin
export JENKINS_TOKEN=admin
export GITHUB_WEBHOOK_SECRET='테스트-secret'
export GITHUB_TOKEN='테스트-token'
uvicorn cicd_router.main:app --host 127.0.0.1 --port 18000
```

GitHub가 로컬 API로 webhook을 보낼 수 있도록 Cloudflare Tunnel, ngrok 또는
공식 배포 주소가 필요합니다. 임시 tunnel URL은 프로세스를 종료하면 사라지는
공개 중계 주소일 뿐 별도 CI/CD 서비스가 아닙니다.

2026-09-19 실제 검증에서는
[`PSHyeok/cicd-manifest-target-demo` PR #1](https://github.com/PSHyeok/cicd-manifest-target-demo/pull/1)의
`src/feature.py` 변경으로 `demo-source-pr`와 `demo-common-pr`가 함께 매칭됐고,
Minikube Jenkins의 `manifest-source #1`, `manifest-common #1`이 모두
`SUCCESS`가 됐습니다. 이어서
[`PR #2`](https://github.com/PSHyeok/cicd-manifest-target-demo/pull/2)에서 문서만
변경했을 때는 공통 job만 `manifest-common #2`로 실행되고 source job은 #1에
그대로 머물러 경로 필터도 확인했습니다.

## 환경변수

| 환경변수 | 의미 |
| --- | --- |
| `CICD_ROUTER_CONFIG` | manifest provider를 정하는 Router YAML 경로. 기본값 `config/policies.yaml` |
| `CICD_ROUTER_DB` | webhook 중복 방지와 실행 결과를 저장할 SQLite 경로. 기본값 `cicd-router.db` |
| `GITHUB_WEBHOOK_SECRET` | GitHub webhook 요청의 HMAC-SHA256 서명 검증 secret |
| `GITHUB_TOKEN` | GitHub PR 파일 조회 또는 private 원격 manifest 조회 token |
| `GITHUB_API_URL` | GitHub Enterprise API root. 기본값 `https://api.github.com` |
| `GITHUB_API_VERSION` | GitHub REST API 버전. 기본값 `2026-03-10` |
| `JENKINS_USERNAME` | Jenkins HTTP Basic 인증 계정 |
| `JENKINS_TOKEN` | Jenkins 계정의 API token. 운영에서는 비밀번호 대신 사용 |
| `HOOK_SECRET` | Perforce adapter의 `X-Hook-Signature` 검증 secret |

`username_env`, `token_env`에는 secret 자체가 아니라 환경변수의 **이름**을
적습니다. 따라서 manifest를 Git에 저장해도 Jenkins 인증 정보는 노출되지
않습니다.

## Perforce와 새 저장소 도구 확장

Perforce는 `POST /v1/hooks/perforce`로 받을 수 있습니다. Bitbucket 등 새
provider를 추가할 때는 `sources/` 아래에 `SourceAdapter.normalize()`를
구현하고 `main.py`에 등록합니다. provider 고유 payload는 adapter 안에서
`NormalizedEvent`로 바뀌므로 manifest provider, 매칭, 중복 방지, Jenkins
코드는 바꿀 필요가 없습니다.

## 검증

```bash
pytest -q
```

운영에서는 HTTPS, 강한 webhook secret, Jenkins API token, 영구 DB 볼륨을
사용하세요. 여러 Router 인스턴스를 실행한다면 SQLite 대신 공유 트랜잭션
DB와 durable queue 도입을 권장합니다.
