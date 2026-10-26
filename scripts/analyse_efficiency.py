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
    """Estimated cross-clock clipping; raw exported records remain untouched."""
    alignment = data.get('metadata', {}).get('gpu_clock_alignment', {})
    fields = [alignment.get('monotonic_anchor_seconds'), alignment.get('media_anchor_seconds'),
              data.get('metadata', {}).get('monotonic_origin_seconds')]
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in fields):
        return {'status': 'UNAVAILABLE: no valid cross-clock alignment',
                'included_interval_union_seconds_estimated': None, 'records_overlapping_exclusions': None}
    offset = fields[0] - fields[1] - fields[2]
    exclusions = []
    for row in data.get('exclusions', []):
        lo, hi = row.get('start'), row.get('end')
        if isinstance(lo, (int, float)) and isinstance(hi, (int, float)) and math.isfinite(lo) and math.isfinite(hi) and hi > lo:
            exclusions.append((lo-offset, hi-offset))
    retained, overlapping = [], 0
    for row in data.get('gpu_records', []):
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
    return {'status': 'ESTIMATED: anchor-mapped exclusions; raw measurements preserved',
            'included_interval_union_seconds_estimated': interval_union(retained),
            'records_overlapping_exclusions': overlapping,
            'scope': 'Partial sampled buffers, not GPU utilisation, per-frame cost or power'}


def audit(data):
    if data.get('schema_version') not in (1, 2, 3, 4, 5, 6):
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
    gpu, gpu_rows = data.get('gpu_sampling', {}), data.get('gpu_records', [])
    union = interval_union(gpu_rows)
    if gpu.get('valid_records') is not None and gpu['valid_records'] != len(gpu_rows) + gpu.get('dropped_export_records', 0):
        errors.append('GPU valid/exported record counts do not reconcile')
    if 'observed_interval_union_seconds' in gpu and not math.isclose(union, gpu['observed_interval_union_seconds'], rel_tol=1e-9, abs_tol=1e-9):
        errors.append('GPU interval union does not match export')
    if gpu.get('dropped_records_or_capture_attempts', 0) or gpu.get('unresolved_handlers_at_snapshot', 0):
        warnings.append('GPU sampled coverage has losses or unresolved handlers')
    exclusion_audit = gpu_exclusion_audit(data)
    if exclusion_audit['records_overlapping_exclusions']:
        warnings.append('GPU records overlap exported exclusions after estimated clock mapping; use corrected analysis, not raw union, for included scope')
    inventory = data.get('render_inventory', {})
    if inventory.get('active'):
        warnings.append('Render inventory adds diagnostic observation work; not a monitoring-off energy comparison')
    if inventory.get('dropped_observations', 0):
        warnings.append('Render inventory has lost observations; absent sizes are not evidence of absent render targets')
    worker = data.get('worker_policy', {})
    utility = [w for w in worker.get('last_observed_workers', [])
               if w.get('role') == 1 and w.get('query_result') == 0 and w.get('after_qos') == 0x11]
    if worker.get('active_mode') == 3 and worker.get('admissions_since_launch', 0) == 0:
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
    return {'analysis_version': 2, 'build': metadata.get('build_sha'), 'schema_version': data['schema_version'],
            'configuration': metadata.get('launch_configuration', {}), 'errors': errors, 'warnings': warnings,
            'host': {'retained_fps': cadence, 'p95_ms': summary.get('p95_ms'), 'p99_ms': summary.get('p99_ms'),
                     'worst_ms': summary.get('worst_ms'), 'slow_pipeline_calls': summary.get('slow_pipeline_calls'),
                     'cpu_weighted_percent_one_core': cpu_mean},
            'gpu': {'status': gpu.get('status', 'UNAVAILABLE: no sampled GPU data'), 'records': len(gpu_rows),
                    'sample_clipped_interval_union_seconds': union, 'exclusion_audit': exclusion_audit,
                    'scope': 'Partial sampled command buffers; not utilisation, displayed frames or watts'},
            'worker': {'active_mode': worker.get('active_mode'), 'admissions': worker.get('admissions_since_launch'),
                       'rollbacks': worker.get('rollback_requests_since_launch'), 'waiting_reason': worker.get('waiting_reason'),
                       'normal_utility_last_observations': len(utility), 'core_residency': 'UNAVAILABLE',
                       'scope': 'Last observations, not live thread count or verified placement'},
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

