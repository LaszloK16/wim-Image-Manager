# Network OS Image Publisher (Docker + Samba + WinPE)

A configurable dashboard for Windows `.wim` upload/import/publish workflows, with WinPE helper scripts.

## 1) Initial setup variables (no hardcoded company/IP/user/pass)

Copy and edit:

```bash
cp .env.example .env
cp winpe/winpe-config.cmd.example winpe/winpe-config.cmd
```

### Docker `.env` variables

- `APP_PORT` (default `8080`)
- `NAS_ROOT` (default `/mnt/nas`)
- `OSSHARE_ROOT` (default `/srv/osshare`)
- `PUBLISH_LINK` (default `/srv/osshare/install.wim`)
- `CAPTURE_ROOT` (default `/srv/osshare/captured`)
- `APP_TAG` (default `LaszloK`)

### WinPE `winpe-config.cmd` variables

- `DEPLOY_SERVER` (e.g. `SERVER_IP_OR_HOSTNAME`)
- `DEPLOY_SHARE` (e.g. `osshare`)
- `SMB_USER`
- `SMB_PASS`
- `PUBLISHED_WIM` (default `install.wim`)
- `IMAGE_INDEX` (default `1`)
- `DISK_INDEX` (default `0`)
- `BOOT_MODE` (`UEFI` or `BIOS`, default `UEFI`)
- `TAG` (display label; default `LaszloK`)

## 2) Start service

```bash
docker compose down
docker compose up --build -d
```

Open: `http://<server-ip>:${APP_PORT}`

## 3) Samba share requirements

- share path writable for WinPE capture target
- published image path exists when deploying
- capture folder exists for new captures

Typical paths:

- `${OSSHARE_ROOT}/install.wim`
- `${OSSHARE_ROOT}/captured`
- `${NAS_ROOT}/images`

## 4) WinPE scripts included

- `winpe/startnet.cmd`
- `winpe/capture.cmd`
- `winpe/diskpart_uefi.txt`
- `winpe/diskpart_bios.txt`
- `winpe/listdisk.txt`
- `winpe/findwin.txt`
- `winpe/winpe-config.cmd.example`

## 5) Install failure fix applied

The deploy script now supports configurable boot mode and picks the correct diskpart script:

- `BOOT_MODE=UEFI` -> `diskpart_uefi.txt`
- `BOOT_MODE=BIOS` -> `diskpart_bios.txt`

It also applies with configurable image index and runs:

- `bcdboot C:\Windows /s S: /f %BOOT_MODE%`

This addresses common install failures caused by UEFI/BIOS mismatch and fixed assumptions.
