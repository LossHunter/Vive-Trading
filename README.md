# VT (Vive Trading)
FastAPI(Backend)와 React(Frontend)를 사용하는 풀스택 애플리케이션입니다.

---

## 준비물
| 항목 | 내용 |
|---|---|
| OS | Ubuntu 24.04 (권장) |
| 필수 프로그램 | Docker, Docker Compose |
| 네트워크 | Port `3000`, `8000` 오픈 |

---

## 설치 및 실행 방법

### 1) 프로젝트 클론
```bash
git clone https://github.com/totalcream/VT.git
cd VT
```

### 2) 애플리케이션 실행
아래 명령어 하나로 백엔드와 프론트엔드 서비스가 모두 빌드되고 실행됩니다.
```bash
docker compose up --build -d
```

### 3) 실행 확인
```bash
docker compose ps
```

예시 출력:
```
NAME                IMAGE               COMMAND                  SERVICE             CREATED             STATUS              PORTS
fastapi_test_prj-backend-1    fastapi_test_prj-backend    "uvicorn main:app --…"   backend             2 minutes ago       Up 2 minutes        0.0.0.0:8000->8000/tcp
fastapi_test_prj-frontend-1   fastapi_test_prj-frontend   "nginx -g 'daemon of…"   frontend            2 minutes ago       Up 2 minutes        0.0.0.0:3000->80/tcp
```

---

## 접속 방법

| 환경 | 접속 URL |
|---|---|
| 로컬 접속 | http://localhost:3000 |
| 외부 IP 접속 | http://<서버-IP>:3000 |

---

## 컨테이너 관리

| 작업 | 명령어 |
|---|---|
| 전체 서비스 중지 | `docker compose stop` |
| 전체 서비스 내리기 (중지 및 컨테이너 삭제) | `docker compose down` |
| 전체 서비스 로그 확인 | `docker compose logs -f` |
| 특정 서비스 로그 확인 (예: frontend) | `docker compose logs -f frontend` |

---

## 프로젝트 구조

이 프로젝트는 `backend`와 `frontend` 두 개의 주요 디렉토리로 구성된 모노레포입니다.

-   **`backend/app/`**: FastAPI 애플리케이션의 핵심 소스 코드가 위치합니다.
    -   **`api/`**: API 엔드포인트와 의존성 관리를 담당합니다.
    -   **`core/`**: 애플리케이션의 설정(환경 변수 등)을 관리합니다.
    -   **`db/`**: 데이터베이스 모델 및 세션 관리를 담당합니다.
    -   **`crud/`**: 데이터베이스 CRUD(생성, 읽기, 수정, 삭제) 로직을 포함합니다.
    -   **`schemas/`**: Pydantic을 사용한 데이터 유효성 검사 스키마를 정의합니다.
    -   **`services/`**: vLLM, Upbit 등 외부 서비스와의 통신 및 핵심 비즈니스 로직을 처리합니다.
-   **`frontend/`**: React 기반의 프론트엔드 애플리케이션 소스 코드가 위치합니다.
-   **`docker-compose.yml`**: `backend`와 `frontend` 서비스를 정의하고 함께 실행하기 위한 파일입니다.
-   **`.github/workflows/`**: `main` 브랜치에 푸시 시 자동으로 클라우드 서버에 배포하는 CI/CD 워크플로우가 정의되어 있습니다.

---

## 주요 API 엔드포인트

### LLM 트레이딩 결정 생성

-   **Endpoint:** `POST /api/llm/trade-decision`
-   **Description:** LLM을 사용하여 시장 데이터에 기반한 트레이딩 결정을 생성합니다.
-   **Request Body:**
    ```json
    {
      "user_data_prompt": "분석할 시장 데이터 및 계좌 정보 문자열...",
      "model_name": "사용할 LLM 모델 이름 (예: openai/gpt-oss-120b)"
    }
    ```
-   **Success Response (200 OK):**
    ```json
    {
      "stop_loss": 2.1877,
      "signal": "hold",
      "leverage": 8,
      "risk_usd": 594.7,
      "profit_target": 2.6485,
      "quantity": 5164.0,
      "invalidation_condition": "BTC breaks below 105,000, confirming deeper market correction",
      "justification": "The current position on XRP is profitable and the market shows potential for further upside. Holding the position is the best course of action.",
      "confidence": 0.75,
      "coin": "XRP"
    }
    ```

---

## 개발 가이드라인 (Development Guidelines)

팀원들과의 효율적인 협업을 위해 다음 가이드라인을 준수해 주세요.

-   **`git push origin main` 금지:**
    -   `main` 브랜치는 항상 안정적이고 배포 가능한 상태를 유지해야 합니다.
    -   모든 개발 작업은 `main` 브랜치에서 파생된 **별도의 피처 브랜치(Feature Branch)** 에서 진행해 주세요.
    -   작업 완료 후에는 `main` 브랜치로 직접 푸시하지 마십시오.

-   **Pull Request (PR)를 통한 코드 검토 및 병합:**
    -   피처 브랜치에서의 개발이 완료되면, `main` 브랜치로 병합하기 위한 **Pull Request(PR)** 를 생성해 주세요.
    -   PR을 통해 팀원들에게 코드 변경 사항을 공유하고, 코드 리뷰를 받아 품질을 높인 후 `main` 브랜치에 병합합니다.

-   **AI로 코드를 작성할 경우:**
    -   AI 도구를 사용하여 코드를 작성할 때는 **구현하고자 하는 기능을 상세하고 명확하게 전달**해 주세요.
    -   단순히 "해줘" 식의 지시는 코드를 불필요하게 늘리거나, 의도와 다른 결과를 초래하여 코드 리뷰를 어렵게 만들 수 있습니다.
    -   AI가 생성한 코드도 본인의 코드와 동일하게 책임감을 가지고 검토하고 이해해야 합니다.

-   **주석 상세 작성:**
    -   코드의 가독성과 유지보수성을 위해 **주석을 상세하게 작성**해 주세요.
    -   특히, 복잡한 로직이나 비즈니스 규칙이 포함된 부분은 **"왜 이렇게 구현했는지" (Why)** 와 **"어떻게 구현되었는지" (How)** 를 명확히 설명하는 주석을 달아주세요.
    -   함수나 클래스에는 Docstring을 사용하여 기능, 인자, 반환 값 등을 명시하는 것이 좋습니다.
