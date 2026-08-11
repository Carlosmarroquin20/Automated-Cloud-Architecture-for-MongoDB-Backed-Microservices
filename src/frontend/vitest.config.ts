import { defineConfig } from "vitest/config";

// Unit tests target framework-free pure logic and run in a Node environment; no
// DOM emulation is required, keeping the suite fast and dependency-light.
export default defineConfig({
  test: {
    environment: "node",
    include: ["tests/**/*.test.ts"],
  },
});
