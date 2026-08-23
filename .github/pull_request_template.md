# Pull request

## Outcome

Describe the user-visible result.

## Safety impact

Describe any new writes, managed paths, permissions, dependencies, deletion behavior, or data exposure risk.

## Verification

- [ ] Unit tests pass on the affected platform(s).
- [ ] `doctor --public-audit` passes for Windows and macOS profiles.
- [ ] Wrapper smoke test passes on the affected platform.
- [ ] `git diff --check` passes.
- [ ] No credentials, personal configuration, real user paths, symlinks, or generated state were added.
