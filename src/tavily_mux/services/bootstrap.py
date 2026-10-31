from dataclasses import dataclass

from loguru import logger

from tavily_mux.common.config import Settings
from tavily_mux.common.security import SecretManager, generate_admin_secret, hash_admin_secret
from tavily_mux.integrations.tavily import TavilyClientManager
from tavily_mux.persistence.database import Database
from tavily_mux.persistence.initialize import initialize_database
from tavily_mux.persistence.models import AdminCredential, SystemSettings
from tavily_mux.runtime.registry import RuntimeRegistry
from tavily_mux.runtime.snapshot_loader import RuntimeSnapshotLoader
from tavily_mux.workers.event_writer import EventWriter
from tavily_mux.workers.retention import RetentionWorker
from tavily_mux.workers.usage_monitor import UsageMonitor


@dataclass(slots=True)
class ApplicationContext:
    settings: Settings
    database: Database
    secrets: SecretManager
    runtime: RuntimeRegistry
    clients: TavilyClientManager
    events: EventWriter
    usage: UsageMonitor
    retention: RetentionWorker
    ready: bool = False

    async def start(self) -> None:
        self.events.start()
        self.usage.start()
        self.retention.start()
        self.ready = True

    async def close(self) -> None:
        self.ready = False
        await self.usage.stop()
        await self.retention.stop()
        await self.events.stop()
        await self.clients.close()
        self.database.close()


def bootstrap_application(settings: Settings) -> ApplicationContext:
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    initialization = initialize_database(
        settings.database_url,
        auto_migrate=settings.AUTO_MIGRATE,
    )
    database = initialization.database
    try:
        secrets = SecretManager.load(
            settings.DATA_DIR,
            settings.MASTER_KEY,
            refuse_generation=initialization.schema_existed,
        )

        with database.session() as session:
            admin = session.get(AdminCredential, 1)
            if admin is None:
                admin_secret = settings.ADMIN_SECRET or generate_admin_secret()
                admin = AdminCredential(id=1, secret_hash=hash_admin_secret(admin_secret))
                session.add(admin)
                if not settings.ADMIN_SECRET:
                    logger.warning("Generated initial admin secret: {}", admin_secret)
            if session.get(SystemSettings, 1) is None:
                session.add(SystemSettings(id=1))
            session.commit()
    except Exception:
        database.close()
        raise

    events = EventWriter(database, queue_size=settings.EVENT_QUEUE_SIZE)
    runtime = RuntimeRegistry(
        RuntimeSnapshotLoader(database, secrets),
        secrets,
        global_max_concurrency=settings.GLOBAL_MAX_CONCURRENCY,
        affinity_sink=events.emit_affinity,
    )
    runtime.load()
    clients = TavilyClientManager(
        max_connections=settings.UPSTREAM_MAX_CONNECTIONS,
        max_keepalive_connections=settings.UPSTREAM_MAX_KEEPALIVE_CONNECTIONS,
    )
    usage = UsageMonitor(
        runtime,
        clients,
        events,
        concurrency=settings.USAGE_CHECK_CONCURRENCY,
    )
    retention = RetentionWorker(database)
    return ApplicationContext(
        settings=settings,
        database=database,
        secrets=secrets,
        runtime=runtime,
        clients=clients,
        events=events,
        usage=usage,
        retention=retention,
    )
