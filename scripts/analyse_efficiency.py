#!/usr/bin/env python3
"""Audit Husk exports offline; observations never establish energy savings alone."""
import argparse
import json
import math
from pathlib import Path


def interval_union(rows):
    intervals = []
    for row in rows:
        fields = [row.get(k) for k in ('gpu_start_media_seconds', 'gpu_end_media_seconds',
                                      'sample_start_media_seconds', 'sample_end_media_seconds')]
        if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in fields):
            continue
        start, end, lower, upper = fields
        a, b = max(start, lower), min(end, upper)
        if b > a:
            intervals.append((a, b))
    total, end = 0.0, -math.inf
    for a, b in sorted(intervals):
        total += max(0, b - max(a, end))
        end = max(end, b)
    return total


def gpu_exclusion_audit(data):
    """Clip using conservative direct brackets, or explicit legacy clock estimate."""
    def finite(*values):
        return all(isinstance(v, (int, float)) and math.isfinite(v) for v in values)
    metadata = data.get('metadata', {})
    alignment = metadata.get('gpu_clock_alignment', {})
    mono, media, origin = (alignment.get('monotonic_anchor_seconds'),
                           alignment.get('media_anchor_seconds'), metadata.get('monotonic_origin_seconds'))
    offset = mono - media - origin if finite(mono, media, origin) else None
    exclusions, direct, mapped, uncertainty = [], 0, 0, 0.0
    for row in data.get('exclusions', []):
        bounds = [row.get(k) for k in ('gpu_media_start_before_seconds', 'gpu_media_start_after_seconds',
                                       'gpu_media_end_before_seconds', 'gpu_media_end_after_seconds')]
        if finite(*bounds) and bounds[0] <= bounds[1] <= bounds[2] <= bounds[3]:
            # Exclude the whole uncertainty bracket; never silently count its edge as gameplay.
            exclusions.append((bounds[0], bounds[3])); direct += 1
            uncertainty += bounds[1] - bounds[0] + bounds[3] - bounds[2]
        else:
            lo, hi = row.get('start'), row.get('end')
            if offset is None or not finite(lo, hi) or hi < lo:
                return {'status': 'UNAVAILABLE: exclusion has no valid direct brackets or clock alignment',
                        'included_interval_union_seconds_estimated': None, 'records_overlapping_exclusions': None}
            if hi > lo:
                exclusions.append((lo-offset, hi-offset)); mapped += 1
    if offset is None and not direct:
        return {'status': 'UNAVAILABLE: no valid cross-clock alignment or direct brackets',
                'included_interval_union_seconds_estimated': None, 'records_overlapping_exclusions': None}
    end = metadata.get('gpu_clock_alignment_end', {})
    end_mono, end_media = end.get('monotonic_anchor_seconds'), end.get('media_anchor_seconds')
    drift = end_mono - end_media - (mono - media) if finite(end_mono, end_media, mono, media) else None
    retained, overlapping = [], 0
    for row in data.get('gpu_records', []) + data.get('gpu_recent_records', []):
        values = [row.get(k) for k in ('gpu_start_media_seconds', 'gpu_end_media_seconds',
                                     'sample_start_media_seconds', 'sample_end_media_seconds')]
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in values):
            continue
        lo, hi = max(values[0], values[2]), min(values[1], values[3])
        if hi <= lo:
            continue
        pieces, hit = [(lo, hi)], False
        for a, b in exclusions:
            next_pieces = []
            for x, y in pieces:
                if y <= a or x >= b:
                    next_pieces.append((x, y))
                else:
                    hit = True
                    if x < a:
                        next_pieces.append((x, a))
                    if y > b:
                        next_pieces.append((b, y))
            pieces = next_pieces
        overlapping += int(hit)
        retained.extend({'gpu_start_media_seconds': x, 'gpu_end_media_seconds': y,
                         'sample_start_media_seconds': x, 'sample_end_media_seconds': y} for x, y in pieces)
    return {'status': 'ESTIMATED: conservative direct brackets / legacy anchor mapping; raw measurements preserved',
            'direct_exclusion_count': direct, 'anchor_mapped_exclusion_count': mapped,
            'direct_boundary_uncertainty_seconds': uncertainty, 'clock_offset_change_seconds': drift,
            'included_interval_union_seconds_estimated': interval_union(retained),
            'records_overlapping_exclusions': overlapping,
            'scope': 'Partial sampled buffers, not GPU utilisation, per-frame cost or power'}


def thread_cpu_audit(data):
    """Deltas only for matching thread identities in successive included snapshots."""
    previous = None
    costs = {}
    for sample in data.get('samples', []):
        if sample.get('excluded'):
            previous = None
            continue
        snapshot = sample.get('cpu_threads', {})
        if not snapshot or snapshot.get('mach_result') != 0:
            continue
        rows = {r['thread_id']: r for r in snapshot.get('threads', []) if 'thread_id' in r}
        if previous:
            before_t, before = previous
            dt = sample['t'] - before_t
            overlaps_exclusion = False
            for exclusion in data.get('exclusions', []):
                a, b = exclusion.get('start'), exclusion.get('end')
                if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in (a, b)) or b < a:
                    overlaps_exclusion = True
                    break
                if max(before_t, a) < min(sample['t'], b):
                    overlaps_exclusion = True
                    break
            if dt > 0 and not overlaps_exclusion:
                for key in rows.keys() & before.keys():
                    r, old = rows[key], before[key]
                    delta = r['user_seconds'] + r['system_seconds'] - old['user_seconds'] - old['system_seconds']
                    if math.isfinite(delta) and delta >= 0:
                        value = costs.setdefault(key, {'thread_id': key, 'name': r.get('name', ''), 'cpu_seconds': 0.0, 'observed_seconds': 0.0})
                        value['cpu_seconds'] += delta
                        value['observed_seconds'] += dt
        previous = (sample['t'], rows)
    policy = {r['mach_thread_id']: r for r in data.get('worker_policy', {}).get('last_observed_workers', []) if r.get('mach_thread_id')}
    for key, row in costs.items():
        if key in policy:row['last_guest_policy_observation'] = policy[key]
    rows = sorted(costs.values(), key=lambda r: r['cpu_seconds'], reverse=True)
    for row in rows:
        row['cpu_percent_one_core'] = row['cpu_seconds'] / row['observed_seconds'] * 100
    return {'status': 'MEASURED cumulative counters / ESTIMATED per-thread deltas' if rows else 'UNAVAILABLE: no paired included thread snapshots',
            'top_threads': rows[:16], 'scope': 'Only intersecting identities with no excluded interval between samples; host included; exited/missing threads absent, not P/E placement or electrical power'}


def audit(data):
    if data.get('schema_version') not in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14):
        raise ValueError('Unsupported diagnostic schema; preserve source for a version-aware audit')
    summary, metadata = data.get('summary', {}), data.get('metadata', {})
    windows, samples = data.get('windows', []), data.get('samples', [])
    errors, warnings = [], []
    for field in ('interval_count', 'interval_seconds', 'above_20_ms', 'above_33_333333_ms',
                  'above_50_ms', 'slow_pipeline_calls'):
        if field in summary and windows:
            values = [w.get(field) for w in windows]
            if any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
                errors.append('Invalid window field: ' + field)
            elif not math.isclose(sum(values), summary[field], rel_tol=1e-9, abs_tol=1e-6):
                errors.append('Window/summary mismatch: ' + field)
    for field in ('host_calls', 'host_ns'):
        if field in summary and windows:
            values = [w.get(field) for w in windows]
            if all(isinstance(v, list) and len(v) == len(summary[field]) for v in values):
                sums = [sum(v[i] for v in values) for i in range(len(summary[field]))]
                if sums != summary[field]:
                    errors.append('Window/summary mismatch: ' + field)
            else:
                errors.append('Invalid stage arrays: ' + field)
    count, seconds = summary.get('interval_count', 0), summary.get('interval_seconds', 0)
    cadence = count / seconds if isinstance(seconds, (int, float)) and seconds > 0 else None
    reported = summary.get('host_cadence_fps')
    if cadence is not None and reported is not None and not math.isclose(cadence, reported, rel_tol=1e-9):
        errors.append('Reported cadence does not equal retained intervals/duration')
    if summary.get('dropped_frame_intervals_cumulative', 0):
        warnings.append('Frame intervals were lost; retained percentiles are incomplete')
    if data['schema_version'] == 1 and summary.get('dropped_collector_records', 0):
        warnings.append('Legacy mixed losses may reset cadence continuity')
    gpu = data.get('gpu_sampling', {})
    gpu_rows = data.get('gpu_records', []) + data.get('gpu_recent_records', [])
    union = interval_union(gpu_rows)
    if gpu.get('valid_records') is not None and gpu['valid_records'] != len(gpu_rows) + gpu.get('dropped_export_records', 0):
        errors.append('GPU valid/exported record counts do not reconcile')
    if 'observed_interval_union_seconds' in gpu and not math.isclose(union, gpu['observed_interval_union_seconds'], rel_tol=1e-9, abs_tol=1e-9):
        errors.append('GPU interval union does not match export')
    if gpu.get('dropped_records_or_capture_attempts', 0) or gpu.get('unresolved_handlers_at_snapshot', 0):
        warnings.append('GPU sampled coverage has losses or unresolved handlers')
    exclusion_audit = gpu_exclusion_audit(data)
    if exclusion_audit['records_overlapping_exclusions']:
        warnings.append('GPU records overlap exported exclusions at direct/estimated clock boundaries; use corrected analysis, not raw union, for included scope')
    gpu_windows = data.get('gpu_windows', [])
    if gpu_windows:
        captured = sum(w.get('valid_records', 0) for w in gpu_windows)
        if captured != gpu.get('aggregate_records') or captured + gpu.get('dropped_aggregate_records', 0) != gpu.get('valid_records'):
            errors.append('GPU aggregate/valid record counts do not reconcile')
        aggregate_union = sum(w.get('sample_clipped_interval_union_seconds', 0) for w in gpu_windows)
        if not math.isclose(aggregate_union, gpu.get('all_window_sample_clipped_union_seconds', -1), rel_tol=1e-9, abs_tol=1e-9):
            errors.append('GPU aggregate union does not reconcile')
    if gpu.get('dropped_export_records', 0):
        warnings.append('GPU raw export cap reached; use bounded aggregate windows when available, not raw totals as full-session coverage')
    inventory = data.get('render_inventory', {})
    if inventory.get('active'):
        warnings.append('Render inventory adds diagnostic observation work; not a monitoring-off energy comparison')
    if inventory.get('dropped_observations', 0):
        warnings.append('Render inventory has lost observations; absent sizes are not evidence of absent render targets')
    worker = data.get('worker_policy', {})
    utility = [w for w in worker.get('last_observed_workers', [])
               if w.get('role') == 1 and w.get('query_result') == 0 and w.get('after_qos') == 0x11]
    if worker.get('active_mode') in (3, 4) and worker.get('admissions_since_launch', 0) == 0:
        warnings.append('Adaptive selected but no admitted trial observed; energy comparison has no admitted treatment')
    elif worker.get('active_mode') == 2:
        warnings.append('Balanced run; additional Adaptive normal-worker caps were not requested')
    groups = sorted(data.get('pipeline_groups_since_launch', []), key=lambda g: g.get('worst_host_ns', 0), reverse=True)
    brightness = sorted({s['environment']['brightness'] for s in samples
                         if isinstance(s.get('environment'), dict) and 'brightness' in s['environment']})
    states = sorted({s['battery_state'] for s in samples if 'battery_state' in s})
    cpu = [(s.get('process_cpu_percent_one_core'), s.get('cpu_sample_elapsed_seconds')) for s in samples if not s.get('excluded')]
    cpu = [(v, dt) for v, dt in cpu if isinstance(v, (int, float)) and isinstance(dt, (int, float)) and dt > 0]
    cpu_mean = sum(v * dt for v, dt in cpu) / sum(dt for _, dt in cpu) if cpu else None
    display = data.get('native_display_sampling', {})
    if display.get('available'):
        hist = display.get('histogram_0_1ms', [])
        if len(hist) != 512 or any(type(v) is not int or v < 0 for v in hist) or sum(hist) != display.get('valid_intervals'):
            errors.append('Native display histogram/interval count does not reconcile')
        direct, estimated = display.get('direct_drawable_events'), display.get('estimated_events')
        rows, overwritten = display.get('records', []), display.get('record_overwrites')
        if all(type(v) is int and v >= 0 for v in (direct, estimated, overwritten)) and direct + estimated != len(rows) + overwritten:
            errors.append('Native display raw-tail accounting does not reconcile')
        if display.get('contention_drops') or display.get('boundary_events') or display.get('invalid_events'):
            warnings.append('Native display capture has gaps/invalid/boundary observations; cadence is partial')
    return {'analysis_version': 3, 'build': metadata.get('build_sha'), 'schema_version': data['schema_version'],
            'configuration': metadata.get('launch_configuration', {}), 'errors': errors, 'warnings': warnings,
            'host': {'retained_fps': cadence, 'p95_ms': summary.get('p95_ms'), 'p99_ms': summary.get('p99_ms'),
                     'worst_ms': summary.get('worst_ms'), 'slow_pipeline_calls': summary.get('slow_pipeline_calls'),
                     'cpu_weighted_percent_one_core': cpu_mean},
            'gpu': {'status': gpu.get('status', 'UNAVAILABLE: no sampled GPU data'), 'records': len(gpu_rows), 'primary_records': len(data.get('gpu_records', [])), 'recent_records': len(data.get('gpu_recent_records', [])),
                    'sample_clipped_interval_union_seconds': union, 'exclusion_audit': exclusion_audit,
                    'scope': 'Partial sampled command buffers; not utilisation, displayed frames or watts'},
            'worker': {'active_mode': worker.get('active_mode'), 'admissions': worker.get('admissions_since_launch'),
                       'rollbacks': worker.get('rollback_requests_since_launch'), 'waiting_reason': worker.get('waiting_reason'),
                       'normal_utility_last_observations': len(utility), 'core_residency': 'UNAVAILABLE',
                       'scope': 'Last observations, not live thread count or verified placement'},
            'native_pipeline_archive': data.get('native_pipeline_archive', {}), 'pipeline_identity_registry': data.get('pipeline_identity_registry', {}), 'component_sampling': data.get('component_sampling', {}), 'native_display_sampling': data.get('native_display_sampling', {}),
            'queue_execution_options': data.get('queue_execution_options', {}), 'initialization_waits': data.get('initialization_waits', {}),
            'driver_phases': data.get('driver_phases', {}), 'component_triage': data.get('component_triage', {}),
            'delayed_os_reports': data.get('delayed_os_reports', {}),
            'presentation_clock': data.get('presentation_clock', {}), 'compatibility_sync': data.get('compatibility_sync', {}),
            'thread_cpu': thread_cpu_audit(data), 'submit_cpu_work': data.get('submit_cpu_work', {}),
            'gpu_windows': data.get('gpu_windows', []),
            'spatial_upscaling': data.get('spatial_upscaling', {}),
            'pipeline_feedback_request': data.get('pipeline_feedback_request', {}),
            'pipeline_groups_since_launch_top8': groups[:8], 'render_inventory': data.get('render_inventory', {}),
            'conditions': {'brightness_values': brightness, 'battery_states': states},
            'battery': {'coarse_pp_per_hour': data.get('battery_drain_pp_per_hour_estimated'),
                        'status': data.get('battery_estimate_status'), 'power_watts': None},
            'energy_benefit': 'UNVERIFIED: needs controlled comparable measurements'}


def compare(left, right):
    differences = []
    for field in sorted(set(left['configuration']) | set(right['configuration'])):
        if left['configuration'].get(field) != right['configuration'].get(field):
            differences.append('configuration.' + field)
    for field in ('brightness_values', 'battery_states'):
        if left['conditions'].get(field) != right['conditions'].get(field):
            differences.append('conditions.' + field)
    return {'changed_fields': differences,
            'host_fps_difference': (right['host']['retained_fps'] - left['host']['retained_fps'])
                if left['host']['retained_fps'] is not None and right['host']['retained_fps'] is not None else None,
            'interpretation': 'Descriptive only; scene, cache, temperature, display delivery and repeatability are not established by matching metadata',
            'energy_improvement': 'UNVERIFIED'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files', nargs='+', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    analyses = [audit(json.loads(path.read_text())) for path in args.files]
    result = {'sessions': analyses, 'comparisons_to_first': [compare(analyses[0], a) for a in analyses[1:]]}
    text = json.dumps(result, indent=2, allow_nan=False)
    if args.output:
        args.output.write_text(text + '\n')
    else:
        print(text)
    return int(any(a['errors'] for a in analyses))


if __name__ == '__main__':
    raise SystemExit(main())

