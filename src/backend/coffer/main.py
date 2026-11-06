from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from coffer.accounts.api import redacted_validation_handler
from coffer.accounts.api import router as accounts_router
from coffer.agent.api import router as agent_router
from coffer.agent.investment.api import router as investment_router
from coffer.budget.api import router as budget_router
from coffer.core.config import Settings, get_settings
from coffer.core.origin import install_origin_policy
from coffer.imports.api import router as imports_router
from coffer.market.api import router as market_router
from coffer.portfolio.api import router as portfolio_router
from coffer.profile.api import router as profile_router
from coffer.transactions.api import router as transactions_router


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Coffer API")
    # Middleware order (outermost first): CORS (if enabled) -> Origin check -> routes.
    # CORS must be outermost so preflight OPTIONS never reaches the Origin check or auth.
    install_origin_policy(app, settings or get_settings())
    app.include_router(accounts_router)
    app.add_exception_handler(RequestValidationError, redacted_validation_handler)
    app.include_router(transactions_router)
    app.include_router(budget_router)
    app.include_router(imports_router)
    app.include_router(agent_router)
    app.include_router(profile_router)
    app.include_router(portfolio_router)
    app.include_router(market_router)
    app.include_router(investment_router)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
