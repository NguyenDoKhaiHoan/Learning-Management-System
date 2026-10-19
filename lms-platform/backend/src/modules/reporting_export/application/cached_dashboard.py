"""Cache aggregates only after live authentication/authorization dependencies."""

from src.core.database.sql import SqlRepository
from src.modules.reporting_export.application.service import DashboardReports


async def dashboard(request, connection, actor, *, admin=False):
    # Discard the authentication dependency's REPEATABLE READ snapshot. Version
    # and aggregate data must then be read from the SAME new consistent snapshot.
    await connection.rollback()
    version = await SqlRepository(connection).fetch_one(
        "SELECT version FROM cache_versions WHERE id=1"
    )
    key = ("overview" if admin else "instructor", actor.id,
           tuple(sorted(actor.roles)), version["version"])

    async def load():
        service = DashboardReports(connection)
        if admin:
            return await service.overview(actor)
        return {"courses": await service.courses(actor)}

    return await request.app.state.dashboard_cache.get_or_load(key, load)
