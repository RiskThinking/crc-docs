"""Optional CI sharding for independent live-test runners."""

import os

import pytest


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    shard = os.environ.get("CRC_DOCS_SHARD")
    if shard is None:
        return
    count = int(os.environ["CRC_DOCS_SHARDS"])
    index = int(shard)
    if count < 1 or not 0 <= index < count:
        raise pytest.UsageError(
            "CRC_DOCS_SHARD must be between 0 and CRC_DOCS_SHARDS - 1"
        )
    selected, deselected = [], []
    for position, item in enumerate(sorted(items, key=lambda item: item.nodeid)):
        (selected if position % count == index else deselected).append(item)
    items[:] = selected
    config.hook.pytest_deselected(items=deselected)
