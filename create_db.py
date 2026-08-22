# We use the sync psycopg to create databases since we just need a simple script
import psycopg

from app.core.config import settings


def create_database(url: str):
    # Parse the URL roughly
    # postgresql+asyncpg://user:password@localhost/itvaya
    # postgresql+asyncpg://user:password@localhost/itvaya_test
    url = url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgresql+psycopg://", "postgresql://"
    )

    parts = url.rsplit("/", 1)
    if len(parts) != 2:
        return

    base_url = parts[0] + "/postgres"
    db_name = parts[1]

    try:
        with psycopg.connect(base_url, autocommit=True) as conn:
            # Check if exists
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
                exists = cur.fetchone()
                if not exists:
                    cur.execute(f"CREATE DATABASE {db_name}")
                    print(f"Database {db_name} created.")
                else:
                    print(f"Database {db_name} already exists.")
    except Exception as e:  # noqa: BLE001
        print(f"Could not connect to base postgres to create DB {db_name}: {e}")


if __name__ == "__main__":
    create_database(settings.DATABASE_URL)
    create_database(settings.TEST_DATABASE_URL)
