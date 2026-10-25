from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, HttpUrl


class Target(BaseModel):
    """One URL to check, validated when it is created."""

    model_config = ConfigDict(frozen=True)
    url: HttpUrl


@dataclass(frozen=True)
class Result:
    """The outcome of checking one URL."""

    url: str
    ok: bool
    status: int | None
    ms: float
    error: str | None
