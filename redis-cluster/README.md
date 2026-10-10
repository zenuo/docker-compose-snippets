# Redis Cluster（Docker Compose）

使用 Docker Compose 部署 Redis 7.4 三主节点集群，并通过 Redis ACL 配置用户名和密码。集群初始化由 `redis-cluster-init` 服务自动执行。

> 当前方案是 **3 个主节点、0 个副本节点**。它可以分片存储数据，但没有从节点用于主从故障转移。生产环境请评估是否需要增加副本节点、网络隔离、TLS 和更严格的 ACL 权限。

## 目录结构

```text
redis-cluster/
├── docker-compose.yml
├── .env
└── README.md
```

## 环境要求

- Docker Engine
- Docker Compose v2（使用 `docker compose` 命令）
- 宿主机的 `7001-7003`、`17001-17003` 端口未被占用

## 1. 配置用户名和密码

在 `docker-compose.yml` 同一目录创建 `.env` 文件：

```dotenv
REDIS_USERNAME=redisuser
REDIS_PASSWORD=Replace_With_A_Strong_Unique_Password
```

请将示例密码替换为强随机密码。限制文件权限，并避免将凭据提交到代码仓库：

```bash
chmod 600 .env
```

在 `.gitignore` 中加入：

```gitignore
.env
```

Compose 文件中的 Redis 节点会使用这些变量生成 ACL 配置：禁用默认用户，并允许指定用户通过密码认证。当前示例 ACL 使用 `+@all`，拥有全部 Redis 命令权限；如用于生产环境，建议按业务需要收紧权限。

## 2. 启动集群

在 `docker-compose.yml` 所在目录执行：

```bash
docker compose up -d
```

Compose 会依次启动三个 Redis 节点，等待健康检查通过，再由 `redis-cluster-init` 服务执行集群创建。初始化服务成功退出是正常现象。

查看容器状态：

```bash
docker compose ps -a
```

查看初始化日志：

```bash
docker compose logs redis-cluster-init
```

查看 Redis 节点日志：

```bash
docker compose logs redis-node-1 redis-node-2 redis-node-3
```

## 3. 检查集群状态

使用容器内的环境变量进行认证：

```bash
docker exec redis-node-1 sh -c \
  'REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli --user "$REDIS_USERNAME" cluster info'
```

正常情况下应包含类似结果：

```text
cluster_state:ok
cluster_slots_assigned:16384
cluster_slots_ok:16384
```

查看节点信息：

```bash
docker exec redis-node-1 sh -c \
  'REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli --user "$REDIS_USERNAME" cluster nodes'
```

## 4. 连接与读写测试

### 从宿主机连接

确保本机已安装 `redis-cli`：

```bash
redis-cli -c -h 127.0.0.1 -p 7001 --user redisuser --askpass
```

按提示输入 `.env` 中设置的密码。连接后执行：

```redis
CLUSTER INFO
SET test hello
GET test
```

`-c` 表示启用集群重定向处理。

也可以通过环境变量避免把密码写在命令行参数中：

```bash
export REDISCLI_AUTH='Replace_With_A_Strong_Unique_Password'
redis-cli -c -h 127.0.0.1 -p 7001 --user redisuser
unset REDISCLI_AUTH
```

请将示例密码替换为实际密码。避免在共享终端、脚本日志或进程参数中泄露凭据。

### 应用连接地址

| 客户端所在位置 | 节点地址 |
|---|---|
| 同一个 Compose 网络内 | `redis-node-1:6379` |
| 宿主机 | `127.0.0.1:7001`、`127.0.0.1:7002`、`127.0.0.1:7003` |
| 其他服务器 | 宿主机可达的地址及对应映射端口 |

应用连接 Redis Cluster 时，客户端会根据集群返回的节点地址访问其他节点。**仅映射端口并不保证远程客户端能正常使用集群**：如果客户端不在 Compose 网络内，需要进一步配置 `cluster-announce-ip`、`cluster-announce-port` 和 `cluster-announce-bus-port`，确保返回的地址可被客户端访问。不要直接把 Redis 暴露到公网。

## 5. 端口说明

| 宿主机端口 | 容器端口 | 用途 |
|---|---:|---|
| `7001` | `6379` | 节点 1 客户端连接 |
| `7002` | `6379` | 节点 2 客户端连接 |
| `7003` | `6379` | 节点 3 客户端连接 |
| `17001` | `16379` | 节点 1 Cluster Bus |
| `17002` | `16379` | 节点 2 Cluster Bus |
| `17003` | `16379` | 节点 3 Cluster Bus |

Redis Cluster Bus 用于节点间通信。若节点分布在不同主机，需要单独规划并开放对应的总线端口；当前 Compose 网络中的节点使用容器内部网络通信。

## 6. 数据持久化

每个节点使用独立的 Docker named volume：

- `redis-node-1-data`
- `redis-node-2-data`
- `redis-node-3-data`

配置启用了 AOF 持久化。普通重启或执行 `docker compose down` 不会删除这些命名卷。

查看卷：

```bash
docker volume ls
```

> **警告：** `docker compose down -v` 会删除 Compose 管理的命名卷，导致持久化数据被删除。执行前请确认已经备份且确实需要清理数据。

## 7. 常用运维命令

启动：

```bash
docker compose up -d
```

停止并删除容器（保留命名卷）：

```bash
docker compose down
```

查看状态：

```bash
docker compose ps -a
```

查看日志：

```bash
docker compose logs -f redis-node-1
```

重启某个节点：

```bash
docker compose restart redis-node-1
```

## 8. 密码修改与已有集群

修改 `.env` 后，已有节点中的 ACL 配置不会因为环境变量变化而自动更新。需要规划 ACL 更新，并确保三个节点的凭据一致。

当前示例把 ACL 文件生成在容器内的 `/tmp/users.acl`。容器重建后会重新生成，因此适用于初始部署示例，但不适合作为完善的生产凭据管理方案。生产环境建议使用受控的 ACL 文件或 Secret 管理方式，并在变更前备份数据与配置。

如果此前已经启动过无密码集群并且其中存在数据，不要为了启用密码而直接删除数据卷或重新创建集群。应先备份，再执行认证迁移。

## 9. 安全建议

- 不要将 Redis 端口暴露到公网。
- 使用强随机密码，并保护 `.env` 文件。
- 生产环境建议限制 ACL 权限，避免默认使用 `+@all`。
- 根据部署环境配置防火墙、网络隔离和 TLS。
- 需要主节点故障转移时，增加副本节点；三主零副本不提供主从自动故障转移。
