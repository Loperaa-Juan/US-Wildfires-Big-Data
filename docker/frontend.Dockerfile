# React frontend: built with pnpm, served by nginx, which also forwards /api to the Flask API
# (same origin for the browser, so the API needs no CORS).
#
#   docker build -f docker/frontend.Dockerfile --target test .   # only the unit tests (CI)
#   docker compose up --build frontend                            # http://localhost:3000

FROM node:24-alpine AS deps
WORKDIR /app
# corepack provides the exact pnpm version pinned in package.json ("packageManager")
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./

FROM deps AS test
RUN pnpm test

FROM deps AS build
# tsc -b type-checks the whole app before Vite bundles it
RUN pnpm build

FROM nginx:1.29-alpine
COPY docker/frontend.nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
