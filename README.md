# VT (Vive Trading)
FastAPI 기반 간단 REST API 서버

---

## 준비물
| 항목 | 내용 |
|---|---|
| OS | Ubuntu 24.04 (권장) |
| 필수 프로그램 | Docker |
| 네트워크 | Port `8000` 오픈 |

---

## 설치 및 실행 방법

### 1) 프로젝트 클론
```bash
git clone https://github.com/totalcream/VT.git
cd VT
```

### 2) Docker 이미지 빌드
```bash
docker build -t fastapi-test-app .
```

### 3) 컨테이너 실행
```bash
docker run -d -p 8000:8000 --name my-fastapi-app fastapi-test-app:latest
```

### 4) 실행 확인
```bash
docker ps
```

예시 출력:
```
CONTAINER ID   IMAGE                     COMMAND                  CREATED         STATUS         PORTS                                         NAMES
fc5206e632ee   fastapi-test-app:latest   "uvicorn main:app --…"   4 seconds ago   Up 3 seconds   0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp   my-fastapi-app
```

---

## 접속 방법

| 환경 | 접속 URL |
|---|---|
| 로컬 접속 | http://localhost:8000 |
| 외부 IP 접속 | http://<서버-IP>:8000 |

---

## 컨테이너 / 이미지 관리

| 작업 | 명령어 |
|---|---|
| 컨테이너 중지 | `docker stop my-fastapi-app` |
| 컨테이너 삭제 | `docker rm my-fastapi-app` |
| 이미지 삭제 | `docker rmi fastapi-test-app` |
