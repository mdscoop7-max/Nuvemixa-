"""Central paths for persistent NUVEMIXA application data."""
import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def _is_within(path, root):
    try:
        Path(path).relative_to(root)
        return True
    except ValueError:
        return False


def _data_dir_required():
    return os.environ.get("NUVEMIXA_REQUIRE_DATA_DIR", "").strip().lower() in {
        "1", "true", "yes", "on"
    }


def _validate_host_path(path, description, is_directory):
    path = Path(path).expanduser()
    if not path.is_absolute():
        raise ValueError(f"{description} moet een absoluut pad zijn wanneer opslag verplicht is.")
    resolved = path.resolve()
    if resolved == BASE_DIR or _is_within(resolved, BASE_DIR):
        raise ValueError(f"{description} mag niet in de project-/webmap staan.")
    if is_directory:
        if not resolved.is_dir():
            raise FileNotFoundError(f"{description} bestaat niet als map: {resolved}")
        if not os.access(resolved, os.W_OK | os.X_OK):
            raise PermissionError(f"{description} is niet schrijfbaar: {resolved}")
    elif not resolved.parent.is_dir() or not os.access(resolved.parent, os.W_OK | os.X_OK):
        raise PermissionError(f"Map voor {description} ontbreekt of is niet schrijfbaar: {resolved.parent}")
    return path


def data_directory():
    raw = os.environ.get("NUVEMIXA_DATA_DIR", "").strip()
    if not raw:
        if _data_dir_required():
            raise RuntimeError("NUVEMIXA_DATA_DIR is verplicht voor deze deployment.")
        return BASE_DIR
    path = Path(raw).expanduser()
    if _data_dir_required():
        return _validate_host_path(path, "NUVEMIXA_DATA_DIR", True)
    return path if path.is_absolute() else BASE_DIR / path


def database_path(env_name, filename, legacy_env_name=None):
    for name in (env_name, legacy_env_name):
        if name:
            raw = os.environ.get(name, "").strip()
            if raw:
                path = Path(raw).expanduser()
                if _data_dir_required():
                    return _validate_host_path(path, name, False)
                return path
    return data_directory() / filename


def two_fa_directory():
    for name in ("NUVEMIXA_2FA_DIR", "2FA_DIR"):
        raw = os.environ.get(name, "").strip()
        if raw:
            path = Path(raw).expanduser()
            if _data_dir_required():
                return _validate_host_path(path, name, True)
            return path
    return data_directory()


CUSTOMER_DB = database_path("NUVEMIXA_CUSTOMER_DB", "nuvemixa_customers.sqlite3", "CUSTOMER_DB")
DASHBOARD_DB = database_path(
    "NUVEMIXA_DASHBOARD_DB", "nuvemixa_dashboard.sqlite3", "DASHBOARD_DB"
)
ADMIN_DB = database_path("NUVEMIXA_ADMIN_DB", "nuvemixa_admin.sqlite3", "ADMIN_DB")
TWO_FA_DIR = two_fa_directory()

if _data_dir_required():
    data_directory()
