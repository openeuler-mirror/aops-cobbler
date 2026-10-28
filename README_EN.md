English | [简体中文](./README.md)

# aops-cobbler

## Overview

aops-cobbler is the automated operating system installation service of the A-Ops platform. It uses the Cobbler API to manage ISO images, Kickstart configurations, bare-metal hosts, and installation tasks, with installation script management and status tracking. This repository provides a REST API backend and does not include a web management UI.

## Requirements

- Python 3.9.9+. Python dependencies are defined in [requirements.txt](./requirements.txt). Check dependency compatibility before using a different Python version.
- MySQL 8.0 for host information and installation status.
- An accessible Cobbler server and API credentials.
- Linux for RPM/systemd deployment and the complete installation workflow. The deployment commands below target systems using yum/dnf. The container example uses openEuler 22.03 LTS SP1.

The complete installation workflow also requires:

- Configured Cobbler, DHCP, TFTP, and HTTP services. Target hosts must be able to boot through PXE and reach installation resources and this service's callback address.
- BMC connectivity from this service to target hosts, `ipmitool`, and valid BMC credentials.
- The post-installation script at `/opt/aops/script/after_os_installed.sh`. The RPM installs this file; when running the complete workflow from source, place the repository's `script/after_os_installed.sh` at that path.
- The application escapes `$` in the built-in post-installation script and shell scripts uploaded through `script_name` when appending them to Kickstart. Upload those scripts as ordinary shell scripts; remove any Cheetah-specific escaping from existing standalone scripts after upgrading. User-provided Kickstart templates are still rendered by Cobbler/Cheetah: literal hashes in `rootpw --iscrypted` are protected with `#raw`, while Cobbler variables such as `$default_password_crypted` still render. Write `\$` for other dollar signs in the template that must survive for the shell.
- Permission to loop-mount ISO images, execute `mount` and `umount`, and read/write the configured upload, script, log, and HTTP resource directories.
- ISO images are mounted under `/mnt/` in this service's environment, and that path is passed to Cobbler for import. When deploying across hosts or containers, Cobbler must be able to read the files at the same path; a remote API address alone is insufficient. Kickstart, script, and PXE directories must also be accessible as required by the deployment.

## Local Development

Run commands from the repository root unless stated otherwise.

### 1. Get the Source and Install Dependencies

```bash
git clone https://atomgit.com/openeuler/aops-cobbler.git
cd aops-cobbler
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

`requirements.txt` includes dependencies with native extensions, such as uWSGI. Source builds require a C compiler and development headers matching your Python installation; systems using yum commonly provide `gcc` and `python3-devel`. To use a package mirror, append `-i https://pypi.tuna.tsinghua.edu.cn/simple/` to the pip command.

### 2. Configure the Service

The configuration template is [conf/aops-cobbler.ini](./conf/aops-cobbler.ini). The default configuration location is `/etc/aops/aops-cobbler.ini`. For local development, edit `ConfigCons.BASE_CONFIG_PATH` in [cobbled/conf/constant.py](./cobbled/conf/constant.py) to point to the absolute path of the repository's `conf` directory, for example:

```python
BASE_CONFIG_PATH = "/absolute/path/aops-cobbler/conf/"
```

This value must be a **directory**; the code appends `aops-cobbler.ini`. There is currently no environment variable for selecting the configuration file. If the file is missing, the code uses its built-in defaults. Check the path to avoid connecting to the example database by mistake.

Update the INI file using the configuration reference below. For local development, use absolute paths writable by your user for uploads, scripts, HTTP resources, and logs, and create the directories first. Restart the process after changing configuration. Do not commit local paths or real credentials.

### 3. Initialize the Database

Prepare a MySQL instance, then run the initialization script. Replace the example address and administrator account with your actual values; enter the password at the prompt:

```bash
mysql -h 127.0.0.1 -P 3306 -u root -p < database/aops-cobbler.sql
```

The script creates and selects the `aops` database and creates the `raw_host` table. To use another database name, update both the SQL script and the `database_name` configuration value. Grant the application account the required table read/write permissions and configure its connection under `[mysql]`.

### 4. Start the Service

With the virtual environment active, configuration complete, and database initialized, run from the repository root:

```bash
python -m cobbled.manage
```

The default address is `127.0.0.1:8888`. Startup also enables the scheduled installation status checks, so use a development database. See Service Verification below.

## Configuration Reference

Review the following settings before deployment. See the [INI template](./conf/aops-cobbler.ini) for the full configuration. Addresses and credentials in the template are examples and must be adapted to your environment.

| Setting | Template or default value | Configuration requirement |
| --- | --- | --- |
| `[cobbler_client] ip / port` | `127.0.0.1` / `8888` | Listen address and port. The installation workflow also uses `ip` to generate callback and resource URLs; use an actual IP reachable by target hosts. |
| `[cobbler_server] server / user / passwd` | Example API address and credentials | Set the actual Cobbler API address and credentials. |
| `[mysql] ip / port / database_name` | Example IP / `3306` / `aops` | Set the actual database address and name. |
| `[mysql] engine_format` | `mysql+pymysql://root:@%s:%s/%s` | Set the application database username and password. Keep the three `%s` placeholders for host, port, and database name. URL-encode special characters in credentials. This template uses Python `%` formatting, so write encoded percent signs as `%%` (for example, encode `@` as `%%40`). |
| `[log] LOG_DIR` | `/var/log/aops/cobbler/` | Application log directory, writable by the service user. |
| `[iso] upload_dir / max_content_length` | `/opt/aops/cobbler/iso/upload` / `5 * 1024 * 1024 * 1024` | Upload directory and request body limit in bytes. The directory must be writable and have sufficient space. |
| `[ks] http_dir` | `/var/www/html/` | HTTP resource root, writable and served over HTTP for installation resources. |
| `[script] script_dir / max_content_length` | `/opt/aops/cobbler/script/upload` / `10240` | Script upload directory and per-file size limit in bytes. |
| `[host] os_start_ip / os_end_ip / subnet_mask` | Example address range / `24` | Available installation IP range and subnet mask, matching the installation network. |
| `[host] check_bmc_connection` | `1` | Enables BMC connectivity checks, requiring `ipmitool` and BMC network access. |
| `[host] scheduler_interval_time / os_installed_time` | `5` / `30` | Installation status check interval and installation timeout in minutes. |
| `[host] os_install_log_dir` | `/var/log/osinstall/` | Installation log directory; configure the installation log receiver accordingly. |
| `[uwsgi]` | See template | Used for RPM/systemd startup; local `python -m cobbled.manage` does not use uWSGI. |

## Building RPM Packages

Use a Linux environment with yum, RPM build tools, and accessible package repositories. This example matches the current spec's `Version: v1.0.0`. If the version changes, update both the archive filename and directory prefix.

```bash
sudo yum install -y rpmdevtools python3-setuptools
rpmdev-setuptree

git archive HEAD --format=tar.gz \
  --prefix=aops-cobbler-v1.0.0/ \
  --output="$HOME/rpmbuild/SOURCES/aops-cobbler-v1.0.0.tar.gz"
cp aops-cobbler.spec "$HOME/rpmbuild/SPECS/"
rpmbuild -ba "$HOME/rpmbuild/SPECS/aops-cobbler.spec"
```

`HEAD` selects the current committed revision and excludes uncommitted changes. Replace it with a tag or commit to build another revision. The archive filename must match `Source0`, and its top-level directory must match `%autosetup -n` in the spec.

Binary packages are written to `~/rpmbuild/RPMS/<architecture>/` and source packages to `~/rpmbuild/SRPMS/`. Keep LF line endings in source files and scripts; use `dos2unix` only when a CRLF issue has been confirmed.

## Installation and Deployment

### 1. Install the RPM

Replace the path and architecture with the actual build output:

```bash
sudo yum localinstall -y "$HOME/rpmbuild/RPMS/x86_64/aops-cobbler-v1.0.0-1.x86_64.rpm"
```

`validators` is replaced by standard library heplers, so no separate package is needed. The complete installation workflow also requires the tools and services listed under Requirements.

### 2. Initialize the Database and Configure the Service

Follow the database initialization steps under Local Development to create the database and table. Edit `/etc/aops/aops-cobbler.ini`, complete the configuration above, and prepare the directories and permissions.

The startup script generates `/opt/aops/uwsgi/cobbled.ini` from the application configuration. Edit `/etc/aops/aops-cobbler.ini` when changing service settings.

### 3. Start and Inspect the Service

```bash
sudo systemctl daemon-reload
sudo systemctl start aops-cobbler
sudo systemctl status aops-cobbler
sudo journalctl -u aops-cobbler -n 100 --no-pager
sudo tail -n 100 /var/log/aops/uwsgi/aops-cobbler.log
sudo ss -lntp | grep ':8888'
```

Adjust the checks if you changed the port or log path. To start at boot, run `sudo systemctl enable aops-cobbler`. After configuration changes, run `sudo systemctl restart aops-cobbler`.

## Service Verification

Replace the address and port with your configured listen address. This read-only endpoint returns a host import CSV template:

```bash
curl --fail --show-error --include \
  http://127.0.0.1:8888/cobbler/getHostTemplateFile
```

Expect HTTP `200`, a `Content-Disposition: attachment; filename=template.csv` header, and this first line in the response body:

```text
host_name,host_mac,bmc_ip,bmc_user_name,bmc_passwd
```

This checks only the API process and route, not database connectivity, Cobbler connectivity, or the full installation workflow. There is no page registered at `/`; a `404` there does not mean the service failed to start.

For further checks, use the host query endpoint to exercise database access and the ISO query endpoint to exercise Cobbler access, and inspect the business result in the response body. API paths are defined in [cobbled/conf/constant.py](./cobbled/conf/constant.py), registration in [cobbled/url.py](./cobbled/url.py), and request parameters in each `*_manager/view.py`.

## Container Deployment Example

[container/](./container/) contains a Dockerfile, Compose file, and interactive script. Before use, review these requirements:

- The Dockerfile installs the `aops-cobbler` RPM from a package repository; it does not build or install Python source from the current working tree.
- The [repository template](./container/conf/aops-cobbler-install.repo) uses an internal network address. Replace it with an accessible repository containing the required packages.
- Compose uses host networking, privileged mode, and host directory mounts. The container runs systemd.
- `run.sh` installs tools and copies templates into host directories including `/etc/aops/`, `/etc/cobbler/`, and `/var/lib/cobbler/`. Review existing configuration and update the templates before use.

Once prepared, run `sudo bash run.sh` from the `container` directory and enter `build`, `start-service`, or `stop-service` as prompted. The script uses `docker-compose`; ensure that command is available and the Docker service is running. You must still configure Cobbler, the database, and installation services for your network.

## Stopping and Uninstalling

```bash
sudo systemctl stop aops-cobbler
sudo systemctl status aops-cobbler
sudo yum remove -y aops-cobbler
```

After stopping, the status should be `inactive`; a nonzero exit code from `systemctl status` is expected in this state. Removing the RPM does not constitute cleanup of the database, uploaded images, or runtime logs. Handle those separately as needed.

## Development and Tests

Main directories:

| Path | Purpose |
| --- | --- |
| `cobbled/` | API entry point, business modules, database access, and utilities |
| `cobbled/tests/` | Unit tests, regression tests, and manual integration scripts |
| `conf/` | Application configuration template |
| `database/` | Database initialization SQL |
| `script/` | Post-installation scripts |
| `container/` | Container deployment example |

After installing dependencies and completing local configuration, run from the repository root:

```bash
python -m unittest discover -s cobbled/tests -p 'test_*.py' -v
```

Importing application modules in tests may initialize configuration, logs, upload directories, or the scheduler. Use development configuration and writable directories. Scripts in `cobbled/tests/server/` manually connect to a real Cobbler instance and include operations that change remote configuration; do not run them as read-only health checks.

## Common Files and Troubleshooting

| File | Purpose |
| --- | --- |
| `/etc/aops/aops-cobbler.ini` | Application configuration |
| `/var/log/aops/cobbler/aops-cobbler.log` | Application log (default path) |
| `/opt/aops/uwsgi/cobbled.ini` | uWSGI configuration generated at startup |
| `/var/log/aops/uwsgi/aops-cobbler.log` | uWSGI log (default path) |

- Import errors: confirm the service uses the Python environment where dependencies were installed.
- Database connection errors: check the address, credentials, `engine_format`, database, and `raw_host` table.
- Directory permission or ISO mount errors: check service user permissions, disk space, and container mount permissions.
- Cobbler import errors: check API credentials and whether Cobbler can read the supplied ISO mount path.

## Contributing

1. Fork this repository and create a feature or fix branch.
2. Make your changes and run relevant tests.
3. Update both README languages when usage changes.
4. Submit a pull request describing the purpose and verification results.

## License

This project is licensed under the [Mulan Permissive Software License, Version 2 (Mulan PSL v2)](./LICENSE).
