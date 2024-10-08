from pydantic import BaseModel, Field

from emirecords.config.base import BaseConfig


class ServerConfig(BaseModel):
    """Configuration for the server."""

    host: str = "0.0.0.0"
    """Host to run the server on."""

    port: int = Field(31000, ge=0, le=65535)
    """Port to run the server on."""

    trusted: str | list[str] | None = "*"
    """Trusted IP addresses."""


class EmishowsHTTPConfig(BaseModel):
    """Configuration for the HTTP API of the emishows service."""

    scheme: str = "http"
    """Scheme of the HTTP API."""

    host: str = "localhost"
    """Host of the HTTP API."""

    port: int | None = Field(35000, ge=1, le=65535)
    """Port of the HTTP API."""

    path: str | None = None
    """Path of the HTTP API."""

    @property
    def url(self) -> str:
        """URL of the HTTP API."""

        url = f"{self.scheme}://{self.host}"
        if self.port:
            url = f"{url}:{self.port}"
        if self.path:
            path = self.path if self.path.startswith("/") else f"/{self.path}"
            path = path.rstrip("/")
            url = f"{url}{path}"
        return url


class EmishowsConfig(BaseModel):
    """Configuration for the emishows service."""

    http: EmishowsHTTPConfig = EmishowsHTTPConfig()
    """Configuration for the HTTP API of the emishows service."""


class MediarecordsS3Config(BaseModel):
    """Configuration for the S3 API of the mediarecords database."""

    secure: bool = False
    """Whether to use a secure connection."""

    host: str = "localhost"
    """Host of the S3 API."""

    port: int | None = Field(30000, ge=1, le=65535)
    """Port of the S3 API."""

    user: str = "readwrite"
    """Username to authenticate with the S3 API."""

    password: str = "password"
    """Password to authenticate with the S3 API."""

    @property
    def bucket(self) -> str:
        """Bucket to store media in."""

        return "default"

    @property
    def endpoint(self) -> str:
        """Endpoint to connect to the S3 API."""

        if self.port is None:
            return self.host

        return f"{self.host}:{self.port}"


class MediarecordsConfig(BaseModel):
    """Configuration for the mediarecords database."""

    s3: MediarecordsS3Config = MediarecordsS3Config()
    """Configuration for the S3 API of the mediarecords database."""


class Config(BaseConfig):
    """Configuration for the application."""

    server: ServerConfig = ServerConfig()
    """Configuration for the server."""

    emishows: EmishowsConfig = EmishowsConfig()
    """Configuration for the emishows service."""

    mediarecords: MediarecordsConfig = MediarecordsConfig()
    """Configuration for the mediarecords database."""

    debug: bool = False
    """Enable debug mode."""
