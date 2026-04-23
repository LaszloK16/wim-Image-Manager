# Network-Based Windows OS Deployment: Recommended Architecture

## Short answer
Using one Docker container per image will likely become hard to maintain and slower to operate at scale.

A better pattern is:

- **One deployment service** (or a small HA set) that controls workflows.
- **One image repository** with deduplicated base OS images.
- **One driver repository** indexed by hardware model/PCI IDs.
- **Task sequences** that combine base image + driver pack + post-install scripts at deployment time.

## Why container-per-image is risky

If you have dozens of images now, you may have hundreds later. Container-per-image introduces:

- Drift between containers (different scripts, patch levels).
- Operational overhead (builds, tags, vuln scanning, updates).
- Duplicate storage for mostly-identical images.
- Harder troubleshooting due to many execution paths.

Containers are still useful for the management plane (web UI/API/background jobs), but not as the core image abstraction.

## Recommended design

### 1) Management Plane (Dockerized)

Run these as containers:

- **Web UI/API**: operator chooses site/model/OS profile and can register/upload new image metadata (and optionally image artifacts) through the portal.
- **Orchestrator worker**: resolves model to driver pack + task sequence.
- **Metadata DB**: models, OS versions, driver mappings, audit logs.
- **Artifact service (optional)**: serves scripts/configs; images can stay on NAS/object store.

### 2) Delivery Plane (PXE/iPXE + WinPE)

- PXE or iPXE boots target machine into WinPE.
- WinPE calls API with hardware inventory (model, vendor, PCI IDs).
- API returns deployment plan:
  - Base image (e.g., Win10 22H2, Win11 23H2)
  - Driver pack URL(s)
  - Optional firmware/BIOS/preflight steps
  - Post-install package list (apps, security agent, domain join)
- WinPE applies image + drivers + unattended config.

### 3) Image strategy

Maintain a **small set of base images** by OS generation, not per model.

- UI should support **saving new images**: create image entries, attach version/build metadata, and publish/unpublish them for deployment selection.
- Add role-based controls so only authorized admins can create/update image records or upload image artifacts.
- For large WIM/ISO files, prefer chunked upload to object/NAS storage with checksum verification before publish.

- Example: `win10-22h2-enterprise-golden.wim`, `win11-23h2-enterprise-golden.wim`
- Keep images clean: latest CU + baseline apps only.
- Layer customization post-install using scripts/package manager.

### 4) Driver strategy

- Store driver packs separately by model and OS.
- Index by:
  - OEM model identifier
  - Compatible OS build
  - Optional fallback by PCI IDs
- Validate pack signatures/checksums.
- Keep “known good” version pinning per model.

### 5) Workflow and governance

- Versioned task sequences in Git.
- Immutable releases (promote dev -> pilot -> production).
- Per-deployment audit trail (who/what/when/result).
- Rollback path to previous image/driver mapping.

## Practical stack options

- **Open-source leaning**: iPXE + WinPE + WIM tooling + your API/UI.
- **Enterprise Microsoft leaning**:
  - MDT/WDS-like flow (where available in your environment)
  - or Configuration Manager / Intune Autopilot for modern lifecycle needs.

If most devices are modern and internet-accessible, evaluate Autopilot/Intune to reduce on-prem imaging over time.

## Suggested MVP

1. Build one deployment API/UI container with an **Add Image** workflow (metadata form + upload/registration).
2. Build one worker container that:
   - accepts hardware inventory,
   - selects base image + driver pack,
   - emits a deployment manifest.
3. Stand up shared storage for:
   - `/images/base/*.wim`
   - `/drivers/<vendor>/<model>/<os>/...`
   - `/scripts/task-sequences/...`
4. Pilot 3–5 hardware models before full rollout.

## Decision rubric

Choose container-per-image only if all are true:

- Very small fleet (<10 model/OS combinations).
- No expectation of rapid growth.
- Minimal compliance/audit requirements.

Otherwise, use **metadata-driven composition** (base image + driver + sequence), which scales better and is easier to operate.
