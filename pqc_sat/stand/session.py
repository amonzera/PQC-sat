"""Append-only presentation session logging with provenance."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import uuid

from pqc_sat.stand.model import StandConfig
from pqc_sat.stand.settings import ROOT


class StandSessionLogger:
    def __init__(
        self,
        log_dir: str | Path,
        *,
        mode: str,
        config: StandConfig,
        fixture_source: str = "",
        flow: str = "investigation",
    ):
        now = datetime.now(timezone.utc)
        day_dir = Path(log_dir) / now.strftime("%Y%m%d")
        day_dir.mkdir(parents=True, exist_ok=True)
        self.path = day_dir / f"{now.strftime('%Y%m%dT%H%M%SZ')}_stand_{mode}_{uuid.uuid4().hex[:8]}.jsonl"
        self._handle = self.path.open("a", encoding="utf-8")
        self.session_id = uuid.uuid4().hex
        if flow != "investigation":
            raise ValueError("somente o jogo por etapas pode criar novos logs")
        self.schema_version = "pqc-sat-stand-log-v2"
        try:
            revision = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
                timeout=2,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            revision = "UNKNOWN"
        self.write(
            "session_start",
            mode=mode,
            flow=flow,
            revision=revision,
            payload=config.payload,
            payload_hex=config.payload_hex,
            missions=[
                {"id": mission.mission_id, "payload": mission.payload, "payload_hex": mission.payload_hex}
                for mission in config.missions
            ],
            fixture_source=fixture_source or None,
            protocol="STAGED_V1",
            kex_experiment="KEX_FAIR_V1",
            public_interaction_timeout_enabled=config.public_interaction_timeout_enabled,
            public_auto_reset_enabled=config.public_auto_reset_enabled,
            key_modes=["ECDH", "MLKEM"],
            guards=["NONE", "CRC32"],
        )

    def write(self, event: str, **fields: object) -> None:
        record = {
            "schema_version": self.schema_version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self.session_id,
            "event": event,
            **fields,
        }
        self._handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        self._handle.flush()

    def close(self) -> None:
        if self._handle.closed:
            return
        self.write("session_end")
        self._handle.close()

__all__ = ("StandSessionLogger",)
