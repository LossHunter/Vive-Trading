# Stage 1: Build the React application
FROM node:18-alpine as builder

WORKDIR /app

COPY package.json ./
COPY package-lock.json ./

RUN npm install

COPY . ./

RUN npm run build

# Stage 2: Serve the React application with Nginx
FROM nginx:stable-alpine

COPY --from=builder /app/build /usr/share/nginx/html

# Copy the Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]