#!/usr/bin/env python3
"""Join a native preparation receipt to first-use/restarted exports. Never infer hits or power."""
import argparse
import json
import math
import re
from pathlib import Path
from compare_efficiency import finite, included_seconds, load_export
from analyse_efficiency import audit

MAX_ARCHIVE = 64 * 1024 * 1024
PIN = 'db66022459ffb663aa2b50f6b018bc2e124f5edf'


def valid_count(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def audit_preparation(first, receipt, restarted):
    errors, warnings = [], []
    before, after = receipt.get('before', {}), receipt.get('after', {})
    identity = receipt.get('preceding_session_metadata', {})
    metas = [d.get('metadata', {}) for d in (first, restarted)]
    if receipt.get('schema_version') != 1 or receipt.get('type') != 'paused_native_pipeline_preparation':
        errors.append('Unsupported preparation receipt')
    for key in ('build_sha', 'device_identifier', 'os'):
        values = [m.get(key) for m in metas] + [identity.get(key)]
        if any(not isinstance(v, str) or not v or v == 'UNAVAILABLE' for v in values) or len(set(values)) != 1:
            errors.append('Missing/different preparation identity: ' + key)
    if receipt.get('build_sha') != metas[0].get('build_sha'):
        errors.append('Receipt build differs from first-use build')
    if not identity.get('session_id') or identity.get('session_id') != metas[0].get('session_id'):
        errors.append('Receipt is not linked to the first-use session')
    if not metas[1].get('session_id') or metas[0].get('session_id') == metas[1].get('session_id'):
        errors.append('Distinct restarted capture is required')
    configs = [m.get('launch_configuration', {}) for m in metas]
    if not configs[0] or configs[0] != configs[1] or configs[0] != receipt.get('configuration'):
        errors.append('Launch configuration changed across capture/preparation/restart')
    if any(c.get('native_pipeline_archive_mode') != 2 for c in configs):
        errors.append('Archive Enabled must be selected in both captures')
    builds = [d.get('spatial_upscaling', {}).get('driver_build') for d in (first, restarted)] + [receipt.get('driver_build')]
    for build in builds:
        if (not isinstance(build, dict) or build.get('upstream_commit') != PIN or build.get('native_archive_abi') not in (1, 2)
                or not isinstance(build.get('husk_native_pipeline_patch_sha256'), str)
                or not re.fullmatch('[0-9a-f]{64}', build['husk_native_pipeline_patch_sha256'])):
            errors.append('Missing/incompatible native driver identity')
    if builds[0] != builds[1] or builds[0] != builds[2]:
        errors.append('Driver manifest differs across capture/preparation/restart')
    if receipt.get('game_pause_requested') is not True or receipt.get('no_gpu_idle_wait') is not True:
        errors.append('Expected pause/no-idle-wait preparation route is not recorded')
    if receipt.get('result') != 1:
        errors.append('Native preparation did not report successful persistence')
    for name, stats in [('before', before), ('after', after)]:
        for key in ('pending', 'prepared', 'prepare_calls', 'saved_bytes', 'prepare_ns', 'write_failures', 'read_failures'):
            if not valid_count(stats.get(key)):
                errors.append('Missing/invalid ' + name + ' counter: ' + key)
        if stats.get('supported') is not True or stats.get('requested') is not True:
            errors.append(name + ': native support/request not established')
    pending = before.get('pending')
    if not valid_count(pending) or not 1 <= pending <= 8:
        errors.append('Preparation needs one to eight captured native requests')
    deltas = {}
    for key in ('prepared', 'prepare_calls', 'prepare_ns', 'write_failures', 'read_failures'):
        a, b = before.get(key), after.get(key)
        if valid_count(a) and valid_count(b) and b >= a:
            deltas[key] = b - a
        else:
            errors.append('Nonmonotonic/missing preparation counter: ' + key)
    if deltas.get('prepare_calls') != 1:
        errors.append('Receipt must cover exactly one preparation call')
    if not 1 <= deltas.get('prepared', 0) <= (pending if valid_count(pending) else 0):
        errors.append('Prepared request count is outside captured bounds')
    saved = after.get('saved_bytes')
    if not valid_count(saved) or not 0 < saved <= MAX_ARCHIVE:
        errors.append('Saved archive size missing or outside bounds')
    for key in ('write_failures', 'read_failures'):
        if deltas.get(key):
            warnings.append('Preparation includes ' + key)
    wall, cpu = receipt.get('measured_host_wall_seconds'), receipt.get('estimated_process_cpu_seconds')
    if not finite(wall) or wall <= 0:
        errors.append('Preparation wall time unavailable/invalid')
    if cpu is not None and (not finite(cpu) or cpu < 0):
        errors.append('Preparation process CPU delta invalid')
    if cpu is None:
        warnings.append('Preparation process CPU delta unavailable; compiler/system CPU is always outside this scope')
    start, end = receipt.get('started_monotonic_seconds'), receipt.get('ended_monotonic_seconds')
    if not finite(start) or not finite(end) or end < start or not finite(wall) or abs(end-start-wall) > .01:
        errors.append('Preparation monotonic endpoints do not reconcile with wall time')
    if finite(wall) and wall > 2:
        warnings.append('Wall exceeds two seconds; budget bounds call starts, not one uninterruptible native call or callback scheduling')
    session_metrics = []
    for label, data in [('first_use', first), ('restarted', restarted)]:
        result = audit(data)
        errors.extend(label + ': ' + x for x in result['errors'])
        warnings.extend(label + ': ' + x for x in result['warnings'])
        archive = data.get('native_pipeline_archive', {})
        if archive.get('requested') is not True or archive.get('supported') is not True:
            errors.append(label + ': actual native archive support not established')
        if label == 'restarted':
            if not valid_count(archive.get('restored_bytes')) or not 0 < archive['restored_bytes'] <= MAX_ARCHIVE:
                errors.append('Restart has no bounded restored native archive evidence')
            if not valid_count(archive.get('archive_attachments')) or archive['archive_attachments'] <= 0:
                errors.append('Restart has no archive attachment evidence')
        if archive.get('archive_fallbacks'):
            warnings.append(label + ': ordinary compiler fallback occurred')
        session_metrics.append({'phase': label, 'included_wall_seconds': included_seconds(data), **result['host'],
                                'native_archive': archive})
    warnings.append('A distinct session ID and restore counters support restart evidence; they do not independently prove a process restart')
    warnings.append('First-use and restarted sessions are different cache conditions; their metrics are descriptive, not a controlled optimisation comparison')
    return {'audit_version': 1, 'plan_ids': ['M2', 'M5', 'M3'],
            'status': 'BLOCKED' if errors else 'MECHANISM PREFLIGHT ONLY; DEVICE AND BENEFIT REVIEW REQUIRED',
            'errors': sorted(set(errors)), 'warnings': sorted(set(warnings)),
            'preparation': {'host_wall_seconds': wall, 'process_cpu_seconds_estimated': cpu,
                            'native_counter_deltas': deltas, 'saved_bytes': saved},
            'sessions': session_metrics, 'cache_hit_verified': False, 'energy_improvement': 'UNVERIFIED',
            'roadmap_gates_automatically_passed': [], 'watts': None, 'temperature_c': None,
            'scope': 'Full-process preparation CPU excludes compiler/system processes; no energy can be computed from time alone. Include the preparation receipt and any uncaptured startup/loading in later net-cost acceptance.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('first_use', type=Path)
    parser.add_argument('receipt', type=Path)
    parser.add_argument('restarted', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    paths = [args.first_use, args.receipt, args.restarted]
    if args.output and args.output.resolve() in [p.resolve() for p in paths]:
        parser.error('Output must not overwrite raw evidence')
    loaded = [load_export(p) for p in paths]
    result = audit_preparation(*(item[0] for item in loaded))
    result['inputs'] = {key: item[1] for key, item in zip(['first_use', 'receipt', 'restarted'], loaded)}
    text = json.dumps(result, indent=2, allow_nan=False) + '\n'
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
