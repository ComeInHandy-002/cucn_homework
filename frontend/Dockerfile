# Frontend: build the Vue3 SPA in Node, serve it from nginx; the API lives in
# the separate `api` service and is reached through the reverse proxy below.
# No `syntax=` directive: the built-in BuildKit frontend avoids a Hub fetch.

FROM node:20-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --registry=https://registry.npmmirror.com --no-fund --no-audit
COPY frontend/ ./
# The repo build outputs into ../app/static/dist for bare-metal serving; inside
# this image an explicit output keeps the nginx copy path obvious.
RUN npm run build -- --outDir /app/dist

FROM nginx:1.27-alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
