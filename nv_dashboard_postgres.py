"""PostgreSQL connection for dashboard data, independent of authentication."""
import os
from contextlib import contextmanager


def configured():
    return bool(os.environ.get("NUVEMIXA_DASHBOARD_DATABASE_URL", "").strip())


@contextmanager
def connect():
    import certifi
    import psycopg

    with psycopg.connect(os.environ["NUVEMIXA_DASHBOARD_DATABASE_URL"],
                         sslmode="verify-full", sslrootcert=certifi.where(),
                         connect_timeout=4, prepare_threshold=None) as db:
        yield db
