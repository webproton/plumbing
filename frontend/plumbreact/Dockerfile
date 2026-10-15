# syntax=docker/dockerfile:1

# ---------- build ----------
FROM node:20-bookworm-slim AS build
WORKDIR /app
COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile --network-timeout 600000
COPY . .
# API на том же домене: запросы идут на /api/... (nginx проксирует в Django)
ENV REACT_APP_API_URL=""
RUN yarn build

# ---------- serve ----------
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build /usr/share/nginx/html
