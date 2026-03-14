# ── Этап 1: сборка ────────────────────────────────────────────────────────────
FROM node:22-alpine AS builder

# Ограничиваем память Node.js (для VPS с малым объёмом RAM)
ENV NODE_OPTIONS="--max-old-space-size=1024"

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts

COPY . .
RUN npm run build

# ── Этап 2: раздача через nginx ───────────────────────────────────────────────
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
