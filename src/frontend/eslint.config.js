import js from "@eslint/js";
import globals from "globals";
import tseslint from "typescript-eslint";

// Type-aware linting is intentionally omitted; static type verification is
// delegated to the TypeScript compiler (tsc --noEmit), while ESLint enforces
// correctness and style rules without a project service.
export default tseslint.config(
  { ignores: ["dist/**", "coverage/**", "node_modules/**"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.ts"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
      globals: { ...globals.browser },
    },
  },
  {
    files: ["**/*.js"],
    languageOptions: {
      globals: { ...globals.node },
    },
  },
);
