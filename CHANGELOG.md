# Changelog

All notable changes to this project will be documented in this file.

## v1.44 (Hardening) (2026-01-20)
- **Security**: Enforced strict `750/640` permissions on dashboard files.
- **Security**: `setup_dashboard.sh` and `update_dashboard.sh` now exclude `venv` from strict permissions to preserve execution.
- **Refactor**: `update_dashboard.sh` fully migrated to JSON config (dropped `.env` support).

## v1.43 (2026-01-20)
- **Refactor**: Replaced Environment Variables with JSON configuration files (`instance/config.json` for Dashboard, `agent_config.json` for Agent).
- **Agent**: Loading config from `agent_config.json` (local or `/etc/vm-agent/`).
- **Deployment**: Installers now generate JSON config automatically.

## v1.42 (2026-01-20)
- **Feature**: Configurable timezone for scheduler via `instance/config.json` (key: `timezone`). No environment variables required.
- **Enhancement**: Moved general settings loading to `general_config.py`.

## v1.41 (2026-01-20)
- **Feature**: Added dashboard-based Agent Auto-Update. Agents can now pull updates directly from the dashboard.
- **Feature**: Added `scripts/update_dashboard.sh` for safe dashboard updates (preserves data).
- **Enhancement**: Dashboard now serves agent binaries and version info via API (`/api/agent/version`).
- **Enhancement**: Updated dashboard footer with detailed credits and links.
- **Fix**: Resolved issue where `update_dashboard.sh` could delete the installation root.

## v1.40 (2026-01-20) - Initial Open Source Release
- Added interactive installation scripts for Linux and Windows
- Added feature flags for modular deployment
- Added cleanup scripts
- Improved documentation and screenshots

## [1.39] - 2026-01-20

### Added
- Interactive installation scripts with feature flag toggles
  - `scripts/setup.sh` - Linux agent installer with prompts
  - `agent/setup.ps1` - Windows agent installer (PowerShell)
  - `scripts/setup_dashboard.sh` - Dashboard installer with auto-generated keys
- Batch mode support (`--batch`) for automated deployments
- Screenshots in `screenshots/` directory

## [1.38] - 2026-01-20

### Added
- Feature flags via `instance/features.json` - enable/disable commands, SMS, alerts, containers, pods, auto_update
- SMS configuration via `instance/sms_config.json` instead of environment variables
- Hot-reload for config changes without service restart
- `/api/features` and `/api/sms-config` API endpoints

## [1.37] - 2026-01-20

### Added
- Configurable timezone support for SMS schedule (default: Europe/Istanbul)
- `/api/schedule` endpoint to view upcoming SMS times

### Fixed
- Windows CPU tracking - System Idle Process excluded from metrics

## [1.36] - 2026-01-20

### Added
- Twilio SMS provider support
- "Send SMS" button in dashboard header for manual triggers
- Schedule API endpoint

## [1.35] - 2026-01-19

### Added
- SMS Alerts with scheduled notifications at 08:30, 12:00, 13:30, 17:00
- Pluggable SMS providers (Textbelt, İleti Merkezi)
- Alert summary in SMS messages

## [1.34] - 2026-01-19

### Added
- Access logging to `instance/access.log`
- `/logs` page to view recent access logs
- Log rotation at 5MB with 3 backups

## [1.33] - 2026-01-18

### Added
- Rootless Podman container discovery
- Historical chart time range selector (1h, 6h, 12h, 24h)
- Improved Kubernetes pod discovery

## [1.32] - 2026-01-17

### Added
- Remote command execution from dashboard
- Agent auto-update system
- Windows agent support

## [1.0.0] - 2026-01-13

### Added
- Initial release
- CPU, RAM, Disk monitoring
- Docker container discovery
- Web dashboard with real-time updates
- Linux and Windows agent support
