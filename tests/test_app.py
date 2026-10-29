from collections.abc import AsyncIterator
from pathlib import Path

import httpx2
import pytest
from cryptography.fernet import Fernet

from tavily_mux.app import create_app
from tavily_mux.common.config import Settings


@pytest.fixture
async def client(tmp_path: Path) -> AsyncIterator[httpx2.AsyncClient]:
    settings = Settings(
        DATA_DIR=tmp_path,
        ADMIN_SECRET="test-admin-secret",
        MASTER_KEY=Fernet.generate_key().decode(),
    )
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as test_client:
            yield test_client


async def test_liveness(client: httpx2.AsyncClient) -> None:
    response = await client.get("/livez")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness(client: httpx2.AsyncClient) -> None:
    response = await client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


async def test_serves_built_web_application_with_spa_fallback(tmp_path: Path) -> None:
    web_root = tmp_path / "web"
    assets = web_root / "assets"
    assets.mkdir(parents=True)
    (web_root / "index.html").write_text("<main>control deck</main>")
    (assets / "app.js").write_text("console.log('ready')")
    settings = Settings(
        DATA_DIR=tmp_path / "data",
        WEB_ROOT=web_root,
        ADMIN_SECRET="test-admin-secret",
        MASTER_KEY=Fernet.generate_key().decode(),
    )
    app = create_app(settings)
    async with (
        app.router.lifespan_context(app),
        httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app),
            base_url="http://test",
        ) as test_client,
    ):
        page = await test_client.get("/pools/example")
        pool_index = await test_client.get("/pools")
        asset = await test_client.get("/assets/app.js")
        missing_api = await test_client.get("/api/v1/missing")

    assert page.text == "<main>control deck</main>"
    assert pool_index.text == "<main>control deck</main>"
    assert asset.text == "console.log('ready')"
    assert missing_api.status_code == 404
