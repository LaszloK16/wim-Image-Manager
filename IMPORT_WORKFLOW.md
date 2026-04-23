# Bringing in external ChatGPT-generated code safely

Yes — you can paste the latest code here and I can figure out what does what, then update this repo.

This is the fastest way to make it reliable:

## What to paste

For each file, paste in this exact block format:

```text
=== FILE START: path/to/file.ext ===
<contents>
=== FILE END ===
```

If you are not sure where a file belongs, use:

```text
=== FILE START: unknown/<descriptive-name>.txt ===
<contents>
=== FILE END ===
```

Also include:

- The run command you used before (if any).
- Any known errors and stack traces.
- Which behaviors matter most (priority order).

## What I will do after you paste

1. **Inventory**: map each pasted file to role (API, UI, DB, infra, scripts).
2. **Diff & merge plan**: compare pasted code to repo code and identify safe merges.
3. **Refactor where needed**: reduce duplication, normalize naming, remove dead code.
4. **Validate**: run static checks and startup checks.
5. **Commit + PR summary**: clear explanation of what changed and why.

## Minimum metadata that helps a lot

- Expected environment variables
- Ports used
- Storage locations
- Authentication expectations
- Windows deployment assumptions (WinPE, driver path format, model lookup rules)

## If you paste one giant file dump

That still works. I can:

- Split files logically,
- Reconstruct a project tree,
- Identify entry points,
- Convert it into maintainable repo commits.

## Recommended phased migration (for very large dumps)

- Phase 1: App boots end-to-end.
- Phase 2: Image registration + listing works.
- Phase 3: Deployment-plan logic works.
- Phase 4: Auth, validation, and hardening.
