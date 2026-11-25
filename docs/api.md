# aops-cobbler REST API 参考文档

## 1. 概述与通用约定

- **基础地址**：`http://<cobbler_client.ip>:<cobbler_client.port>`（本地开发默认 `http://127.0.0.1:8888`）。
- **路由与鉴权**：所有接口均挂载在 `/cobbler/` 路径下，无版本前缀，无内置身份认证或 TLS；生产环境应部署在隔离的管理网段内。
- **配置依赖**：本页提及的 `[iso]`、`[ks]`、`[script]`、`[host]` 等配置项均位于服务配置文件（默认 `/etc/aops/aops-cobbler.ini`），详见 [README.md](../README.md)。

### 请求体格式差异

1. **`application/json`（JSON 对象）**：除下方明确标注为 `multipart/form-data` 或 `GET` 之外的 15 个 `POST` 接口均要求请求体为 JSON 对象。若请求体不是合法 JSON 对象（例如数组、纯字符串或空 body），服务直接返回 HTTP `400`：
   ```json
   {
     "code": 400,
     "msg": "Request body must be a JSON object."
   }
   ```
2. **`multipart/form-data`（表单文件上传）**：
   - `POST /cobbler/uploadISO`：文件字段名为 `file`。
   - `POST /cobbler/uploadScript`：文件字段名为 `script_file`。
3. **无请求体（`GET`）**：`GET /cobbler/queryISO`、`GET /cobbler/getHostTemplateFile`。

### 响应格式差异

> [!IMPORTANT]
> 本服务的响应结构随接口类型而不同，调用方不可假设所有接口都返回 `{"code", "msg", "data"}`。

1. **标准 JSON 包裹格式**（绝大多数写接口、`queryHosts`、`autoInstall`、`notify`）：
   - HTTP 状态码与响应体中的 `code` 字段保持一致（`200` / `400` / `500`）。
   - 成功/失败结构：`{"code": <int>, "msg": "<str>"}`，部分接口附带 `"data"` 字段：`{"code": <int>, "msg": "<str>", "data": ...}`。
2. **裸 JSON 数组**（HTTP `200`，无 `code`/`msg` 外层包裹）：
   - `GET /cobbler/queryISO`
   - `POST /cobbler/queryKickstart`
   - `POST /cobbler/queryScript`
3. **二进制文件流**：
   - `GET /cobbler/getHostTemplateFile`：返回 CSV 附件流（`template.csv`）。
   - `POST /cobbler/downloadLogFile`：成功时返回 `.zip` 附件流；参数校验失败或文件不存在时返回 HTTP `400` 标准 JSON。

### 状态枚举

#### 主机状态 `status`

| 值 | 含义 | 说明 |
| --- | --- | --- |
| `0` | 裸机 | 新增主机的默认状态，尚未发起或完成装机。 |
| `1` | 已安装 | 已收到对应轮次的安装成功回调。 |
| `2` | 已纳管 | 主机处于已纳管状态。 |
| `3` | 装机中 | 已受理装机并预留安装轮次，正在安装或等待结果。 |
| `4` | 安装失败 | 装机启动异常、安装后脚本主动上报失败或调度超时判失败。 |

#### 清理任务状态 `cleanup.state`

| 值 | 含义 | 说明 |
| --- | --- | --- |
| `none` | 无任务 | 尚无安装清理记录。 |
| `pending` | 待清理 | 已有安装结果，但远端 Cobbler system 清理及 DHCP 同步尚未完成；期间禁止对该主机再次装机、编辑或删除。 |
| `done` | 已完成 | 最近一轮次的 Cobbler system 已删除且 DHCP 已同步。 |

### 通用命名与校验规则

| 字段 | 校验规则 | 补充说明 |
| --- | --- | --- |
| `host_id` / `installation_round` | 合法 UUID 字符串（`8-4-4-4-12` 十六进制格式） | `/cobbler/notify` 的 `installation_round` 严格要求标准小写带连字符格式（`str(UUID(v)) == v`）。 |
| `host_name` | 1–63 个字符；按 `.` 分段后每段仅含 `[A-Za-z0-9-]`，且每段首尾不得为 `-` | 与数据库 `raw_host.host_name` 列宽一致。 |
| `host_mac` | 48 位 MAC 地址，冒号 `:` 或连字符 `-` 分隔 | 入库与查重时统一转为小写。 |
| `bmc_ip` / `host_ip` / `gateway` | 点分十进制 IPv4 地址（不含 CIDR 掩码） | — |
| `bmc_user_name` / `bmc_passwd` | 非空字符串，长度 1–128 | 仅做字符串长度限制；库内存储加密后的 `bmc_passwd`。 |
| `iso_name` | 仅含 `[A-Za-z0-9_-]`，长度 1–128 | **不得包含** `-x86`、`_x86`、`-aarch64`、`_aarch64`；调用时**不带**架构后缀与 `.iso`。 |
| `arch` | 必须包含在配置项 `[iso] arch` 中 | 默认允许 `x86_64` 或 `aarch64`。 |
| `ks_name` | 仅含 `[A-Za-z0-9_-]`，长度 1–128 | 增删改与装机时**不带** `.ks` 后缀；`queryKickstart` 返回值带 `.ks`。 |
| `script_name` | 仅含 `[A-Za-z0-9_-]`，长度 1–128 | 上传/删除/装机时**不带** `.sh` 后缀；`queryScript` 返回值带 `.sh`。 |

---

## 2. 接口总览

| 分类 | 方法 | 路径 | 请求类型 | 响应类型 | 用途 |
| --- | --- | --- | --- | --- | --- |
| 镜像管理 | `POST` | `/cobbler/uploadISO` | `multipart/form-data` | 标准 JSON | 上传并异步导入 ISO 镜像 |
| 镜像管理 | `GET` | `/cobbler/queryISO` | 无 | 裸 JSON 数组 | 查询已导入的 ISO 镜像列表 |
| 镜像管理 | `POST` | `/cobbler/deleteISO` | `application/json` | 标准 JSON | 删除 Cobbler 中的镜像及本地文件 |
| Kickstart 管理 | `POST` | `/cobbler/addKickstart` | `application/json` | 标准 JSON | 新增 Kickstart 模板 |
| Kickstart 管理 | `POST` | `/cobbler/queryKickstart` | `application/json` | 裸 JSON 数组 | 查询 Kickstart 模板列表 |
| Kickstart 管理 | `POST` | `/cobbler/updateKickstart` | `application/json` | 标准 JSON | 更新 Kickstart 模板 |
| Kickstart 管理 | `POST` | `/cobbler/deleteKickstart` | `application/json` | 标准 JSON | 删除 Kickstart 模板 |
| 脚本管理 | `POST` | `/cobbler/uploadScript` | `multipart/form-data` | 标准 JSON | 上传安装后自定义 Shell 脚本 |
| 脚本管理 | `POST` | `/cobbler/queryScript` | `application/json` | 裸 JSON 数组 | 查询自定义脚本列表 |
| 脚本管理 | `POST` | `/cobbler/deleteScript` | `application/json` | 标准 JSON | 删除自定义脚本 |
| 主机管理 | `POST` | `/cobbler/addHost` | `application/json` | 标准 JSON | 添加单台裸机 |
| 主机管理 | `POST` | `/cobbler/batchAddHost` | `application/json` | 标准 JSON（含明细） | 批量添加裸机 |
| 主机管理 | `POST` | `/cobbler/updateHost` | `application/json` | 标准 JSON | 更新裸机信息 |
| 主机管理 | `POST` | `/cobbler/deleteHost` | `application/json` | 标准 JSON | 批量删除裸机 |
| 主机管理 | `POST` | `/cobbler/queryHosts` | `application/json` | 标准 JSON（分页） | 分页查询裸机及清理状态 |
| 主机管理 | `GET` | `/cobbler/getHostTemplateFile` | 无 | CSV 文件流 | 下载主机批量导入 CSV 模板 |
| 自动装机 | `POST` | `/cobbler/autoInstall` | `application/json` | 标准 JSON（部分成功） | 为一批主机发起自动装机 |
| 自动装机 | `POST` | `/cobbler/notify` | `application/json` | 标准 JSON | 接收装机完成/失败回调通知 |
| 自动装机 | `POST` | `/cobbler/downloadLogFile` | `application/json` | ZIP 文件流 / JSON | 打包下载单台主机的安装日志 |

---

## 3. 分模块详细说明

### 一、镜像管理（ISO）

#### 1. 上传并导入镜像：`POST /cobbler/uploadISO`

将 `.iso` 文件上传到 `[iso] upload_dir`（保存为 `<iso_name>-<arch>.iso` 及对应的 `.txt` SHA-256 校验文件），只读 loop 挂载到 `/mnt/<iso_name>-<arch>`，并调用 Cobbler `background_import` 异步导入（distro 名称为 `<iso_name>-<arch>`）。

- **请求类型**：`multipart/form-data`（请求体大小受 `[iso] max_content_length` 限制，默认 5 GiB）。
- **表单字段**：
  - `file`（文件，必填）：上传的镜像文件，文件名后缀必须为 `.iso`。
  - `iso_name`（文本，必填）：镜像基础名称，满足 `iso_name` 校验规则。
  - `arch`（文本，必填）：镜像架构，必须在 `[iso] arch` 允许列表中（默认 `x86_64` 或 `aarch64`）。
- **响应**：
  - `200`：`{"code": 200, "msg": "The iso background import in progress, please refresh the query list later."}`
  - `400`：参数缺失/校验失败，或 Cobbler 中已存在 `<iso_name>-<arch>` distro。
  - `500`：挂载失败（`Failed to mount the iso file.`）或远端 Cobbler 异常。

```bash
curl --fail-with-body \
  -F "file=@/path/to/openEuler-24.03-LTS-x86_64-dvd.iso" \
  -F "iso_name=openEuler-24.03-LTS" \
  -F "arch=x86_64" \
  http://127.0.0.1:8888/cobbler/uploadISO
```

#### 2. 查询镜像列表：`GET /cobbler/queryISO`

从远端 Cobbler 查询已导入的 distro 列表，按创建时间（`ctime`）降序返回。

- **请求参数**：无。
- **响应**：HTTP `200`，直接返回 **JSON 数组**：
  - `iso_name`（string）：补全 `.iso` 后缀的名称（如 `"openEuler-24.03-LTS.iso"`）。
  - `arch`（string）：架构（如 `"x86_64"`）。
  - `iso_size`（int）：本地镜像文件大小（字节）；本地文件不存在时为 `0`。
  - `iso_sha256_value`（string）：上传时计算的 SHA-256 摘要；校验文件不存在时为 `""`。
- **注意**：当连接或查询 Cobbler 失败时，接口会记录错误日志并返回空数组 `[]`。

```bash
curl -s http://127.0.0.1:8888/cobbler/queryISO
```

```json
[
  {
    "iso_name": "openEuler-24.03-LTS.iso",
    "arch": "x86_64",
    "iso_size": 4380917760,
    "iso_sha256_value": "e3b0c44298fc1c149afbf4c8996fb924..."
  }
]
```

#### 3. 删除镜像：`POST /cobbler/deleteISO`

卸载 `/mnt/<iso_name>-<arch>`，从 Cobbler 删除对应的 profile 和 distro 并执行 `sync`，最后删除本地 `.iso`、`.txt` 及挂载点目录（同基础名无其他架构共用时一并清理旧版无架构后缀文件）。

- **请求体**（JSON）：
  - `iso_name`（string，必填）：镜像基础名称（不含架构和 `.iso`）。
  - `arch`（string，必填）：镜像架构。
- **响应**：
  - `200`：`{"code": 200, "msg": "The iso delete successfully."}`
  - `400`：参数非法，或 Cobbler、挂载点及本地目录中均不存在该镜像（`The iso file not exists in remote cobbler server.`）。
  - `500`：卸载、删除或同步过程中出现异常。

```bash
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"iso_name":"openEuler-24.03-LTS","arch":"x86_64"}' \
  http://127.0.0.1:8888/cobbler/deleteISO
```

---

### 二、Kickstart 模板管理

#### 4. 新增 Kickstart 模板：`POST /cobbler/addKickstart`

使用本机 `ksvalidator` 校验 Kickstart 语法后，保存到 `[ks] http_dir` 下的 `ks/<ks_name>.ks`。

- **请求体**（JSON）：
  - `ks_name`（string，必填）：模板名称（不含 `.ks`）。
  - `ks_content`（string，必填）：非空的 Kickstart 文本内容。
- **响应**：
  - `200`：`{"code": 200, "msg": "The kickstart add successfully."}`
  - `400`：参数校验失败或 `ksvalidator` 校验报错（`msg` 为 `ksvalidator` 的标准错误输出）。
- **注意**：若同名 `<ks_name>.ks` 文件已存在，该接口会直接覆盖原文件。

```bash
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"ks_name":"oe2403-default","ks_content":"lang en_US.UTF-8\n..."}' \
  http://127.0.0.1:8888/cobbler/addKickstart
```

#### 5. 查询 Kickstart 模板：`POST /cobbler/queryKickstart`

按文件修改时间降序返回 `[ks] http_dir/ks/` 目录下的 `.ks` 文件列表（忽略非 `.ks` 文件及子目录）。

- **请求体**（JSON）：
  - `ks_name`（string，可选）：按子串模糊过滤文件名；省略、为 `null` 或 `""` 时返回全部模板。至少需传入 `{}`。
- **响应**：HTTP `200`，直接返回 **JSON 数组**：
  - `ks_name`（string）：含 `.ks` 后缀的文件名。
  - `ks_content`（string）：模板文件原始内容。
  - `ks_address`（string）：拼接自 `[cobbler_client] ip`，格式为 `http://<ip>/ks/<ks_name>`。

```bash
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"ks_name":"oe2403"}' \
  http://127.0.0.1:8888/cobbler/queryKickstart
```

```json
[
  {
    "ks_name": "oe2403-default.ks",
    "ks_content": "lang en_US.UTF-8\n...",
    "ks_address": "http://127.0.0.1/ks/oe2403-default.ks"
  }
]
```

#### 6. 更新 Kickstart 模板：`POST /cobbler/updateKickstart`

校验目标 `<ks_name>.ks` 已存在，通过 `ksvalidator` 语法检查后覆盖写入。

- **请求体**（JSON）：`ks_name`（string，必填）、`ks_content`（string，必填）。
- **响应**：
  - `200`：`{"code": 200, "msg": "The kickstart update successfully."}`
  - `400`：模板不存在（`The kickstart file not exist.`）、参数非法或语法校验失败。

#### 7. 删除 Kickstart 模板：`POST /cobbler/deleteKickstart`

删除 `[ks] http_dir/ks/<ks_name>.ks`。

- **请求体**（JSON）：`ks_name`（string，必填，不含 `.ks`）。
- **响应**：
  - `200`：`{"code": 200, "msg": "The kickstart delete successfully."}`
  - `400`：参数非法或模板不存在。

---

### 三、装机脚本管理

#### 8. 上传安装后脚本：`POST /cobbler/uploadScript`

上传自定义 Shell 脚本至 `[script] script_dir`（保存为 `<script_name>.sh`），用于后续 `/cobbler/autoInstall` 时追加到 Kickstart 的 `%post` 段执行。

- **请求类型**：`multipart/form-data`。
- **表单字段**：
  - `script_file`（文件，必填）：文件后缀必须为 `.sh`，大小不得超过 `[script] max_content_length`（默认 `10240` 字节），上传前会执行 `bash -n` 语法检查。
  - `script_name`（文本，必填）：脚本名称（不含 `.sh`）。
- **说明**：
  - 应直接上传普通 Shell 脚本，无需手工为 Cobbler/Cheetah 转义 `$`（装机流程在拼接时会自动转义）。
  - 若同名 `<script_name>.sh` 已存在会直接覆盖。
- **响应**：
  - `200`：`{"code": 200, "msg": "The script file upload successfully."}`
  - `400`：参数非法、文件超限或 `bash -n` 语法检查失败。
  - `500`：文件写入异常。

```bash
curl --fail-with-body \
  -F "script_file=@./post_init.sh" \
  -F "script_name=post_init" \
  http://127.0.0.1:8888/cobbler/uploadScript
```

#### 9. 查询脚本列表：`POST /cobbler/queryScript`

按文件修改时间降序返回 `[script] script_dir` 中的脚本文件列表。

- **请求体**（JSON）：
  - `script_name`（string，可选）：按子串过滤文件名；省略、为 `null` 或 `""` 时返回全部。至少需传入 `{}`。
- **响应**：HTTP `200`，直接返回 **JSON 数组**：
  - `script_name`（string）：含 `.sh` 后缀的文件名。
  - `script_content`（string）：脚本文件内容。

#### 10. 删除脚本：`POST /cobbler/deleteScript`

删除 `[script] script_dir/<script_name>.sh`。

- **请求体**（JSON）：`script_name`（string，必填，不含 `.sh`）。
- **响应**：
  - `200`：`{"code": 200, "msg": "The script file delete successfully."}`
  - `400`：参数非法或脚本不存在（`The script file not exist.`）。

---

### 四、主机管理

#### 11. 添加单台主机：`POST /cobbler/addHost`

向 `raw_host` 表录入一台裸机信息；当 `[host] check_bmc_connection` 非 `0` 时，入库前会执行 `ipmitool ... power status` 验证 BMC 连通性。

- **请求体**（JSON）：
  - `host_name`（string，必填）：主机名。
  - `host_mac`（string，必填）：PXE 网卡 MAC 地址（入库转小写）。
  - `bmc_ip`（string，必填）：BMC IPv4 地址。
  - `bmc_user_name`（string，必填）：BMC 用户名。
  - `bmc_passwd`（string，必填）：BMC 密码（入库时加密）。
  - `host_id`（string，可选）：UUID；省略、`null` 或 `""` 时由服务端自动生成。
  - `host_ip`（string，可选）：业务/装机 IPv4；省略、`null` 或 `""` 时置空。
  - `status`（int，可选）：`0`–`4` 整数（省略或 `null` 时数据库默认 `0`；传入 `""` 或布尔值会校验失败）。
  - 其余未列出的字段会被静默忽略（不会写入数据库）。
- **校验与查重**：`bmc_ip` 与 `host_mac`（大小写不敏感）在库中均不能重复。
- **响应**：
  - `200`：`{"code": 200, "msg": "The host add successfully."}`
  - `400`：字段校验失败、BMC 连通性检查失败、IP/MAC 重复或入库失败。

```bash
curl -s -X POST -H "Content-Type: application/json" \
  -d '{
    "host_name": "node-01",
    "host_mac": "52:54:00:ab:cd:10",
    "bmc_ip": "10.10.10.1",
    "bmc_user_name": "admin",
    "bmc_passwd": "Password123"
  }' \
  http://127.0.0.1:8888/cobbler/addHost
```

#### 12. 批量添加主机：`POST /cobbler/batchAddHost`

一次提交最多 100 台主机；逐条执行字段校验、BMC 连通性检查以及批内和库内的 `host_mac`/`bmc_ip` 查重，仅将校验通过的主机批量写入数据库。

- **请求体**（JSON）：
  - `host_list`（array\<object\>，必填）：长度 1–100，每个元素字段规范同 `/cobbler/addHost`。
- **响应**：
  - `200`（全部或部分校验通过并成功批量入库时；即使存在单条校验失败也返回 `200`）：
    ```json
    {
      "code": 200,
      "msg": "Batch add hosts successfully.",
      "data": {
        "result": [
          {
            "host_name": "bad-node",
            "host_mac": "invalid",
            "bmc_ip": "10.10.10.2",
            "bmc_user_name": "admin",
            "bmc_passwd": "Password123",
            "result": "failed",
            "reason": "The host_mac can not be none and must comply with mac rules."
          },
          {
            "host_name": "node-01",
            "host_mac": "52:54:00:ab:cd:10",
            "bmc_ip": "10.10.10.1",
            "bmc_user_name": "admin",
            "bmc_passwd": "Password123",
            "result": "succeed",
            "reason": ""
          }
        ]
      }
    }
    ```
  - `400`：`host_list` 本身格式/长度非法，或预查询/批量入库数据库操作失败（返回 `data.result` 明细）。
- **注意**：
  - `data.result` 中**失败项排在前面**（保留原始顺序），**校验成功项排在后面**。
  - 返回明细中成功项的 `bmc_passwd` 会回显请求原文，数据库内存储加密后的密文。

#### 13. 更新主机信息：`POST /cobbler/updateHost`

按 `host_id` 更新主机全量可编辑字段（该接口对必填字段要求完整传入）。

- **请求体**（JSON）：
  - `host_id`（string，必填）：目标主机 UUID。
  - `status`（int，必填）：目标状态，必须为 `0`–`4` 的整数。
  - `host_name`、`host_mac`、`bmc_ip`、`bmc_user_name`、`bmc_passwd`（string，均必填）。
  - `host_ip`（string，可选）。
- **业务限制与细节**：
  - 若请求中的 `bmc_passwd` 与数据库现有密文一致（例如前端回传 `queryHosts` 拿到的密文），则保留原值不重复加密；否则当作明文重新加密保存。
  - **并发与生命周期保护**：当主机正在装机中（已有 `installation_round` 且 `status == 3`）或存在未完成的清理任务（`cleanup.state != "done"`）时，拒绝更新并返回 `400`；此外，已有 `installation_round` 的主机不允许通过此接口更改 `status`。
  - 会检查与其他主机的 `bmc_ip`、`host_mac` 是否冲突。
- **响应**：
  - `200`：`{"code": 200, "msg": "The host update successfully."}`
  - `400`：校验失败、主机不存在、冲突或处于装机/待清理状态。

#### 14. 删除主机：`POST /cobbler/deleteHost`

按 `host_id` 列表批量删除主机及关联的清理任务记录。

- **请求体**（JSON）：
  - `host_list`（array\<string\>，必填）：1–100 个主机 UUID 字符串。
- **原子性与限制**：
  - 若 `host_list` 中**任一**主机处于装机中或清理未完成（`cleanup.state != "done"`），整个事务回滚，所有主机均不删除，返回 HTTP `400`（`The host delete failed.`）。
- **响应**：
  - `200`：`{"code": 200, "msg": "The host delete successfully."}`
  - `400`：参数非法或删除失败。

#### 15. 分页查询主机：`POST /cobbler/queryHosts`

分页查询主机信息及最近一轮次的安装收尾状态，按 `update_time` 降序返回。

- **请求体**（JSON）：
  - `page_no`（int，必填）：页码，正整数（`>= 1`）。
  - `page_size`（int，必填）：每页数量，正整数（`1`–`100`）。
  - `host_id`（string，可选）：精确匹配 `host_id`。
  - `host_name`（string，可选）：精确匹配 `host_name`。
  - `bmc_ip`（string，可选）：精确匹配 `bmc_ip`。
- **响应**：
  - `200`：`data` 包含 `host_infos`（array）、`total_count`（int）、`total_page`（int）。其中 `host_infos` 每项包含以下字段：
    - `host_id`（string）
    - `installation_round`（string | null）：当前或最近一次装机轮次 UUID。
    - `cleanup`（object）：
      - `state`（string）：`"none"` / `"pending"` / `"done"`。
      - `failures`（int）：连续清理失败次数。
      - `next_attempt_at`（string | null）：下次重试的 ISO-8601 本地时间字符串。
      - `last_error`（string | null）：最近一次清理失败摘要（已剥离远端凭证等敏感信息）。
    - `host_name`（string）
    - `bmc_ip`（string）
    - `bmc_user_name`（string）
    - `bmc_passwd`（string）：数据库存储的加密密文。
    - `host_ip`（string | null）
    - `created_time`（string | null）：ISO-8601 时间字符串。
    - `status`（int）：`0`–`4`。
    - `host_mac`（string）
  - `400`：分页参数非法或查询失败。

```bash
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"page_no":1,"page_size":10}' \
  http://127.0.0.1:8888/cobbler/queryHosts
```

```json
{
  "code": 200,
  "msg": "Query host successfully.",
  "data": {
    "host_infos": [
      {
        "host_id": "d201d50c-f9cc-40d6-912c-1e62d8ffbcb8",
        "installation_round": "38642f8d-e9c5-4357-b241-89e73ce1e510",
        "cleanup": {
          "state": "done",
          "failures": 0,
          "next_attempt_at": null,
          "last_error": null
        },
        "host_name": "node-01",
        "bmc_ip": "10.10.10.1",
        "bmc_user_name": "admin",
        "bmc_passwd": "gAAAAAB...",
        "host_ip": "10.10.192.210",
        "created_time": "2026-10-20T12:00:00",
        "status": 1,
        "host_mac": "52:54:00:ab:cd:10"
      }
    ],
    "total_count": 1,
    "total_page": 1
  }
}
```

#### 16. 下载主机导入 CSV 模板：`GET /cobbler/getHostTemplateFile`

- **请求参数**：无。
- **响应**：HTTP `200`，`Content-Type: application/octet-stream`，`Content-Disposition: attachment; filename=template.csv`，首行表头为：
  ```text
  host_name,host_mac,bmc_ip,bmc_user_name,bmc_passwd
  ```

---

### 五、自动装机、回调与日志

#### 17. 发起自动装机：`POST /cobbler/autoInstall`

为指定裸机列表准备 Kickstart 模板、Cobbler system 配置及 PXE 引导，并逐台通过 `ipmitool` 设置下次 PXE 启动后重启机器。

- **请求体**（JSON）：
  - `host_list`（array\<object\>，必填）：1–100 项，每项至少包含 `bmc_ip`（IPv4 字符串），例如 `[{"bmc_ip": "10.10.10.1"}]`。
  - `ks_name`（string，必填）：Kickstart 模板名（不含 `.ks`）。
  - `iso_name`（string，必填）：镜像基础名（不含架构后缀与 `.iso`）。
  - `arch`（string，必填）：镜像架构（默认 `x86_64` 或 `aarch64`）。
  - `script_name`（string，可选）：装机后追加执行的自定义脚本名（不含 `.sh`）。省略或 `""` 时不追加。
  - `install_rpm`（string，可选）：需要额外安装的 RPM 包名，多个包以逗号 `,` 分隔（总长度 `<= 256` 字符，最多 `10` 个包，包名匹配 `[A-Za-z0-9][A-Za-z0-9._+-]*`）。非空时服务端会先逐一在本机执行 `yum search` 检查包是否存在。
  - `gateway`（string，可选）：安装后静态网络配置的默认网关 IPv4 地址，用于覆盖 `[host] gateway` 配置；传 `""` 可显式清空配置的静态网关（改为沿用装机网卡默认路由或原有配置）。若传入非空网关，必须位于 `os_start_ip` 与 `[host] subnet_mask` 定义的网段内、不能是网段网络地址或广播地址，且不得落在 `os_start_ip`–`os_end_ip` 分配池内。
- **部分成功语义与响应说明**：
  - **请求级失败（返回 HTTP `400`）**：参数格式错误、Kickstart/脚本/镜像（含 Cobbler profile）不存在、`install_rpm` 校验或 `yum search` 失败、网关配置无效，或修改本地 PXE 默认配置失败。
  - **逐主机处理结果（通常返回 HTTP `200`）**：进入主机循环后，单台主机失败（如数据库无该 `bmc_ip`、IP 池耗尽、BMC 不通、主机仍在装机中或清理未 `done`、Cobbler system 保存/DHCP 同步失败、IPMI 重启失败）**不会**中断同批其他主机；失败原因写入该主机对象的 `result: "failed"` 和 `reason`，整体仍返回 HTTP `200` 与 `data` 结果数组（即使所有主机都因各自前置校验失败而跳过，亦返回 `200`）。
  - **结果含义**：单台返回 `result: "succeed"` 并附带 `installation_round`（UUID）仅表示已成功下发 PXE 重启指令，不代表操作系统已安装完成。

```bash
curl -s -X POST -H "Content-Type: application/json" \
  -d '{
    "host_list": [{"bmc_ip": "10.10.10.1"}],
    "ks_name": "oe2403-default",
    "iso_name": "openEuler-24.03-LTS",
    "arch": "x86_64",
    "script_name": "post_init",
    "install_rpm": "vim,jq",
    "gateway": "10.10.192.1"
  }' \
  http://127.0.0.1:8888/cobbler/autoInstall
```

```json
{
  "code": 200,
  "msg": "The os installation command have been successfully announced.",
  "data": [
    {
      "bmc_ip": "10.10.10.1",
      "result": "succeed",
      "reason": "",
      "installation_round": "38642f8d-e9c5-4357-b241-89e73ce1e510",
      "bmc_user_name": "admin",
      "bmc_passwd": "gAAAAAB...",
      "host_name": "node-01",
      "host_mac": "52:54:00:ab:cd:10"
    }
  ]
}
```

#### 18. 装机完成/失败回调：`POST /cobbler/notify`

由目标主机安装后脚本（`/opt/aops/script/after_os_installed.sh`）在 Kickstart `%post` 阶段调用，通知本服务该安装轮次的最终结果。

- **请求体**（JSON）：
  - `installation_round`（string，必填）：当前安装轮次 UUID（须为标准小写连字符格式），安装脚本从 `/proc/cmdline` 的 `aops_installation_round` 读取。
  - `bmc_ip`（string，可选）：目标主机 BMC IPv4 地址；若省略或为 `null`，服务端按 `installation_round` 定位主机（并校验请求来源 IP 与预分配 IP 是否一致，不一致仅记告警日志）。
  - `result`（string，可选）：`"success"` 或 `"failed"`，默认为 `"success"`。
- **状态流转与清理行为**：
  - 服务端取客户端来源地址 `REMOTE_ADDR` 作为最终 `host_ip`。
  - 当 `result="success"` 时，主机 `status` 置为 `1`（已安装）并更新 `host_ip`；当 `result="failed"` 时，仅在当前 `status == 3`（装机中）时置为 `4`（安装失败），不会覆盖已确认的完成结果。
  - 结果与待清理任务（`installation_cleanup`）在同一数据库事务中提交；返回 `200` 仅表示结果已持久化，Cobbler system 删除与 DHCP 同步由后台定时任务异步完成。
- **响应**：
  - `200`：`{"code": 200, "msg": "Notify aops-cobbler to update host info successfully."}`
  - `400`：`bmc_ip` 非法、`installation_round` 缺失或格式错误、`result` 无效，或主机不存在/轮次不匹配。
  - `500`：`{"code": 500, "msg": "安装结果保存失败，请重试"}`

> 轮次隔离、并发加锁与后台清理重试细节见 [安装收尾与升级](./installation-cleanup.md)。

```bash
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"installation_round":"38642f8d-e9c5-4357-b241-89e73ce1e510","bmc_ip":"10.10.10.1","result":"success"}' \
  http://127.0.0.1:8888/cobbler/notify
```

#### 19. 下载装机日志：`POST /cobbler/downloadLogFile`

从 `[host] os_install_log_dir` 读取指定主机的安装日志，在内存中打包为 `.zip` 后下载。

- **请求体**（JSON）：
  - `log_file_name`（string，必填）：日志基础文件名（**不含** `.log` 后缀），命名格式为 `<host_name>-<host_id>`。禁止包含 `/`、`\`、`..` 等路径穿越字符。
- **响应**：
  - `200`：二进制流（`application/octet-stream`），响应头 `Content-Disposition: attachment; filename=<log_file_name>.zip`，压缩包内包含 `<log_file_name>.log`。
  - `400`：文件名为空、包含非法路径字符或日志文件不存在（`The os install log file not exists.`）。

```bash
curl --fail-with-body -X POST -H "Content-Type: application/json" \
  -d '{"log_file_name":"node-01-d201d50c-f9cc-40d6-912c-1e62d8ffbcb8"}' \
  -o node-01.zip \
  http://127.0.0.1:8888/cobbler/downloadLogFile
```
