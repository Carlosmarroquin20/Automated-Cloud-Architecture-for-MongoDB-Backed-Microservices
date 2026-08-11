// Runtime configuration resolution.
//
// Resolution order, most to least specific:
//   1. window.APP_CONFIG   - injected at container start, enabling per-environment
//      configuration without rebuilding the image
//   2. import.meta.env     - Vite build-time environment
//   3. same-origin default - matches the production reverse-proxy topology and
//      keeps no backend host embedded in the shipped assets

interface RuntimeConfig {
  apiBaseUrl: string;
  healthUrl: string;
}

declare global {
  interface Window {
    APP_CONFIG?: Partial<RuntimeConfig>;
  }
}

const injected: Partial<RuntimeConfig> = window.APP_CONFIG ?? {};

export const config: RuntimeConfig = {
  apiBaseUrl: injected.apiBaseUrl ?? import.meta.env.VITE_API_BASE_URL ?? "/api/v1",
  healthUrl: injected.healthUrl ?? import.meta.env.VITE_HEALTH_URL ?? "/health/ready",
};
