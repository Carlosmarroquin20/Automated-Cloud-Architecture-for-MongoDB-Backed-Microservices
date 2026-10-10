# syntax=docker/dockerfile:1

# ------------------------------------------------------------------------------
# Builder stage
# Produces the optimized, hashed static assets. Dependencies are installed from
# the lockfile for a reproducible build.
# ------------------------------------------------------------------------------
FROM node:25-alpine@sha256:bdf2cca6fe3dabd014ea60163eca3f0f7015fbd5c7ee1b0e9ccb4ced6eb02ef4 AS builder

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
FROM nginx:1.31-alpine@sha256:df221db836e1754089190208cee7eeda94f233197056426eda74a43ab1abeac2 AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
