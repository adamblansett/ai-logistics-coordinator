from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
async def test_app(tmp_path: Path) -> AsyncIterator[FastAPI]:
    db_path = tmp_path / "logistics_test.db"
    settings = Settings(
        app_env="test",
        database_url=f"sqlite+aiosqlite:///{db_path.as_posix()}",
        llm_default_provider="mock",
        llm_fallback_providers="mock",
        auth_enabled=False,
        rate_limit_enabled=False,
        seed_demo_data=False,
    )
    application = create_app(settings)
    yield application
    await application.state.engine.dispose()


@pytest.fixture
async def client(test_app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
