"""Deterministic scene without camera hardware."""

from datetime import UTC, datetime
from uuid import uuid4

from rosa_turbopi.robot.camera.source import Frame


class MockCamera:
    def capture(self) -> Frame:
        scene = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540">
        <rect width="960" height="540" fill="#172b36"/>
        <path d="M0 310H960V540H0Z" fill="#29424b"/>
        <path d="M480 310L80 540M480 310L880 540M0 400H960M0 480H960" stroke="#48616a" fill="none"/>
        <rect x="340" y="240" width="110" height="130" rx="8" fill="#d76952"/>
        <circle cx="650" cy="340" r="45" fill="#e3ba69"/>
        <text x="32" y="48" fill="#b7d8d3" font-family="sans-serif" font-size="22">MOCK CAMERA / TURBOPI</text>
        </svg>"""
        return Frame(str(uuid4()), datetime.now(UTC), scene, "image/svg+xml")
