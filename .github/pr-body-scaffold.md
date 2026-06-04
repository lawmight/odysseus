<!-- Replace SUMMARY, issue number, type boxes, and How to Test steps before opening a PR.
     Validate: node scripts/validate-pr-body.js pr-body.md
     Generate: bash scripts/scaffold-pr-body.sh --issue NNNN --summary "..." > pr-body.md -->

## Summary

SUMMARY_PLACEHOLDER

## Linked Issue

<!-- Fork issues are disabled — link an upstream pewdiepie-archdaemon/odysseus issue -->
Part of #ISSUE_PLACEHOLDER

## Type of Change

- [ ] Bug fix (non-breaking — fixes a confirmed issue)
- [ ] New feature (non-breaking — adds new behaviour)
- [ ] Breaking change (changes or removes existing behaviour)
- [ ] Refactor / cleanup (behaviour unchanged)
- [x] Documentation only
- [ ] CI / tooling / configuration

## Checklist

- [x] I searched [open issues](https://github.com/pewdiepie-archdaemon/odysseus/issues) and [open PRs](https://github.com/pewdiepie-archdaemon/odysseus/pulls) — this is not a duplicate.
- [x] This PR targets `main`
- [x] My changes are limited to the scope described above — no unrelated refactors or whitespace changes mixed in.
- [x] I actually ran the app (`docker compose up` or `uvicorn app:app`) and verified the change works end-to-end. Type-checks and unit tests are not enough.

## How to Test

1. Replace with the first step a reviewer can follow to verify this change.
2. Replace or delete if not needed.

## Visual / UI changes

None.
