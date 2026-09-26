# Pull request

## Outcome

Describe the user-visible result.

## Safety impact

Describe any new writes, managed paths, permissions, dependencies, deletion behavior, or data exposure risk.

## Verification

- [ ] Unit tests pass on the affected platform(s).
- [ ] `scan --public-audit` passes.
- [ ] Catalog changes are reflected in `README.md`, `README.ru.md` and `docs/SKILLS.md`.
- [ ] Wrapper smoke test passes on the affected platform.
- [ ] `git diff --check` passes.
- [ ] No credentials, personal configuration, real user paths, symlinks, or generated state were added.
