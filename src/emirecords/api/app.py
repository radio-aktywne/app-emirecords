import logging
import warnings
from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from importlib import metadata

from litestar import Litestar, Router
from litestar.contrib.pydantic import PydanticPlugin
from litestar.openapi import OpenAPIConfig
from litestar.plugins import PluginProtocol
from urllib3.exceptions import InsecureRequestWarning

from emirecords.api.routes.router import router
from emirecords.config.models import Config
from emirecords.services.emishows.service import EmishowsService
from emirecords.services.mediarecords.service import MediarecordsService
from emirecords.state import State


class AppBuilder:
    """Builds the app.

    Args:
        config: Config object.
    """

    def __init__(self, config: Config) -> None:
        self._config = config

    def _get_route_handlers(self) -> list[Router]:
        return [router]

    def _get_debug(self) -> bool:
        return self._config.debug

    @asynccontextmanager
    async def _suppress_urllib_warnings_lifespan(
        self, app: Litestar
    ) -> AsyncGenerator[None]:
        with warnings.catch_warnings(
            action="ignore",
            category=InsecureRequestWarning,
        ):
            yield

    @asynccontextmanager
    async def _suppress_httpx_logging_lifespan(
        self, app: Litestar
    ) -> AsyncGenerator[None]:
        logger = logging.getLogger("httpx")
        disabled = logger.disabled
        logger.disabled = True

        try:
            yield
        finally:
            logger.disabled = disabled

    def _build_lifespan(
        self,
    ) -> list[Callable[[Litestar], AbstractAsyncContextManager]]:
        return [
            self._suppress_urllib_warnings_lifespan,
            self._suppress_httpx_logging_lifespan,
        ]

    def _build_openapi_config(self) -> OpenAPIConfig:
        return OpenAPIConfig(
            # Title of the app
            title="emirecords app",
            # Version of the app
            version=metadata.version("emirecords"),
            # Description of the app
            summary="Emission recordings 📼",
            # Use handler docstrings as operation descriptions
            use_handler_docstrings=True,
            # Endpoint to serve the OpenAPI docs from
            path="/schema",
        )

    def _build_pydantic_plugin(self) -> PydanticPlugin:
        return PydanticPlugin(
            # Use aliases for serialization
            prefer_alias=True,
            # Allow type coercion
            validate_strict=False,
        )

    def _build_plugins(self) -> list[PluginProtocol]:
        return [
            self._build_pydantic_plugin(),
        ]

    def _build_emishows(self) -> EmishowsService:
        return EmishowsService(
            config=self._config.emishows,
        )

    def _build_mediarecords(self) -> MediarecordsService:
        return MediarecordsService(
            config=self._config.mediarecords,
        )

    def _build_initial_state(self) -> State:
        config = self._config
        emishows = self._build_emishows()
        mediarecords = self._build_mediarecords()

        return State(
            {
                "config": config,
                "emishows": emishows,
                "mediarecords": mediarecords,
            }
        )

    def build(self) -> Litestar:
        return Litestar(
            route_handlers=self._get_route_handlers(),
            debug=self._get_debug(),
            lifespan=self._build_lifespan(),
            openapi_config=self._build_openapi_config(),
            plugins=self._build_plugins(),
            state=self._build_initial_state(),
        )
