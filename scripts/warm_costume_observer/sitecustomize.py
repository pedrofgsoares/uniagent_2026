"""Observação externa do SDK, ativada apenas por UNIAGENT_RESPONSE_METADATA."""
from datetime import datetime, timezone
from functools import wraps
import json
import os
from pathlib import Path
import time


def observe(create, path: Path):
    @wraps(create)
    def wrapped(*args, **kwargs):
        started = time.monotonic()
        row = {"started_at": datetime.now(timezone.utc).isoformat(),
               "requested_model": kwargs.get("model"), "pid": os.getpid()}
        try:
            response = create(*args, **kwargs)
            extra = getattr(response, "model_extra", None) or {}
            row.update(response_model=getattr(response, "model", None),
                       provider=extra.get("provider"),
                       system_fingerprint=getattr(response, "system_fingerprint", None),
                       service_tier=getattr(response, "service_tier", None),
                       request_id=getattr(response, "_request_id", None),
                       response_id=getattr(response, "id", None))
            row["status"] = "ok"
            return response
        except Exception as error:
            row.update(status="error", error_type=type(error).__name__)
            raise
        finally:
            row.update(finished_at=datetime.now(timezone.utc).isoformat(),
                       seconds=round(time.monotonic() - started, 4))
            try:
                with path.open("a") as stream:
                    stream.write(json.dumps(row, default=str) + "\n")
            except OSError:
                # A observação nunca muda uma resposta ou exceção do solver.
                pass
    return wrapped


if os.environ.get("UNIAGENT_RESPONSE_METADATA"):
    from openai.resources.chat.completions import Completions
    Completions.create = observe(Completions.create, Path(os.environ["UNIAGENT_RESPONSE_METADATA"]))
