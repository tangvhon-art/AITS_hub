# 阶段1: 构建前端
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

# 阶段2: nginx 部署
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html

# nginx 配置（代理 /api → backend, /flower → flower）
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
