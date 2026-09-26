# Security policy

## Reporting a vulnerability

Use GitHub's **Report a vulnerability** form in the Security tab. Do not open a public issue containing exploit details, credentials, private configuration, or real user paths.

Include:

- the affected version and operating system;
- the exact command and a minimal sanitized manifest;
- the expected and observed filesystem targets;
- whether a symlink, junction, reparse point, stale plan, pinned third-party skill, or rollback was involved;
- a reproduction that uses placeholders instead of secrets.

## Supported versions

Security fixes are provided for the latest tagged release. During the `0.x` series, upgrade to the newest release before reporting a problem already fixed on `main`.

## Security boundary

Codex Config Sync is not a secrets manager and cannot prove that arbitrary natural-language files contain no private information. Its scanner is defense in depth.

The project protects against accidental cross-device copying, unsafe manifest paths, stale plans, linked filesystem targets, unpinned third-party sources, common credential formats, and partial writes. It does not protect against a malicious local administrator or an attacker who can modify the process or filesystem during execution.

See [Security model](docs/SECURITY_MODEL.md) for the complete threat model.
