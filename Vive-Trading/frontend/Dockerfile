# Stage 1: Build the Vite React application
FROM node:20-alpine AS build

WORKDIR /app

# 패키지 파일 복사 및 의존성 설치
COPY package*.json ./
RUN npm install

# 소스 복사 및 빌드
COPY . .
RUN npm run build

# Stage 2: Serve the Vite app with Nginx
FROM nginx:alpine

# 빌드 결과물을 Nginx html 폴더로 복사
COPY --from=build /app/dist /usr/share/nginx/html

# (선택) 커스텀 nginx.conf가 있으면 추가
# COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]