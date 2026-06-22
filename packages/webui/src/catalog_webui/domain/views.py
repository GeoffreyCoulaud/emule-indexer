"""View-models PRÉCALCULÉS (spec webui W-D8) : les templates n'itèrent et n'interpolent
que ces champs — aucune logique côté template."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CoverageStatus:
    status: str  # "found" | "partial" | "none"
    best_tier: str | None  # "download" | "notify" | "catalog" | None
    file_count: int
