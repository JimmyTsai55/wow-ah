import sqlite3
import pytest


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary SQLite database path."""
    return str(tmp_path / "test.db")
