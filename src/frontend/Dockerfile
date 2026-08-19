# syntax=docker/dockerfile:1

# ------------------------------------------------------------------------------
# Builder stage
# Produces the optimized, hashed static assets. Dependencies are installed from
# the lockfile for a reproducible build.
# ------------------------------------------------------------------------------
FROM node:20-alpine AS builder

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
FROM nginx:1.27-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
