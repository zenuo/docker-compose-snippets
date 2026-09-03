## how to run

```
docker network create impala
docker compose up -d
docker compose down
```

### Impala ports:
- 21000: Impala Shell
- 21050: JDBC/ODBC
- 25000: Impala Web UI (http://localhost:25000)

## reference

- https://github.com/ibis-project/ibis/blob/main/compose.yaml
- https://github.com/big-data-europe/docker-hive-metastore-postgresql
- https://github.com/big-data-europe/docker-hive
- https://impala.apache.org/docs/build/html/index.html
- https://github.com/apache/impala/blob/2975f10701501ed52304845ff6ac9c7ba35b63c9/docker/quickstart_conf/hive-site.xml
- https://github.com/apache/impala/blob/master/docker/quickstart.yml

### query with Poetry (Python)

本地 Poetry 虚拟环境（`.venv`）已安装 `impyla`，可通过 HS2 端口 `21050` 执行 SQL（无认证）。

```bash
poetry install
poetry run python examples/query.py
```

或在代码中执行任意 SQL：

```python
from impala.dbapi import connect

conn = connect(
    host="localhost",
    port=21050,
    database="default",
    auth_mechanism="NOSASL",
    user="",
    password="",
)
cursor = conn.cursor()
cursor.execute("SHOW DATABASES")
for row in cursor.fetchall():
    print(row[0])
cursor.close()
conn.close()
```

### access by spark

```java
String sql = "select * from table ";
Map<String, String> options = new HashMap<>();
options.put("url", "jdbc:impala://localhost:21050/default;authMech=0;SSL=0");
options.put("driver", "com.cloudera.impala.jdbc41.Driver");
options.put("user", "");
options.put("password", "");
options.put("dbtable", sql);
Dataset<Row> ds = sparkSession.read().format("jdbc").options(options).load();
```

### import data

```
sudo docker run --rm --network impala-network \
  -v /path/to/data.sql:/tmp/export.sql:ro \
  apache/impala:4.5.0-impala_quickstart_client \
  impala-shell -i impala:21050 -f /tmp/export.sql
```
