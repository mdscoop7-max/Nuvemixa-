import pytest

import nv_source_guard


@pytest.fixture(autouse=True)
def fresh_source_guard():
    nv_source_guard.reset()
    yield
    nv_source_guard.reset()
