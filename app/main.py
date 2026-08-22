"""FastAPI application entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents import (
    CompetitionAgent,
    DocumentsAgent,
    GeographyAgent,
    GovernmentDataAgent,
    WeatherAgent,
)
from app.api.errors import register_exception_handlers
from app.api.routes import api_router
from app.config import get_settings
from app.core.cache import InMemoryCache
from app.core.http import AsyncHttpClient
from app.core.logging import get_logger, setup_logging
from app.core.monitoring import init_error_monitoring
from app.db.session import create_engine, create_schema, create_session_factory
from app.db.store import InvestigationStore, SqlAlchemyEvidenceRepository
from app.evidence import EvidenceService, EvidenceValidator
from app.graph.deps import ResearchOrchestrationDeps
from app.graph.graph import build_investigation_graph
from app.rag.corpus import public_sample_corpus
from app.rag.embeddings import HashingEmbeddingProvider
from app.rag.ingest import DocumentIngestor
from app.rag.retriever import DocumentRetriever
from app.rag.store import PgVectorStore
from app.services.external import (
    DataGovInProvider,
    FallbackGeocoder,
    NominatimClient,
    OpenMeteoClient,
    OverpassBusinessSearchProvider,
)
from app.services.investigation import InvestigationService
from app.services.investigation_app import InvestigationAppService
from app.services.progress import InvestigationProgressSink

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan hooks for startup and shutdown."""
    settings = get_settings()
    setup_logging(settings.log_level)
    init_error_monitoring(dsn=settings.sentry_dsn, environment=settings.app_env)
    logger.info(
        "Starting %s (env=%s)",
        settings.app_name,
        settings.app_env,
    )

    engine = create_engine(settings.database_url)
    await create_schema(engine)
    session_factory = create_session_factory(engine)
    store = InvestigationStore(session_factory)
    evidence_repository = SqlAlchemyEvidenceRepository(session_factory)

    http_client = AsyncHttpClient(timeout=settings.http_timeout_seconds)
    cache = InMemoryCache(default_ttl_seconds=settings.cache_ttl_seconds)
    open_meteo = OpenMeteoClient(
        http_client,
        forecast_base_url=settings.open_meteo_base_url,
        archive_base_url=settings.open_meteo_archive_base_url,
        geocoding_base_url=settings.open_meteo_geocoding_base_url,
        cache=cache,
        cache_ttl_seconds=settings.cache_ttl_seconds,
    )
    nominatim = NominatimClient(
        http_client,
        base_url=settings.nominatim_base_url,
        user_agent=settings.nominatim_user_agent,
        cache=cache,
        cache_ttl_seconds=settings.nominatim_cache_ttl_seconds,
        min_request_interval_seconds=settings.nominatim_min_request_interval_seconds,
    )
    geocoder = FallbackGeocoder(nominatim, open_meteo)
    business_search = OverpassBusinessSearchProvider(
        http_client,
        base_url=settings.overpass_base_url,
    )
    government_data = DataGovInProvider(
        http_client,
        base_url=settings.data_gov_in_base_url,
        api_key=settings.data_gov_in_api_key or None,
    )

    app.state.db_engine = engine
    app.state.db_session_factory = session_factory
    app.state.investigation_store = store
    app.state.http_client = http_client
    app.state.cache = cache
    app.state.open_meteo = open_meteo
    app.state.nominatim = geocoder
    app.state.business_search = business_search
    app.state.government_data = government_data
    app.state.weather_agent = WeatherAgent(open_meteo)
    app.state.geography_agent = GeographyAgent(geocoder)
    app.state.competition_agent = CompetitionAgent(business_search)
    app.state.government_data_agent = GovernmentDataAgent(government_data)

    embeddings = HashingEmbeddingProvider(dim=settings.rag_embedding_dim)
    rag_store = PgVectorStore(session_factory)
    retriever = DocumentRetriever(
        rag_store,
        embeddings,
        top_k=settings.rag_top_k,
    )
    if settings.rag_seed_on_startup:
        ingestor = DocumentIngestor(
            rag_store,
            embeddings,
            chunk_size=settings.rag_chunk_size,
            overlap=settings.rag_chunk_overlap,
        )
        if await rag_store.document_count() == 0:
            await ingestor.ingest_many(public_sample_corpus())
    app.state.rag_store = rag_store
    app.state.documents_agent = DocumentsAgent(retriever)

    evidence_validator = EvidenceValidator(
        min_confidence=settings.evidence_min_confidence,
        stale_after_hours=settings.evidence_stale_after_hours,
        treat_low_confidence_as_error=settings.evidence_low_confidence_as_error,
    )
    app.state.evidence_repository = evidence_repository
    app.state.evidence_validator = evidence_validator
    app.state.evidence_service = EvidenceService(
        evidence_repository,
        evidence_validator,
    )

    orchestration_deps = ResearchOrchestrationDeps(
        weather_agent=app.state.weather_agent,
        geography_agent=app.state.geography_agent,
        competition_agent=app.state.competition_agent,
        government_data_agent=app.state.government_data_agent,
        documents_agent=app.state.documents_agent,
        evidence_service=app.state.evidence_service,
        nominatim=geocoder,
        progress_sink=InvestigationProgressSink(store),
    )
    investigation_graph = build_investigation_graph(deps=orchestration_deps)
    investigation_service = InvestigationService(graph=investigation_graph)
    app.state.orchestration_deps = orchestration_deps
    app.state.investigation_graph = investigation_graph
    app.state.investigation_service = investigation_service
    app.state.investigation_app_service = InvestigationAppService(
        store=store,
        runner=investigation_service,
    )

    try:
        yield
    finally:
        await http_client.aclose()
        await engine.dispose()
        logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    settings = get_settings()
    setup_logging(settings.log_level)
    production = settings.app_env.lower() == "production"

    application = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
        docs_url=None if production else "/docs",
        redoc_url=None if production else "/redoc",
        openapi_url=None if production else "/openapi.json",
    )
    origins = [
        origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()
    ]
    if origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Content-Type", "Accept"],
        )
    register_exception_handlers(application)
    application.include_router(api_router)
    return application


app = create_app()
