# docker-compose-snippets

本地常用服务的 Docker Compose 片段。仓库里的 `image:` 使用官方镜像名，便于提交；需要走镜像站时，用脚本按 JSON 映射替换。

## 目录

| 路径 | 说明 |
|---|---|
| [impala-in-docker](impala-in-docker/) | Apache Impala + Kudu 快速环境，用法见该目录 [README](impala-in-docker/README.md) |
| [mysql-in-dokcer](mysql-in-dokcer/) | MySQL 5.7.23（演示账号，勿用于生产） |
| [image-mirrors.json](image-mirrors.json) | 官方镜像 → 镜像站地址 |
| [scripts/replace_compose_images.py](scripts/replace_compose_images.py) | 在官方名与镜像站之间切换 |

## 镜像替换

`image-mirrors.json` 格式为 JSON 对象，键是官方镜像，值是镜像站地址：

```json
{
  "mysql:5.7.23": "docker.m.daocloud.io/library/mysql:5.7.23"
}
```

当前示例使用 DaoCloud 公共前缀。若你的 registry 不同，只改这个文件。

在仓库根目录执行：

```bash
# 换成镜像站，并在 image 上一行写入「# 原始链接」
python3 scripts/replace_compose_images.py apply

# 还原官方名，并删除该注释（提交前执行）
python3 scripts/replace_compose_images.py restore
```

可选参数：`--config`（默认仓库根目录的 `image-mirrors.json`）、`--root`（默认当前工作目录）。

脚本会递归查找 `docker-compose.yml` / `docker-compose.yaml` / `compose.yml` / `compose.yaml`，并跳过 `.git`、`.venv`、`node_modules`、`__pycache__`。

**apply 之后：**

```yaml
    # mysql:5.7.23
    image: docker.m.daocloud.io/library/mysql:5.7.23
```

**restore 之后（提交到 git 的形态）：**

```yaml
    image: mysql:5.7.23
```

## 新增 snippet

1. 在子目录中放 `docker-compose.yml`，`image:` 写官方镜像名。
2. 把新镜像补进 `image-mirrors.json`。
3. 本地拉镜像前先 `apply`，提交前再 `restore`。
