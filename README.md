# Palo Alto Firewall Upgrade Playbook

Ansible playbook for automating PAN-OS upgrades, designed for Ansible Automation Platform (AAP).

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Requirements](#requirements)
- [Directory Structure](#directory-structure)
- [AAP Setup](#aap-setup)
- [Survey Variables Reference](#survey-variables-reference)
- [Operation Modes](#operation-modes)
- [Upgrade Modes](#upgrade-modes)
- [Step-by-Step Usage Guide](#step-by-step-usage-guide)
- [Staged Upgrade Workflow](#staged-upgrade-workflow)
- [Rollback Procedures](#rollback-procedures)
- [Version Matrix](#version-matrix)
- [Custom Filters](#custom-filters)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)

---

## Overview

This playbook provides automated upgrade capabilities for Palo Alto firewalls, including:

- Pre-upgrade health validation
- Configuration and state backups
- Firmware staging (download only)
- Standalone and HA pair upgrades
- Post-upgrade verification
- Rollback capabilities (config and firmware)

---

## Architecture

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│                 │         │                 │         │                 │
│  AAP Controller │────────▶│    Panorama     │         │    Firewall     │
│                 │  REST   │  (Discovery)    │         │   (Target)      │
└─────────────────┘  API    └─────────────────┘         └─────────────────┘
        │                                                        ▲
        │                                                        │
        └────────────────────────────────────────────────────────┘
                              SSH (panos_op)
                         All upgrade operations
```

- **Panorama REST API**: Device discovery and validation only
- **SSH to Firewall**: All upgrade operations via `paloaltonetworks.panos` collection

This architecture ensures upgrade operations are performed directly on the firewall, avoiding Panorama as a bottleneck.

---

## Requirements

### Software Requirements

| Component | Version |
|-----------|---------|
| Ansible Automation Platform | 2.x |
| Python | 3.9+ |
| paloaltonetworks.panos collection | 2.x |

### Network Requirements

| Source | Destination | Port | Purpose |
|--------|-------------|------|---------|
| AAP Controller | Panorama | 443 | REST API (device discovery) |
| AAP Controller | Firewall | 443 | SSH/API (upgrade operations) |
| Firewall | updates.paloaltonetworks.com | 443 | Firmware downloads |

### Collections

Install required collections:

```bash
ansible-galaxy collection install -r collections/requirements.yml
```

Required collection:
- `paloaltonetworks.panos`

---

## Directory Structure

```
palo_alto_upgrade/
├── ansible.cfg                 # Ansible configuration
├── site.yml                    # Master playbook
├── README.md                   # This file
├── collections/
│   └── requirements.yml        # Required collections
├── group_vars/
│   └── all.yml                 # Global variables and defaults
├── vars/
│   ├── panos_version_matrix.yml  # Supported upgrade paths
│   └── ha_strategies.yml       # HA upgrade strategies
├── library/
│   └── module_utils/
│       ├── panos_api_client.py
│       └── panos_common.py
├── filter_plugins/
│   └── panos_filters.py        # Custom Jinja2 filters
├── roles/
│   ├── pre_checks/             # Pre-upgrade validation
│   │   ├── tasks/
│   │   │   └── main.yml
│   │   └── defaults/
│   │       └── main.yml
│   ├── backup/                 # Configuration backup
│   │   ├── tasks/
│   │   │   └── main.yml
│   │   └── defaults/
│   │       └── main.yml
│   ├── upgrade/                # Upgrade operations
│   │   ├── tasks/
│   │   │   ├── main.yml
│   │   │   ├── check_software.yml
│   │   │   ├── download_image.yml
│   │   │   ├── install.yml
│   │   │   ├── standalone.yml
│   │   │   └── ha_pair.yml
│   │   └── defaults/
│   │       └── main.yml
│   ├── post_checks/            # Post-upgrade verification
│   │   ├── tasks/
│   │   │   └── main.yml
│   │   └── defaults/
│   │       └── main.yml
│   └── rollback/               # Rollback operations
│       ├── tasks/
│       │   ├── main.yml
│       │   ├── config_restore.yml
│       │   └── firmware_rollback.yml
│       └── defaults/
│           └── main.yml
└── survey/
    └── aap_survey_spec.yml     # AAP survey definition
```

---

## AAP Setup

### Step 1: Create Credential Type

In AAP, navigate to **Administration → Credential Types** and create a new credential type.

**Name:** `Palo Alto Credentials`

**Input Configuration:**
```yaml
fields:
  - id: panorama_host
    type: string
    label: Panorama Host
  - id: username
    type: string
    label: Username
  - id: password
    type: string
    label: Password
    secret: true
```

**Injector Configuration:**
```yaml
extra_vars:
  panorama_server: '{{ panorama_host }}'
  ansible_user: '{{ username }}'
  ansible_password: '{{ password }}'
```

### Step 2: Create Credential

Navigate to **Resources → Credentials** and create a new credential using the type created above.

- **Name:** `Palo Alto - Production` (or your environment name)
- **Credential Type:** `Palo Alto Credentials`
- **Panorama Host:** Your Panorama IP/hostname
- **Username:** API/SSH username
- **Password:** API/SSH password

### Step 3: Create Project

Navigate to **Resources → Projects** and create a new project.

- **Name:** `Palo Alto Upgrade`
- **Source Control Type:** Git
- **Source Control URL:** Your repository URL
- **Source Control Branch:** main (or your branch)

### Step 4: Create Job Template

Navigate to **Resources → Templates** and create a new Job Template.

| Field | Value |
|-------|-------|
| Name | Palo Alto Firewall Upgrade |
| Job Type | Run |
| Inventory | localhost or your inventory |
| Project | Palo Alto Upgrade |
| Playbook | site.yml |
| Credentials | Palo Alto - Production |
| Verbosity | 0 (Normal) - increase for debugging |
| Enable Survey | Yes |

### Step 5: Configure Survey

In the Job Template, click **Survey** tab and add questions matching the `survey/aap_survey_spec.yml` file, or import directly if your AAP version supports it.

---

## Survey Variables Reference

### Required Variables

| Variable | Type | Description | Example |
|----------|------|-------------|---------|
| `survey_operation` | multiplechoice | Operation to perform | `full_upgrade` |
| `panorama_server` | text | Panorama hostname or IP | `panorama.example.com` |
| `survey_target_firewall` | text | Firewall hostname or IP | `fw-dc1-01` |
| `survey_target_version` | text | Target PAN-OS version | `11.1.10-h1` |
| `survey_upgrade_mode` | multiplechoice | Standalone or HA pair | `standalone` |

### Optional Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `survey_download_only` | boolean | `false` | Download without install |
| `survey_force_upgrade` | boolean | `false` | Force even if same version |
| `survey_ha_strategy` | multiplechoice | `sequential` | HA upgrade strategy |
| `survey_ha_failover_wait` | integer | `300` | Seconds to wait after failover |
| `survey_ha_sync_timeout` | integer | `600` | Max seconds to wait for HA sync |
| `survey_backup_enabled` | boolean | `true` | Create backup before upgrade |
| `survey_skip_prechecks` | boolean | `false` | Skip pre-upgrade checks |
| `survey_auto_rollback` | boolean | `true` | Auto rollback on failure |
| `validate_certs` | boolean | `true` | Validate SSL certificates |

---

## Operation Modes

### pre_checks_only

**Purpose:** Validate device readiness without making any changes.

**What it does:**
1. Connects to Panorama to verify device is managed
2. Connects to firewall via SSH
3. Checks system health (CPU, memory, disk)
4. Validates HA status and sync state (if applicable)
5. Verifies upgrade path is supported

**When to use:**
- Before scheduling a maintenance window
- To verify a device is healthy
- To validate upgrade path before committing

**Example:**
```
Operation Mode: pre_checks_only
Panorama Server: panorama.example.com
Target Firewall: fw-dc1-01
Target Version: 11.1.10-h1
Upgrade Mode: standalone
```

---

### backup_only

**Purpose:** Create configuration backup without performing upgrade.

**What it does:**
1. Connects to firewall
2. Creates configuration snapshot on device
3. Names backup with timestamp: `pre-upgrade-YYYYMMDD-HHMMSS.xml`

**When to use:**
- Before making manual changes
- As part of change management process
- To create restore point before maintenance

**Example:**
```
Operation Mode: backup_only
Panorama Server: panorama.example.com
Target Firewall: fw-dc1-01
Target Version: 11.1.10-h1 (not used but required)
Upgrade Mode: standalone
```

---

### download_only

**Purpose:** Stage firmware on device for later upgrade.

**What it does:**
1. Connects to firewall
2. Runs `request system software check` to refresh available versions
3. Verifies target version is available
4. Checks if version is already downloaded (skips if yes)
5. Downloads firmware to device
6. Verifies download completed successfully

**What it does NOT do:**
- Does not install firmware
- Does not reboot device
- No service impact

**When to use:**
- Stage firmware during business hours
- Prepare multiple devices before maintenance window
- Pre-position firmware when bandwidth is available

**Example:**
```
Operation Mode: download_only
Panorama Server: panorama.example.com
Target Firewall: fw-dc1-01
Target Version: 11.1.10-h1
Upgrade Mode: standalone
```

---

### full_upgrade

**Purpose:** Complete end-to-end upgrade workflow.

**What it does:**
1. **Pre-checks** (unless skipped)
   - Validates device health
   - Checks upgrade path
   - Verifies HA status
2. **Backup** (unless skipped)
   - Creates configuration snapshot
3. **Download**
   - Checks if firmware already downloaded (skips if yes)
   - Downloads target version
   - Verifies download success
4. **Install**
   - Installs firmware to inactive partition
   - Monitors installation job
5. **Reboot**
   - Reboots device
   - Waits for device to come online
   - Waits for services to initialize
6. **Post-checks**
   - Verifies new version is running
   - Validates device is healthy

**Service Impact:** Yes - device will reboot

**Estimated Duration:** 15-45 minutes depending on device and version

**Example:**
```
Operation Mode: full_upgrade
Panorama Server: panorama.example.com
Target Firewall: fw-dc1-01
Target Version: 11.1.10-h1
Upgrade Mode: standalone
Enable Backup: true
Skip Pre-checks: false
Auto Rollback: true
```

---

### rollback

**Purpose:** Restore device to previous state after failed or unwanted upgrade.

**What it does:**
1. **Config Restore**
   - Loads configuration from pre-upgrade snapshot
   - Commits restored configuration
2. **Firmware Rollback**
   - Auto-detects previous firmware version
   - Installs previous version (already on device)
   - Reboots device
   - Verifies rollback successful

**Rollback Type:** Full (config + firmware) by default

**Auto-detection:** The playbook automatically determines the previous version by:
1. Checking `pre_upgrade_version` variable (if set during upgrade)
2. Checking `device_current_version` from the upgrade run
3. Finding downloaded versions on device that differ from current

**Service Impact:** Yes - device will reboot

**Example:**
```
Operation Mode: rollback
Panorama Server: panorama.example.com
Target Firewall: fw-dc1-01
Target Version: (not used for rollback)
Upgrade Mode: standalone
```

---

## Upgrade Modes

### Standalone

For single firewalls not in an HA configuration.

**Workflow:**
```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Download   │────▶│   Install   │────▶│   Reboot    │────▶│   Verify    │
│  Firmware   │     │  Software   │     │   Device    │     │  Version    │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

**Service Impact:** Traffic interruption during reboot (typically 5-15 minutes)

---

### HA Pair (Sequential)

For firewalls in Active/Passive HA configuration.

**Workflow:**
```
┌─────────────────────────────────────────────────────────────────────────┐
│                           HA PAIR UPGRADE                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. Validate HA Sync                                                     │
│     └── Ensure both devices are synchronized                            │
│                                                                          │
│  2. Upgrade Passive Device                                               │
│     ├── Download firmware                                                │
│     ├── Install software                                                 │
│     └── Reboot (no traffic impact)                                      │
│                                                                          │
│  3. Failover                                                             │
│     ├── Make upgraded device active                                      │
│     └── Brief traffic interruption during failover                      │
│                                                                          │
│  4. Upgrade Former Active Device                                         │
│     ├── Now passive, safe to upgrade                                    │
│     ├── Download firmware                                                │
│     ├── Install software                                                 │
│     └── Reboot (no traffic impact)                                      │
│                                                                          │
│  5. Verify HA Sync                                                       │
│     └── Confirm both devices synchronized on new version                │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

**Service Impact:** Brief interruption during failover only (typically < 1 minute)

---

## Step-by-Step Usage Guide

### First Time Setup

1. **Clone the repository** to your AAP project source

2. **Install collections:**
   ```bash
   ansible-galaxy collection install paloaltonetworks.panos
   ```

3. **Configure AAP** following the [AAP Setup](#aap-setup) section

4. **Test connectivity** by running `pre_checks_only` on a test device

### Performing Your First Upgrade

#### Step 1: Pre-Checks

Run pre-checks to validate the device is ready:

```
Operation Mode: pre_checks_only
Target Firewall: fw-test-01
Target Version: 11.1.10-h1
```

Review the output for any warnings or failures.

#### Step 2: Backup (Optional)

If you want a separate backup before the upgrade:

```
Operation Mode: backup_only
Target Firewall: fw-test-01
```

#### Step 3: Stage Firmware (Optional)

If upgrading during a maintenance window, stage firmware ahead of time:

```
Operation Mode: download_only
Target Firewall: fw-test-01
Target Version: 11.1.10-h1
```

This can be done during business hours with no impact.

#### Step 4: Full Upgrade

Perform the upgrade:

```
Operation Mode: full_upgrade
Target Firewall: fw-test-01
Target Version: 11.1.10-h1
Upgrade Mode: standalone
Enable Backup: true
Auto Rollback: true
```

#### Step 5: Verify

Check the AAP job output for:
- `UPGRADE COMPLETED SUCCESSFULLY`
- New version confirmation
- Post-check results

---

## Staged Upgrade Workflow

For planned maintenance windows, use a two-phase approach:

### Phase 1: Staging (Business Hours)

**When:** Days or hours before maintenance window

**What:** Download firmware to all target devices

```
Operation Mode: download_only
Target Version: 11.1.10-h1
```

**Benefits:**
- No service impact
- Bandwidth usage during off-peak times
- Identifies download issues early
- Reduces maintenance window duration

**Repeat for each device** or create a workflow template in AAP.

### Phase 2: Upgrade (Maintenance Window)

**When:** During scheduled maintenance window

**What:** Install and reboot

```
Operation Mode: full_upgrade
Target Version: 11.1.10-h1
```

**The playbook will:**
1. Check if firmware is downloaded → **Skip download** (already staged)
2. Proceed directly to install
3. Reboot and verify

**Time Savings:** 10-30 minutes per device (download time eliminated)

---

## Rollback Procedures

### Automatic Rollback

If `survey_auto_rollback` is `true` (default), the playbook automatically initiates rollback when:

- Post-upgrade version verification fails
- Device fails to come online after reboot
- Post-checks fail

### Manual Rollback

To manually rollback after a problematic upgrade:

```
Operation Mode: rollback
Target Firewall: fw-dc1-01
```

**What happens:**
1. Config restored from pre-upgrade snapshot
2. Previous firmware version auto-detected
3. Previous firmware installed (from device cache)
4. Device rebooted
5. Version verified

### Rollback Considerations

- **Previous firmware must be on device** - PAN-OS keeps the previous version
- **Config snapshot must exist** - Created during backup phase
- **Rollback is full by default** - Both config and firmware
- **Service impact** - Device will reboot

---

## Version Matrix

Supported upgrade paths are defined in `vars/panos_version_matrix.yml`.

### Checking Upgrade Paths

The playbook validates:
- Direct upgrade compatibility
- Required intermediate versions
- Content version requirements
- Downgrade restrictions

### Finding Available Versions

On the firewall CLI:
```
request system software check
show system software
```

### Common Upgrade Paths

| From | To | Direct? |
|------|-----|---------|
| 10.1.x | 10.2.x | Yes |
| 10.2.x | 11.0.x | Yes |
| 11.0.x | 11.1.x | Yes |
| 11.1.x | 11.2.x | Yes |
| 10.1.x | 11.1.x | No - requires intermediate |

Always check Palo Alto's official compatibility matrix for your specific versions.

---

## Custom Filters

Custom Jinja2 filters available in `filter_plugins/panos_filters.py`:

### Version Comparison

```yaml
# Check if version is greater than or equal
{{ current_version | panos_version_gte('10.2.0') }}
# Returns: true/false

# Compare two versions
{{ current_version | panos_version_compare(target_version) }}
# Returns: -1 (less), 0 (equal), 1 (greater)
```

### HA State Checks

```yaml
# Check if device is active
{{ ha_state | ha_state_is_active }}
# Returns: true/false

# Check if device is passive
{{ ha_state | ha_state_is_passive }}
# Returns: true/false
```

### Utilities

```yaml
# Generate backup filename
{{ hostname | backup_filename('config') }}
# Returns: hostname_config_20241215-143022.xml

# Convert uptime to minutes
{{ uptime_string | uptime_minutes }}
# Returns: integer minutes
```

---

## Troubleshooting

### Connection Issues

#### Panorama Connection Failed

**Symptoms:**
- `Failed to connect to Panorama`
- `Connection refused`
- `Timeout`

**Solutions:**
1. Verify Panorama IP/hostname is correct
2. Check firewall rules allow AAP → Panorama on port 443
3. Verify API access is enabled on Panorama
4. Test credentials manually

#### Firewall SSH Connection Failed

**Symptoms:**
- `Failed to connect to firewall`
- `Authentication failed`

**Solutions:**
1. Verify firewall IP/hostname is reachable from AAP
2. Check SSH is enabled on management interface
3. Verify credentials have API/SSH access
4. Check for management profile restrictions

### Download Issues

#### Version Not Available

**Symptoms:**
- `Target version X.X.X is not available for download`

**Solutions:**
1. Run `request system software check` on firewall to refresh list
2. Verify version exists for your platform (VM vs hardware)
3. Check firewall has internet access to update servers

#### Download Fails

**Symptoms:**
- `Software download failed`
- Download job shows error

**Solutions:**
1. Check disk space: `show system disk-space`
2. Verify connectivity to `updates.paloaltonetworks.com`
3. Check for proxy requirements
4. Review job details for specific error

#### Version Not Downloaded After Success

**Symptoms:**
- Job shows success but version not available

**Solutions:**
1. Check disk space
2. Review `SOFTWARE INFO RESPONSE` in job output
3. Manually verify: `show system software`

### Upgrade Issues

#### Install Job Fails

**Symptoms:**
- `Software installation failed`
- Job shows error status

**Solutions:**
1. Check disk space
2. Verify no pending commits
3. Check for active sessions that block install
4. Review firewall system logs

#### Device Not Coming Online

**Symptoms:**
- Timeout waiting for device
- `Device failed to respond after reboot`

**Solutions:**
1. Check physical/console access if possible
2. Verify management interface configuration
3. Check for boot issues (may need console access)
4. Increase `reboot_timeout` value

#### Version Mismatch After Upgrade

**Symptoms:**
- `Version mismatch after upgrade. Expected: X, Got: Y`

**Solutions:**
1. Check if install actually completed
2. Verify device rebooted (check uptime)
3. May indicate install failure - check logs
4. Run rollback if needed

### HA Issues

#### HA Sync Timeout

**Symptoms:**
- `Timeout waiting for HA sync`

**Solutions:**
1. Check HA link status
2. Verify both devices can communicate
3. Increase `survey_ha_sync_timeout`
4. Check for config differences blocking sync

#### Failover Failed

**Symptoms:**
- `Failover did not complete`

**Solutions:**
1. Verify HA configuration
2. Check device priorities
3. Manual failover may be required
4. Verify preemption settings

### Debug Mode

Enable verbose output in AAP job template for detailed troubleshooting:

1. Edit Job Template
2. Set **Verbosity** to `3 (Debug)` or higher
3. Run job
4. Review detailed output

**Key debug outputs to look for:**
- `Raw software info response` - Shows available versions and download status
- `DOWNLOAD JOB FINAL STATUS` - Shows download job result
- `INSTALL JOB FINAL STATUS` - Shows install job result
- `POST-REBOOT SYSTEM INFO` - Shows version after upgrade

---

## FAQ

### Q: Can I upgrade multiple firewalls at once?

**A:** Yes, create an AAP Workflow Template that runs the job template for each firewall in sequence or parallel.

### Q: How long does an upgrade take?

**A:** Typical times:
- Download: 5-15 minutes (depends on bandwidth)
- Install: 5-10 minutes
- Reboot: 5-15 minutes
- **Total:** 15-40 minutes for full upgrade

If firmware is pre-staged, subtract download time.

### Q: What happens if the upgrade fails midway?

**A:** If `auto_rollback` is enabled (default), the playbook attempts automatic rollback. If rollback fails or is disabled, manual intervention is required.

### Q: Can I downgrade to a previous version?

**A:** Yes, use the `rollback` operation. The previous version must still be on the device (PAN-OS keeps the prior version cached).

### Q: Do I need Panorama?

**A:** Panorama is used for device discovery/validation but is not strictly required. You can modify `site.yml` to skip Panorama validation if needed.

### Q: How do I upgrade through an intermediate version?

**A:** Run the playbook multiple times:
1. Upgrade to intermediate version
2. Wait for completion
3. Upgrade to final version

### Q: Can I schedule upgrades?

**A:** Yes, use AAP's scheduling feature on the Job Template to run at specific times.

### Q: Where are backups stored?

**A:** Backups are stored on the firewall device itself as configuration snapshots, named `pre-upgrade-TIMESTAMP.xml`.

### Q: How do I check what versions are available?

**A:** On the firewall CLI:
```
request system software check
show system software
```

Or run `pre_checks_only` and check the job output.

### Q: What if I need to cancel an in-progress upgrade?

**A:** 
- If in download phase: Cancel the AAP job (download can be restarted)
- If in install phase: Do NOT cancel - may corrupt the install
- If rebooting: Wait for completion

---

## License

MIT License