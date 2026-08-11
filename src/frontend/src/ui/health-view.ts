import { checkReadiness } from "../api/health";
import { el } from "./dom";

// Readiness is polled on an interval so the indicator reflects backend recovery
// without a manual page refresh.
const POLL_INTERVAL_MS = 15_000;

export function mountHealthView(root: HTMLElement): void {
  const dot = el("span", { class: "health__dot health__dot--unknown" });
  const label = el("span", { class: "health__label" }, ["Checking…"]);
  const pill = el(
    "div",
    { class: "health__pill", role: "status", "aria-live": "polite" },
    [dot, label],
  );
  root.append(pill);

  async function refresh(): Promise<void> {
    const ready = await checkReadiness();
    dot.className = `health__dot ${ready ? "health__dot--up" : "health__dot--down"}`;
    label.textContent = ready ? "API ready" : "API unavailable";
  }

  void refresh();
  window.setInterval(() => {
    void refresh();
  }, POLL_INTERVAL_MS);
}
