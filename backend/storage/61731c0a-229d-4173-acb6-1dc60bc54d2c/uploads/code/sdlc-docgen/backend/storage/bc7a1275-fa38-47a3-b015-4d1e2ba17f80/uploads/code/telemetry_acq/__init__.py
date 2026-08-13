"""Telemetry acquisition subsystem (sample codebase for SDLC DocGen demo)."""

from .acquisition import AcquisitionEngine, Sample
from .processing import HealthMonitor
from .server import app

__all__ = ["AcquisitionEngine", "Sample", "HealthMonitor", "app"]
