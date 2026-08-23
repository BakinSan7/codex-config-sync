# Migrating two existing machines

Use this workflow when Windows and macOS already have different Codex configurations. Do not choose one device as canonical until you inspect both.

## 1. Create a private repository from the template

Keep this public template unchanged. Create a new private repository with **Use this template**, then clone that private repository on the first machine.

## 2. Inventory the first machine

Run `doctor`, then prepare a local-to-repository plan:

```text
plan --direction from-device --show-diff
```

The plan may propose replacing the example `portable/AGENTS.md` and portable memory note. It does not automatically discover every skill or config key; add only the names and keys you intend to manage.

Run `apply`, then inspect `git diff`. Remove private paths, transient facts, credentials, and device-only instructions before committing.

## 3. Inspect the second machine before applying

Clone the private repository on the second machine and run:

```text
plan --direction to-device --show-diff
```

If its local `AGENTS.md`, skills, or selected config values contain useful differences, stop. Edit the canonical files in the private repository or collect a separate sanitized copy for comparison. Run `plan` again after every edit.

## 4. Classify every difference

- **Common:** same meaning and dependencies on both systems.
- **Windows:** PowerShell, drive letters, Windows apps, junctions, or Windows-only tools.
- **macOS:** Keychain, AppleScript, Homebrew paths, Accessibility, or macOS-only tools.
- **Local:** security permissions, UI settings, reasoning effort, project paths, auth, plugin/MCP state, chats, caches, and generated memory.

Name equality is not evidence that two skills are equivalent. Compare their complete directory contents and dependencies.

## 5. Apply only the reviewed result

When the new plan reflects the approved classification, run `apply` and `verify`. Keep the reported backup until the new Codex process discovers the expected instructions and skills.

## 6. Verify in Codex

Filesystem equality proves installation, not model discovery. Start a new Codex process and confirm that the expected global instructions, personal skills, and custom agents are visible. OS-specific components must be absent on the other platform.

The project cannot automate this final product-level verification because Codex discovery and account state can vary by installation and version.
