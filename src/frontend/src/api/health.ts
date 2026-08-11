import { config } from "../config";

// Readiness is checked directly rather than through the JSON client because the
// probe is a plain reachability signal and any failure is treated as "not ready".
export async function checkReadiness(): Promise<boolean> {
  try {
    const response = await fetch(config.healthUrl, { method: "GET" });
    return response.ok;
  } catch {
    return false;
  }
}
