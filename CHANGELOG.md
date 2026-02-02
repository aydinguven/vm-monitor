# Changelog

All notable changes to this project will be documented in this file.

## v1.52 (2026-02-02)
- **Feature**: Memory Ballooning Detection!
- **Agent**: Detects VirtIO balloon driver (Linux) or Windows Balloon Driver.
- **UI**: Added 🎈 indicator for balloon-enabled VMs.
- **Alerts**: Surpresses RAM alerts if ballooning is active to prevent false positives.
- **Migration**: Added `migrate_add_balloon.py` for database schema updates.

## v1.51 (2026-02-02)
- **Repo**: Bumped version for agent auto-updates.
- **Fix**: Minor improvements to packaging.

## v1.50 (2026-01-29)
- **Rename**: Project renamed from `vm-agent-dashboard` to `vm-monitor`. Service/user/paths updated.
- **Feature**: Telegram notifications (direct bot or via relay service).
- **Feature**: Multi-provider support! Send SMS (Twilio) and Telegram alerts simultaneously.
- **Config**: Setup Wizard now supports Multi-Provider config generation (`providers` array).
- **Security**: Removed secrets from git history and docs. Added `get_all_providers()` factory.
- **UI**: Added "Test Telegram" button to dashboard.
- **Docs**: Added `docs/TELEGRAM_SETUP.md` guide.

## v1.49 (2026-01-24)
- **Feature**: ICMP ping latency + HTTP RTT (both metrics tracked).
- **UI**: More tolerant color thresholds (green <100ms, yellow 100-300ms, red >300ms).
- **Docs**: Added Windows agent installation to README.

## v1.48 (2026-01-24)
- **Feature**: Agent-side latency monitoring - ICMP ping + HTTP RTT.
- **UI**: VM cards show color-coded ping latency (green <100ms, yellow 100-300ms, red >300ms).
- **Agent**: Agent now measures ICMP ping and HTTP POST time, reports both with metrics.

## v1.47 (2026-01-21)
- **Feature**: Demo Mode - run a fully functional demo with fake data.
- **Demo**: Live demo at [monitordemo.aydin.cloud](https://monitordemo.aydin.cloud).
- **Demo**: Includes data simulator to keep VMs "online" with varying metrics.
- **Demo**: Demo banner injected without modifying production code.
- **Docs**: Improved README with "Control vs Visibility" positioning.
- **Docs**: Added CONTRIBUTING.md for first-time contributors.
- **Docs**: Expanded Feature Flags documentation.

## v1.46.1 (2026-01-21)
- **Fix**: `update_dashboard.sh` now copies agent files to `static/downloads/` for auto-update.
- **Fix**: Agent version API now returns correct version after dashboard updates.

## v1.46 (2026-01-21)
- **Feature**: Configurable SMS schedule times via `sms_config.json`.
- **Config**: New `schedule.times` array (e.g., `["09:00", "11:30", "14:30", "17:00"]`).
- **Note**: Falls back to default times (08:30, 12:00, 13:30, 17:00) if not configured.

## v1.45.3 (2026-01-21)
- **Security**: Agent now runs as dedicated `vm-agent` user (not root).
- **Security**: Dynamic sudoers rules generated for detected binaries (podman, docker, systemctl, etc.).
- **Security**: Principle of Least Privilege - agent can only execute approved commands.
- **Fix**: Container discovery now uses `sudo` for root-level queries.
- **Fix**: Cleanup script no longer corrupts terminal (`stty sane`, specific `pkill`).
- **Fix**: Sudoers rules now work correctly (removed faulty wildcards).
- **Fix**: Ensure `/etc/sudoers.d/` directory exists before creating rules.
- **Fix**: Handle missing binaries gracefully during sudoers generation.


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
