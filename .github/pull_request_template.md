<!--
Keep pull requests focused on a single concern. The checklist mirrors the gates
the CI pipeline enforces, so a self-check here shortens the review cycle.
-->

## Summary

<!-- What does this change do, and why? -->

## Type of change

- [ ] Feature
- [ ] Fix
- [ ] Refactor / cleanup
- [ ] Documentation
- [ ] CI / build / infrastructure

## Related issues

<!-- e.g. Closes #123 -->

## Checklist

- [ ] The change is scoped to a single concern.
- [ ] Backend gates pass locally (`ruff check`, `mypy --strict`, `pytest`).
- [ ] Frontend gates pass locally (`eslint`, `tsc`, `vitest`, `vite build`), if applicable.
- [ ] Terraform / Kubernetes manifests validate, if applicable.
- [ ] No secrets, credentials, tokens, or private hosts are introduced.
- [ ] Documentation and comments are updated where behavior changed.
