"""Serial block executor. Started cells are never replayed."""
import fcntl
import json
from pathlib import Path
import subprocess
import time

from .plan import code_hash, validate_plan
from .transport import atomic_json


def admission(plan, state, block):
    """Reserve tail estimate of every remaining complete block before proceeding."""
    if state.get('fatal'):
        raise ValueError('Campaign has a fatal integrity/budget record')
    fraction = (3 - block) / 2
    estimate = plan['estimates']['tail']
    telemetry = plan['telemetry']
    probes = {'requests': telemetry['probe_requests'],
              'input_tokens': telemetry['probe_input_tokens'],
              'output_tokens': telemetry['probe_output_tokens'],
              'wall_seconds': telemetry['probe_seconds']}
    probes['money'] = (probes['input_tokens'] * plan['pricing']['input_per_million'] +
                       probes['output_tokens'] * plan['pricing']['output_per_million']) / 1e6
    for key, total in estimate.items():
        if key == 'money' and plan.get('monetary_policy') == 'metered-wallet':
            continue
        remaining = plan['quotas'][key] - (time.time() - state['started_epoch']
                    if key == 'wall_seconds' else state['spent'][key])
        # Construction has already been charged once. Generic probes belong
        # before the blocks, not half to each block or twice after preflight.
        block_cost = total - probes[key] - (telemetry['build_seconds'] if key == 'wall_seconds' else 0)
        reserve = max(0, block_cost) * fraction + (0 if state.get('preflight_complete') else probes[key])
        if remaining < reserve:
            raise ValueError('Cannot reserve all remaining blocks: ' + key)


def execute(plan, output, run_cell, *, stop_after_block=None):
    """run_cell is injected for simulation; real callback starts a new container."""
    validate_plan(plan, executable=True)
    if code_hash() != plan['source_hash']:
        raise ValueError('Controller source hash differs from frozen plan')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    # Held across all subprocesses; prevents concurrent campaign/resume processes.
    with (output / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _execute(plan, output, run_cell, stop_after_block)


def _execute(plan, output, run_cell, stop_after_block):
    state_path, frozen = output / 'state.json', output / 'plan.json'
    if frozen.exists():
        if json.loads(frozen.read_text()) != plan:
            raise ValueError('Resume plan differs from frozen plan')
        state = json.loads(state_path.read_text())
        if state['active_block'] is not None:
            raise ValueError('Incomplete block cannot be resumed or replayed')
    else:
        if any(p.name != '.lock' for p in output.iterdir()):
            raise ValueError('New campaign output must be empty')
        atomic_json(frozen, plan)
        state = {'plan_hash': plan['plan_hash'], 'completed_blocks': [], 'active_block': None,
                 'cells': {}, 'cell_timing': {},
                 'started_epoch': time.time() - plan['telemetry']['build_seconds'],
                 'build_seconds_accounted_once': plan['telemetry']['build_seconds'],
                 'spent': dict.fromkeys(('requests', 'input_tokens', 'output_tokens', 'money'), 0.),
                 'reservations': [], 'fatal': None}
        atomic_json(state_path, state)
    if getattr(run_cell, 'preflight', None) and not state.get('preflight_complete'):
        admission(plan, state, 1)
        state['active_block'] = 0  # An interrupted preflight cannot be replayed.
        atomic_json(state_path, state)
        run_cell.preflight(plan, output, state_path)
        state = json.loads(state_path.read_text())
        if state.get('fatal'):
            raise ValueError('Preflight recorded fatal failure')
        state.update(preflight_complete=True, active_block=None)
        atomic_json(state_path, state)
    for block in (1, 2):
        state = json.loads(state_path.read_text())
        if block in state['completed_blocks']:
            continue
        admission(plan, state, block)
        state['active_block'] = block
        atomic_json(state_path, state)
        for cell in (c for c in plan['cells'] if c['block'] == block):
            state = json.loads(state_path.read_text())
            if cell['id'] in state['cells']:
                raise ValueError('Started cell cannot be repeated')
            destination = output / cell['id']
            destination.mkdir()
            state['cells'][cell['id']] = 'started'
            state['cell_timing'][cell['id']] = {'started': time.time()}
            atomic_json(state_path, state)
            try:
                run_cell(plan, cell, destination, state_path)
                state = json.loads(state_path.read_text())
                if state.get('fatal'):
                    raise ValueError('Cell recorded fatal integrity failure')
                complete = json.loads((destination / 'completion.json').read_text())
                if complete['case_ids'] != cell['cases'] or complete['plan_hash'] != plan['plan_hash']:
                    raise ValueError('Cell completion/order mismatch')
                state['cells'][cell['id']] = 'complete'
                state['cell_timing'][cell['id']]['finished'] = time.time()
                atomic_json(state_path, state)
            except BaseException:
                # Leave active block and started cell intact, even on interruption.
                raise
        state = json.loads(state_path.read_text())
        state['completed_blocks'].append(block)
        state['active_block'] = None
        if block == 2:
            state['finished_epoch'] = time.time()
        atomic_json(state_path, state)
        if stop_after_block == block:
            break
    return json.loads(state_path.read_text())


def docker_callback(dataset_root, indices):
    """No gold mounted, no stdout accuracy evaluation; one immutable image."""
    root, indices = Path(dataset_root).resolve(), Path(indices).resolve()
    def container(plan, identifier, destination, state_path, arguments, inputs=None):
        metadata = json.loads(subprocess.check_output(
            ['docker', 'image', 'inspect', plan['image']], text=True))[0]
        if metadata['Id'] != plan['image'] or metadata['Config'].get('Labels', {}).get(
                'org.opencontainers.image.revision') != plan['commit']:
            raise ValueError('Image digest/source commit mismatch')
        campaign = destination.parent.resolve()
        command = ['docker', 'run', '--rm', '--cpus', '4', '--memory', '40g',
            '-e', 'OPENAI_API_KEY', '-e', 'OPENAI_BASE_URL',
            '-v', f'{indices}:/indices:ro', '-v', f'{campaign}:/campaign',
            '--entrypoint', 'python', plan['image'], '-m', 'scripts.task2_factorial.worker',
            '--plan', '/campaign/plan.json', '--output', f'/campaign/{identifier}',
            '--budget', '/campaign/state.json']
        command.extend(arguments)
        if inputs is not None:
            command[3:3] = ['-v', f'{inputs}:/inputs:ro']
        # Complete both serial blocks within the remaining global wall quota.
        state = json.loads(state_path.read_text())
        remaining = plan['quotas']['wall_seconds'] - (time.time() - state['started_epoch'])
        with (destination / 'worker.log').open('w') as log:
            # Docker --rm alone would leave a timed-out container running. Use a
            # deterministic name and always remove it on interruption/timeout.
            name = 'uniagent-factorial-' + plan['plan_hash'][:12] + '-' + identifier
            command[3:3] = ['--name', name]
            try:
                subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT,
                               timeout=max(.001, remaining))
            finally:
                subprocess.run(['docker', 'rm', '-f', name], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, check=False)
    def launch(plan, cell, destination, state_path):
        container(plan, cell['id'], destination, state_path,
            ['--cell', cell['id'], '--inputs', '/inputs', '--indices', '/indices'],
            root / cell['dataset'] / 'inputs')
    def preflight(plan, output, state_path):
        for effort in ('medium', 'high'):
            identifier = 'preflight-' + effort
            destination = output / identifier
            destination.mkdir()
            container(plan, identifier, destination, state_path, ['--preflight', effort])
    launch.preflight = preflight
    return launch
