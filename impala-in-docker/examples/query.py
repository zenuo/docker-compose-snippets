"""Minimal Impala HS2 client example.

Connects to the local Docker Impala coordinator (port 21050, no auth).
"""

from impala.dbapi import connect

IMPALA_HOST = "localhost"
IMPALA_PORT = 21050
IMPALA_DATABASE = "default"


def main() -> None:
    conn = connect(
        host=IMPALA_HOST,
        port=IMPALA_PORT,
        database=IMPALA_DATABASE,
        auth_mechanism="NOSASL",
        user="",
        password="",
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT version()")
            print("Impala version:", cursor.fetchone()[0])

            cursor.execute("SHOW DATABASES")
            print("Databases:")
            for row in cursor.fetchall():
                print(" ", row[0])
    finally:
        conn.close()


if __name__ == "__main__":
    main()
