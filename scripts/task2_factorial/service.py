"""Persistent controller with explicit terminal status and separate heartbeat."""
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import traceback

from .diagnostics import campaign_counterfactual
from .results import evaluate
from .runner import docker_callback, execute
from .transport import atomic_json


def run(plan_path, campaign, datasets, indices, benchmark, control):
    plan = json.loads(Path(plan_path).read_text())
    campaign, control = Path(campaign), Path(control)
    control.mkdir(parents=True, exist_ok=True)
    status = {'status': 'running', 'stage': 'inference', 'plan_hash': plan['plan_hash'],
              'campaign': str(campaign), 'started_utc': datetime.now(timezone.utc).isoformat()}
    atomic_json(control / 'status.json', status)
    stop = threading.Event()
    def heartbeat():
        while not stop.is_set():
            atomic_json(control / 'heartbeat.json', {'utc': datetime.now(timezone.utc).isoformat(),
                                                    'stage': status['stage']})
            stop.wait(15)
    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    try:
        execute(plan, campaign, docker_callback(datasets, indices))
        status['stage'] = 'analysis'
        atomic_json(control / 'status.json', status)
        evaluate(plan, campaign, datasets)
        status['stage'] = 'counterfactual'
        atomic_json(control / 'status.json', status)
        campaign_counterfactual(plan, campaign, datasets, indices, benchmark)
        status.update(status='complete', stage='complete')
    except BaseException as error:
        status.update(status='failed', error_type=type(error).__name__)
        state = campaign / 'state.json'
        if state.exists():
            saved = json.loads(state.read_text())
            status.update(completed_blocks=saved['completed_blocks'],
                          active_cells=[k for k, v in saved['cells'].items() if v == 'started'],
                          spent=saved['spent'], fatal=saved.get('fatal'))
        raise
    finally:
        stop.set()
        thread.join(timeout=2)
        status['finished_utc'] = datetime.now(timezone.utc).isoformat()
        atomic_json(control / 'status.json', status)
