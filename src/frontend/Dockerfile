# syntax=docker/dockerfile:1

# ------------------------------------------------------------------------------
# Builder stage
# Produces the optimized, hashed static assets. Dependencies are installed from
# the lockfile for a reproducible build.
# ------------------------------------------------------------------------------
FROM node:26-alpine@sha256:2d984a15c9b54fd0aeb608b8e0d0d83529eb34d2966db27a1fb4f1edc3d298a3 AS builder

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
FROM nginx:1.27-alpine@sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10 AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
