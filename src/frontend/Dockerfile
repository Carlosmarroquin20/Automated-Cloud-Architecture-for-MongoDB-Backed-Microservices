# syntax=docker/dockerfile:1

# ------------------------------------------------------------------------------
# Builder stage
# Produces the optimized, hashed static assets. Dependencies are installed from
# the lockfile for a reproducible build.
# ------------------------------------------------------------------------------
FROM node:20-alpine@sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293 AS builder

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# ------------------------------------------------------------------------------
# Runtime stage
# A minimal nginx image serves the static assets and reverse-proxies API and
# health traffic to the backend, keeping the browser on a single origin.
# ------------------------------------------------------------------------------
FROM nginx:1.31-alpine@sha256:72ba65eb42c10344912a84ff42408db7d34f2feb642204570ab8fc5ffd29f1d3 AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
