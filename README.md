简体中文 | [English](./README_EN.md)

# aops-cobbler

## 介绍

aops-cobbler 是智能运维平台 A-Ops 的操作系统自动安装服务，通过 Cobbler API 管理 ISO 镜像、Kickstart 配置、裸机和安装任务，并提供安装脚本管理及状态跟踪能力。本仓库提供后端 REST API，不包含 Web 管理页面。

## 环境需求

- Python 3.9.9+；Python 依赖以 [requirements.txt](./requirements.txt) 为准。使用其他 Python 版本前，请确认这些依赖支持该版本。
- MySQL 8.0，用于保存裸机信息和安装状态。
- 可访问的 Cobbler 服务及其 API 账号。
- RPM/systemd 部署和完整装机流程需要 Linux 环境；以下部署命令面向使用 yum/dnf 的系统。容器示例使用 openEuler 22.03 LTS SP1。

完整装机还需准备以下条件：

- 配置好 Cobbler、DHCP、TFTP 和 HTTP 服务，目标主机能够通过 PXE 启动并访问安装资源及本服务的回调地址。
- 本服务能够访问目标主机的 BMC，安装 `ipmitool`，并配置有效的 BMC 账号。
- 安装后脚本需位于 `/opt/aops/script/after_os_installed.sh`。RPM 会安装该文件；从源码运行完整装机流程时，需将仓库中的 `script/after_os_installed.sh` 放到该路径。
- 应用会在拼接时自动转义内置安装后脚本和通过 `script_name` 上传的 shell 脚本中的 `$`；上传的脚本应保持普通 shell 写法。用户提交的 Kickstart 模板仍由 Cobbler/Cheetah 渲染：`rootpw --iscrypted` 中直接填写的密码散列会自动用 `#raw` 保护，`$default_password_crypted` 等 Cobbler 变量照常替换；模板中其他要保留给 shell 的 `$` 仍需写成 `\$`。过去为 Cheetah 手工转义过的独立 shell 脚本，升级后应恢复为普通 shell 写法。
- 服务进程具备 ISO loop 挂载权限，能够执行 `mount`、`umount`，并读写配置指定的上传、脚本、日志和 HTTP 资源目录。
- ISO 在本服务所在环境的 `/mnt/` 下挂载，随后该路径会传给 Cobbler 导入。部署在不同主机或容器时，必须保证 Cobbler 能在相同路径读取这些文件；仅配置远程 API 地址不足以完成导入。Kickstart、脚本及 PXE 相关目录也需按实际部署保持可访问。

## 本地开发

以下命令均从仓库根目录执行，除非另有说明。

### 1. 获取源码与安装依赖

```bash
git clone https://atomgit.com/openeuler/aops-cobbler.git
cd aops-cobbler
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

`requirements.txt` 包含 uWSGI 等带原生扩展的依赖。若需要从源码编译，请先安装 C 编译器和与当前 Python 匹配的开发头文件；使用 yum 的系统通常可安装 `gcc` 和 `python3-devel`。如需镜像源，可在 pip 命令后追加 `-i https://pypi.tuna.tsinghua.edu.cn/simple/`。

### 2. 配置服务

配置模板位于 [conf/aops-cobbler.ini](./conf/aops-cobbler.ini)。默认从 `/etc/aops/aops-cobbler.ini` 加载；本地开发可修改 [cobbled/conf/constant.py](./cobbled/conf/constant.py) 中的 `ConfigCons.BASE_CONFIG_PATH`，使其指向本仓库 `conf` 目录的绝对路径，例如：

```python
BASE_CONFIG_PATH = "/absolute/path/aops-cobbler/conf/"
```

这里填写的是**目录**，代码会自动拼接 `aops-cobbler.ini`。当前没有通过环境变量指定配置文件的入口。配置文件不存在时会使用代码内的默认值，请确认路径正确，避免误连示例数据库。

按下文的配置说明修改 INI 文件。本地开发时，将上传、脚本、HTTP 资源和日志目录设为当前用户可写的绝对路径，并提前创建目录。修改配置后需重启进程。不要提交本机路径和实际账号密码。

### 3. 初始化数据库

先准备 MySQL 实例，再执行仓库内的初始化脚本。将示例地址和管理员账号替换为实际值，密码通过提示输入：

```bash
mysql -h 127.0.0.1 -P 3306 -u root -p < database/aops-cobbler.sql
```

该脚本会创建并使用 `aops` 数据库，创建 `raw_host` 表。如果使用其他数据库名，需同时调整 SQL 脚本和配置中的 `database_name`。为应用账号授予所需表的读写权限，并将连接信息写入 `[mysql]`。

### 4. 启动服务

在已激活虚拟环境、完成配置和数据库初始化后，从仓库根目录运行：

```bash
python -m cobbled.manage
```

默认监听 `127.0.0.1:8888`。启动时也会启动安装状态检查定时任务，因此应使用开发数据库。服务验证方法见下文。

## 配置说明

下表列出需重点确认的配置项，完整配置见 [INI 模板](./conf/aops-cobbler.ini)。模板中的地址和账号仅为示例，应按部署环境替换。

| 配置项 | 模板值或默认值 | 配置要求 |
| --- | --- | --- |
| `[cobbler_client] ip / port` | `127.0.0.1` / `8888` | 服务监听地址及端口。完整装机时，`ip` 还用于生成安装回调和资源地址，应设置为目标主机可达的实际 IP。 |
| `[cobbler_server] server / user / passwd` | 示例 API 地址与账号 | 改为实际 Cobbler API 地址及凭据。 |
| `[mysql] ip / port / database_name` | 示例 IP / `3306` / `aops` | 改为实际数据库地址和库名。 |
| `[mysql] engine_format` | `mysql+pymysql://root:@%s:%s/%s` | 填写应用数据库账号和密码，保留三个 `%s`，分别由主机、端口和库名替换。账号或密码中的 URL 特殊字符需编码；由于该模板使用 Python `%` 格式化，编码中的 `%` 需写成 `%%`（例如 `@` 写为 `%%40`）。 |
| `[log] LOG_DIR` | `/var/log/aops/cobbler/` | 业务日志目录，服务用户需可写。 |
| `[iso] upload_dir / max_content_length` | `/opt/aops/cobbler/iso/upload` / `5 * 1024 * 1024 * 1024` | 上传目录和请求体大小上限，单位为字节；目录需可写并有足够空间。 |
| `[ks] http_dir` | `/var/www/html/` | HTTP 资源根目录，需可写且能通过 HTTP 提供装机资源。 |
| `[script] script_dir / max_content_length` | `/opt/aops/cobbler/script/upload` / `10240` | 脚本上传目录及单文件大小上限，单位为字节。 |
| `[host] os_start_ip / os_end_ip / subnet_mask` | 示例地址范围 / `24` | 设置可分配的装机 IP 范围及掩码，与实际装机网络保持一致。 |
| `[host] check_bmc_connection` | `1` | 是否检查 BMC 连通性，启用时需要 `ipmitool` 和可用的 BMC 网络。 |
| `[host] scheduler_interval_time / os_installed_time` | `5` / `30` | 安装状态检查间隔及安装超时，单位为分钟。 |
| `[host] rpm_search_timeout` | `30` | 每个 `yum search` 查询的超时时间，单位为秒。 |
| `[host] os_install_log_dir` | `/var/log/osinstall/` | 安装日志目录，需配合装机日志接收服务配置。 |
| `[uwsgi]` | 见模板 | RPM/systemd 启动时使用；本地 `python -m cobbled.manage` 不使用 uWSGI。 |

## 构建 RPM 包

在具备 yum、RPM 构建工具及可用软件源的 Linux 环境中执行。以下示例对应当前 spec 中的 `Version: v1.0.0`，版本变化时需同步调整文件名和归档目录前缀。

```bash
sudo yum install -y rpmdevtools python3-setuptools
rpmdev-setuptree

git archive HEAD --format=tar.gz \
  --prefix=aops-cobbler-v1.0.0/ \
  --output="$HOME/rpmbuild/SOURCES/aops-cobbler-v1.0.0.tar.gz"
cp aops-cobbler.spec "$HOME/rpmbuild/SPECS/"
rpmbuild -ba "$HOME/rpmbuild/SPECS/aops-cobbler.spec"
```

`HEAD` 表示当前已提交版本，不包含未提交改动；构建其他版本时替换为对应 tag 或 commit。归档文件名必须与 spec 的 `Source0` 一致，内部顶层目录必须与 `%autosetup -n` 一致。

二进制包输出到 `~/rpmbuild/RPMS/<架构>/`，源码包输出到 `~/rpmbuild/SRPMS/`。保留源码和脚本的 LF 换行符；仅在确认有 CRLF 问题时使用 `dos2unix` 转换。

## 安装及部署

### 1. 安装 RPM

将路径和架构替换为实际构建产物：

```bash
sudo yum localinstall -y "$HOME/rpmbuild/RPMS/x86_64/aops-cobbler-v1.0.0-1.x86_64.rpm"
```

完整装机还需准备“环境需求”中列出的系统工具和服务。

### 2. 初始化数据库与配置

按“本地开发”的数据库初始化步骤创建数据库和表，编辑 `/etc/aops/aops-cobbler.ini`，完成上表中的配置，并准备相应目录和权限。

`/opt/aops/uwsgi/cobbled.ini` 由启动脚本根据业务配置生成，修改服务设置应编辑 `/etc/aops/aops-cobbler.ini`。

### 3. 启动和检查

```bash
sudo systemctl daemon-reload
sudo systemctl start aops-cobbler
sudo systemctl status aops-cobbler
sudo journalctl -u aops-cobbler -n 100 --no-pager
sudo tail -n 100 /var/log/aops/uwsgi/aops-cobbler.log
sudo ss -lntp | grep ':8888'
```

如修改了端口或日志路径，请相应调整检查命令。需要开机自启时执行 `sudo systemctl enable aops-cobbler`；修改配置后执行 `sudo systemctl restart aops-cobbler`。

## 服务验证

将地址和端口替换为配置中的监听地址。以下只读接口返回主机导入 CSV 模板：

```bash
curl --fail --show-error --include \
  http://127.0.0.1:8888/cobbler/getHostTemplateFile
```

预期返回 HTTP `200`，响应头包含 `Content-Disposition: attachment; filename=template.csv`，正文第一行为：

```text
host_name,host_mac,bmc_ip,bmc_user_name,bmc_passwd
```

这一步只验证 API 进程和路由可用，不验证数据库、Cobbler 或完整装机链路。根路径 `/` 没有注册页面，返回 `404` 不代表服务未启动。

进一步验证时，可调用主机查询接口检查数据库访问、调用 ISO 查询接口检查 Cobbler 访问，并检查响应体中的业务结果。接口路径见 [cobbled/conf/constant.py](./cobbled/conf/constant.py)，注册关系见 [cobbled/url.py](./cobbled/url.py)，请求参数见各 `*_manager/view.py`。

## 容器部署示例

[container/](./container/) 提供 Dockerfile、Compose 文件及交互脚本。使用前需检查：

- Dockerfile 从软件源安装 `aops-cobbler` RPM，不会构建或安装当前工作区的 Python 源码。
- [软件源模板](./container/conf/aops-cobbler-install.repo) 使用内网地址，需替换为可访问且包含所需软件包的源。
- Compose 使用 host 网络、特权模式及宿主机目录挂载，容器内运行 systemd。
- `run.sh` 会安装工具并将模板复制到宿主机 `/etc/aops/`、`/etc/cobbler/` 和 `/var/lib/cobbler/` 等目录；使用前应检查现有配置并修改模板。

准备完成后，在 `container` 目录运行 `sudo bash run.sh`，按提示输入 `build`、`start-service` 或 `stop-service`。脚本使用 `docker-compose` 命令，需确保其可用且 Docker 服务已启动。该示例仍需按实际网络配置 Cobbler、数据库及装机服务。

## 停止及卸载

```bash
sudo systemctl stop aops-cobbler
sudo systemctl status aops-cobbler
sudo yum remove -y aops-cobbler
```

停止后状态应显示为 `inactive`；此时 `systemctl status` 返回非零退出码属于正常情况。卸载 RPM 不等同于清理数据库、上传镜像和运行日志，应根据需要单独处理这些数据。

## 开发与测试

主要目录：

| 路径 | 用途 |
| --- | --- |
| `cobbled/` | API 入口、业务模块、数据库访问及工具函数 |
| `cobbled/tests/` | 单元测试、回归测试及手动联调脚本 |
| `conf/` | 业务配置模板 |
| `database/` | 数据库初始化 SQL |
| `script/` | 操作系统安装后执行的脚本 |
| `container/` | 容器部署示例 |

安装依赖并完成本地配置后，在仓库根目录运行：

```bash
python -m unittest discover -s cobbled/tests -p 'test_*.py' -v
```

测试导入业务模块时可能初始化配置、日志、上传目录或调度器，应使用开发配置及可写目录。`cobbled/tests/server/` 下的脚本用于手动连接真实 Cobbler，其中包含修改远端配置的操作；不应将它们直接作为只读健康检查运行。

## 常用文件与排查

| 文件 | 用途 |
| --- | --- |
| `/etc/aops/aops-cobbler.ini` | 业务配置 |
| `/var/log/aops/cobbler/aops-cobbler.log` | 业务日志（默认路径） |
| `/opt/aops/uwsgi/cobbled.ini` | 启动时生成的 uWSGI 配置 |
| `/var/log/aops/uwsgi/aops-cobbler.log` | uWSGI 日志（默认路径） |

- 模块导入失败：确认使用的 Python 环境与安装依赖的环境相同。
- 数据库连接失败：检查地址、账号、`engine_format`、数据库和 `raw_host` 表。
- 目录权限或 ISO 挂载失败：检查服务用户权限、磁盘空间及容器挂载权限。
- Cobbler 导入失败：检查 API 凭据，以及 Cobbler 是否能读取传入的 ISO 挂载路径。

## 参与贡献

1. Fork 本仓库并创建功能或修复分支。
2. 完成修改，运行与改动相关的测试。
3. 涉及使用方式的变更，同步更新中英文 README。
4. 提交 Pull Request，说明变更目的和验证结果。

## 许可证

本项目采用 [木兰宽松许可证第 2 版（Mulan PSL v2）](./LICENSE)。
