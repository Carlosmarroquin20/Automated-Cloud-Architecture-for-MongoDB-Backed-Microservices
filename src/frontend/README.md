# Frontend Console

Lightweight static client for the MongoDB-backed microservice API, built with
Vite and TypeScript without a UI framework. The build emits optimized, hashed,
minified static assets suitable for serving behind a reverse proxy.

## Architecture

- **Stack:** Vite + strict TypeScript, no runtime dependencies.
- **Rendering:** framework-free DOM composition. User-provided values are written
  as text nodes rather than HTML, removing a cross-site scripting vector.
- **API boundary:** a typed client mirrors the backend contract and normalizes
  the server error envelope into a single `ApiError` type; requests are bounded
  by a timeout.
- **Configuration:** the API base URL resolves from `window.APP_CONFIG` (runtime
  injection), then Vite build-time environment, then a same-origin default of
  `/api/v1`. No backend host is embedded in the shipped assets.
- **Topology:** same-origin defaults assume a reverse proxy that forwards `/api`
  and `/health` to the backend, avoiding cross-origin exposure. The development
  server replicates this with a proxy.

## Project Structure

```
src/frontend/
├── index.html
├── public/favicon.svg
├── src/
│   ├── api/            # Typed client, error model, resource and health calls
│   ├── types/          # Shared API contract types
│   ├── ui/             # Framework-free views and DOM helpers
│   ├── styles/         # Design tokens and component styles
│   ├── config.ts       # Runtime configuration resolution
│   └── main.ts         # Composition root
├── tests/              # Vitest unit tests for pure logic
├── eslint.config.js
├── tsconfig.json
├── vite.config.ts
└── vitest.config.ts
```

## Local Development

Commands are executed from `src/frontend` with Node.js 20 or newer.

Install dependencies:

```bash
npm install
```

Run the development server (proxies `/api` and `/health` to `http://localhost:8000`):

```bash
npm run dev
```

Quality gates:

```bash
npm run lint
npm run typecheck
npm run test
```

Produce the optimized production build in `dist/`:

```bash
npm run build
```

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `VITE_API_BASE_URL` | `/api/v1` | API base path or absolute URL |
| `VITE_HEALTH_URL` | `/health/ready` | Readiness probe path or absolute URL |

For runtime configuration without rebuilding, a served `window.APP_CONFIG`
object may define `apiBaseUrl` and `healthUrl`; it takes precedence over the
build-time values.
