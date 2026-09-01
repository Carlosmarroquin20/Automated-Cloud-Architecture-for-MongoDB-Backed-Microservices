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
FROM nginx:1.27-alpine@sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10 AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
