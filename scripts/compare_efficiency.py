#!/usr/bin/env python3
"""Preflight paired Husk exports. No automatic optimisation or roadmap acceptance."""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path

from analyse_efficiency import audit

RECIPES = {
    'strict-worker': ('worker_policy', 2, 3, ['M7', 'M3']),
    'relative-worker': ('worker_policy', 2, 4, ['M7', 'M3']),
    'engine-only': ('engine_only_limiter', False, True, ['M4']),
    'async': ('submission_mode', 0, 1, ['M6']),
    'prefill': ('metal_prefill', -1, 1, ['M6', 'M8']),
    'swapchain-images': ('swapchain_image_budget', 0, 2, ['M6', 'M8']),
    'buffer-limit': ('metal_command_buffer_limit', 0, 8, ['M6', 'M8']),
    'initialization-parking': ('initialization_parking', False, True, ['M8', 'M3']),
    'spatial': ('metalfx_spatial_requested', False, True, ['M9', 'M3']),
    'native-archive': ('native_pipeline_archive_mode', 1, 2, ['M2', 'M5']),
    'feedback-clock': ('feedback_clock_correction', False, True, ['M4', 'M6']),
    'presentation-clock': ('clock_correct_presentation', False, True, ['M4', 'M6']),
}
REQUIRED_CONFIG = ('engine', 'game', 'launch_width', 'launch_height', 'sharp_graphics',
                   'efficient_graphics', 'requested_fps', 'worker_policy', 'submission_mode',
                   'detailed_driver_profiling', 'metalfx_spatial_requested', 'windowed')
MAX_BYTES = 32 * 1024 * 1024
CONTEXT_FIELDS = ('route', 'cache_state', 'case', 'ambient_c', 'starting_surface_c')


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def load_export(path):
    """Bound decompression; hash the original bytes and decoded diagnostic separately."""
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError('Input exceeds 32 MiB: ' + str(path))
    raw = path.read_bytes()
    if len(raw) > MAX_BYTES:
        raise ValueError('Input exceeds 32 MiB: ' + str(path))
    if path.suffix == '.gz':
        with gzip.open(path, 'rb') as stream:
            decoded = stream.read(MAX_BYTES + 1)
    else:
        decoded = raw
    if len(decoded) > MAX_BYTES:
        raise ValueError('Decoded input exceeds 32 MiB: ' + str(path))
    def invalid_constant(value):
        raise ValueError('Non-finite JSON number: ' + value)
    return json.loads(decoded, parse_constant=invalid_constant), {'path': str(path), 'file_sha256': hashlib.sha256(raw).hexdigest(),
                                'decoded_sha256': hashlib.sha256(decoded).hexdigest()}


def included_seconds(data):
    duration = data.get('duration_seconds')
    if not finite(duration) or duration <= 0:
        return None
    intervals = []
    for row in data.get('exclusions', []):
        a, b = row.get('start'), row.get('end')
        if not finite(a) or not finite(b) or b < a or a < 0 or b > duration + .01:
            return None
        intervals.append((max(0, a), min(duration, b)))
    excluded, end = 0.0, 0.0
    for a, b in sorted(intervals):
        excluded += max(0, b - max(a, end))
        end = max(end, b)
    return duration - excluded


def included_point(data, t):
    if not finite(t) or not finite(data.get('duration_seconds')) or not 0 <= t <= data['duration_seconds']:
        return False
    for row in data.get('exclusions', []):
        a, b = row.get('start'), row.get('end')
        if not finite(a) or not finite(b) or b < a or a <= t <= b:
            return False
    return True


def worker_treatment(data, mode):
    summary = data.get('worker_policy', {})
    observations = [r for r in summary.get('last_observed_workers', [])
                    if r.get('role') == 1 and r.get('mode') == mode and r.get('after_qos') == 0x11
                    and r.get('set_result') == 0 and r.get('query_result') == 0
                    and included_point(data, r.get('observed_t'))]
    samples = [r for r in data.get('samples', []) if r.get('excluded') is False and included_point(data, r.get('t'))]
    controllers = [r.get('worker_controller', {}) for r in samples]
    values = [r.get('admissions_since_launch') for r in controllers if finite(r.get('admissions_since_launch'))]
    return {'included_normal_utility_observations': len(observations),
            'included_trial_requested_samples': sum(r.get('trial_requested') is True for r in controllers),
            'included_admission_counter_increase': max(values) - min(values) if values else None,
            'lifetime_admissions': summary.get('admissions_since_launch'),
            'lifetime_rollback_requests': summary.get('rollback_requests_since_launch'),
            'scope': 'Last bounded observations and sampled counters; excluded/pre-session observations do not prove treatment. No core residency or energy.'}


def run_metrics(data, analysed):
    summary = data.get('summary', {})
    seconds, count = included_seconds(data), summary.get('interval_count')
    def rate(key):
        n = summary.get(key)
        return 1000 * n / count if finite(n) and finite(count) and count > 0 else None
    return {'included_wall_seconds': seconds, 'host_interval_count': count, **analysed['host'],
            'reported_swapchain_dimensions': [summary.get('swapchain_width'), summary.get('swapchain_height')],
            'over20_per1000_host_intervals': rate('above_20_ms'),
            'over33_per1000_host_intervals': rate('above_33_333333_ms'),
            'over50_per1000_host_intervals': rate('above_50_ms'),
            'slow_pipeline_calls_per_included_minute': summary.get('slow_pipeline_calls', 0) * 60 / seconds if seconds else None,
            'worst_pipeline_ms': summary['worst_pipeline_ns'] / 1e6 if finite(summary.get('worst_pipeline_ns')) else None,
            'cpu_scope': 'Process CPU, 100% = one logical CPU; not electrical power',
            'gpu': analysed['gpu'], 'battery': analysed['battery'],
            'submit_cpu_work': analysed['submit_cpu_work'], 'top_threads': analysed['thread_cpu']['top_threads'],
            'native_pipeline_archive': analysed['native_pipeline_archive']}


def compare_pair(left, right, recipe, context=None):
    if recipe not in RECIPES:
        raise ValueError('Unknown comparison recipe')
    field, baseline, candidate, plan_ids = RECIPES[recipe]
    analyses = [audit(left), audit(right)]
    blockers, warnings = [], []
    metas = [d.get('metadata', {}) for d in (left, right)]
    configs = [m.get('launch_configuration', {}) for m in metas]
    if any(m.get('device_identifier') not in ('iPad16,5', 'iPad16,6') for m in metas):
        blockers.append('Device is not the M4 reference; other hardware needs its own independent profile')
    warnings.append('Matching build stamps are metadata, not independent binary/driver hashes')
    for key in ('build_sha', 'device_identifier', 'os', 'session_id'):
        if any(not isinstance(m.get(key), str) or not m[key] or m[key] == 'UNAVAILABLE' for m in metas):
            blockers.append('Missing identity: ' + key)
        elif key == 'session_id':
            if metas[0][key] == metas[1][key]:
                blockers.append('Same session exported twice')
        elif metas[0][key] != metas[1][key]:
            blockers.append('Different identity: ' + key)
    for key in REQUIRED_CONFIG + (field,):
        if any(key not in c for c in configs):
            blockers.append('Missing launch configuration: ' + key)
    changes = [key for key in sorted(set(configs[0]) | set(configs[1])) if configs[0].get(key) != configs[1].get(key)]
    if configs[0].get(field) != baseline or configs[1].get(field) != candidate:
        blockers.append('Recipe requires baseline/candidate ' + field + '=' + str(baseline) + '/' + str(candidate))
    for key in changes:
        if key != field:
            blockers.append('Additional changed control: ' + key)
    defaults = {'worker_policy': 2, 'submission_mode': 0, 'engine_only_limiter': False,
                'clock_correct_presentation': False, 'metalfx_spatial_requested': False,
                'feedback_clock_correction': False, 'native_pipeline_archive_mode': 0, 'native_archive_verification': False, 'metal_prefill': -1, 'metal_command_buffer_limit': 0, 'initialization_parking': False, 'swapchain_image_budget': 0}
    for index, (data, analysed, config) in enumerate(zip((left, right), analyses, configs)):
        side = 'baseline' if index == 0 else 'candidate'
        blockers.extend(side + ': ' + e for e in analysed['errors'])
        warnings.extend(side + ': ' + w for w in analysed['warnings'])
        summary = data.get('summary', {})
        if config.get('engine') != 'ue4' or 'dungeon' not in str(config.get('game', '')).lower():
            blockers.append(side + ': Dungeons UE4 reference is not selected')
        if not isinstance(data.get('gpu_sampling', {}).get('requested'), bool) or not isinstance(metas[index].get('cpu_thread_sampling_requested'), bool):
            warnings.append(side + ': GPU/thread diagnostic activation is unknown')
        if data.get('schema_version', 0) >= 12:
            for key in ('metal_prefill', 'metal_command_buffer_limit', 'initialization_parking', 'swapchain_image_budget'):
                if key not in config:
                    blockers.append(side + ': missing launch control in schema12: ' + key)
        for key, value in defaults.items():
            if key != field and key in config and config[key] != value:
                blockers.append(side + ': unrelated experimental control enabled: ' + key)
        if summary.get('dropped_frame_intervals_cumulative', 0) or summary.get('frame_distribution_complete') is False:
            blockers.append(side + ': incomplete host-frame distribution')
        if any(summary.get(k, 0) for k in ('dropped_host_records_cumulative', 'dropped_events_cumulative')) or data.get('dropped_export_records', 0):
            warnings.append(side + ': host/event/export losses limit attribution')
        if config.get('requested_fps') != 60 or config.get('launch_width') != 2128 or config.get('launch_height') != 1600:
            blockers.append(side + ': protected M4 reference configuration is not selected')
        if config.get('sharp_graphics') is not True or config.get('efficient_graphics') is not True:
            blockers.append(side + ': Sharp/Efficient reference is not selected')
        if config.get('detailed_driver_profiling') is not False:
            blockers.append(side + ': detailed driver profiling is enabled or unknown')
        for key in ('clock_correct_presentation', 'engine_only_limiter', 'pipeline_identification', 'pipeline_creation_feedback', 'render_target_inventory'):
            if key not in config:
                warnings.append(side + ': launch control unavailable: ' + key)
            elif key != field and config[key] is True:
                warnings.append(side + ': additional experiment/diagnostic enabled: ' + key)
        if analysed['conditions']['battery_states'] != [1]:
            blockers.append(side + ': unplugged battery state not established throughout sampled states')
        samples = [s for s in data.get('samples', []) if s.get('excluded') is False]
        if any(s.get('environment', {}).get('low_power_mode') is True for s in samples):
            blockers.append(side + ': Low Power Mode observed')
        if included_seconds(data) is None or included_seconds(data) < 120:
            blockers.append(side + ': invalid exclusions/duration or less than120 included seconds')
    for key in ('cpu_thread_sampling_requested', 'component_sampling_requested'):
        if metas[0].get(key) != metas[1].get(key):
            blockers.append('Changed diagnostic: ' + key)
    if left.get('gpu_sampling', {}).get('requested') != right.get('gpu_sampling', {}).get('requested'):
        blockers.append('Changed diagnostic: gpu_sampling.requested')
    brightness = [a['conditions']['brightness_values'] for a in analyses]
    if any(not xs or not all(finite(v) for v in xs) for xs in brightness):
        blockers.append('Missing valid brightness samples')
    elif max(v for xs in brightness for v in xs) - min(v for xs in brightness for v in xs) > .001:
        blockers.append('Brightness varies between/within sessions')
    durations = [included_seconds(d) for d in (left, right)]
    if all(durations) and abs(durations[0] - durations[1]) / max(durations) > .1:
        blockers.append('Included session durations differ by more than10%')
    treatment = worker_treatment(right, candidate) if recipe.endswith('worker') else None
    if treatment:
        if not treatment['included_normal_utility_observations'] or not treatment['included_trial_requested_samples']:
            blockers.append('Candidate lacks included extra normal-worker treatment evidence')
        if not treatment['included_admission_counter_increase']:
            warnings.append('No admission counter increase inside capture; lifetime admissions alone cannot pass admission gate')
    if recipe == 'relative-worker':
        warnings.append('Mode4 is a separate treatment; it cannot pass strict Adaptive-versus-Balanced energy gate M7-E1')
    if recipe == 'spatial':
        s = right.get('spatial_upscaling', {})
        if s.get('configured') is not True or not finite(s.get('encoded_calls')) or s['encoded_calls'] <= 0:
            blockers.append('Candidate has no configured/encoded scaler evidence')
        if s.get('failures'):
            blockers.append('Candidate scaler failures were recorded')
        if (s.get('output_width'), s.get('output_height')) != (2128, 1600):
            blockers.append('Candidate does not retain selected spatial output')
        warnings.append('Scaler dimensions/encode counts alone do not establish useful scene identity, colour/lifetime, quality or GPU/energy benefit')
    if recipe == 'native-archive':
        archive = right.get('native_pipeline_archive', {})
        if archive.get('requested') is not True or archive.get('supported') is not True:
            blockers.append('Candidate native archive activation/support not established')
        if not finite(archive.get('restored_bytes')) or archive['restored_bytes'] <= 0:
            blockers.append('Candidate has no persisted native archive restore evidence')
        if not finite(archive.get('archive_attachments')) or archive['archive_attachments'] <= 0:
            blockers.append('Candidate has no native archive attachment evidence')
        builds = [d.get('spatial_upscaling', {}).get('driver_build') for d in (left, right)]
        if not all(isinstance(b, dict) and b.get('native_archive_abi') in (1, 2) for b in builds) or builds[0] != builds[1]:
            blockers.append('Same native experimental driver manifest not established')
        warnings.append('Native attachments/bytes are not cache hits; include separately audited preparation receipt and loading costs in net acceptance')
    if recipe == 'feedback-clock':
        clock = right.get('presentation_clock', {})
        if clock.get('feedback_only_requested') is not True or clock.get('requested') is not False:
            blockers.append('Independent feedback-only runtime treatment not established')
        if not finite(clock.get('feedback_records')) or clock['feedback_records'] <= 0:
            blockers.append('Candidate has no observed presentation feedback to correct')
        if clock.get('invalid_clock_or_overflow') or clock.get('unsupported_chains'):
            blockers.append('Candidate presentation clock/chain errors recorded')
    context = context or {}
    gaps = []
    for key in CONTEXT_FIELDS:
        rows = [context.get(side, {}).get(key) for side in ('baseline', 'candidate')]
        if any(v is None or v == '' for v in rows):
            gaps.append(key)
        elif rows[0] != rows[1]:
            warnings.append('User-supplied condition differs: ' + key)
    clean = all(d.get('gpu_sampling', {}).get('requested') is False and m.get('cpu_thread_sampling_requested') is False
                and m.get('component_sampling_requested', False if d.get('schema_version', 0) < 11 else None) is False
                and all(c.get(k) is False for k in ('detailed_driver_profiling', 'pipeline_identification', 'pipeline_creation_feedback', 'render_target_inventory'))
                for d, m, c in zip((left, right), metas, configs))
    if all(d.get('schema_version', 0) >= 12 for d in (left, right)):
        queues = [d.get('queue_execution_options', {}) for d in (left, right)]
        if any(q.get('actual_configuration_available') is not True for q in queues):
            blockers.append('Actual queue configuration unavailable for schema12 comparison')
        for key, permitted_recipe in [('actual_synchronous_submission', 'async'), ('actual_prefill', 'prefill'), ('actual_command_buffer_limit', 'buffer-limit')]:
            if any(key not in q for q in queues):
                blockers.append('Missing runtime queue field: ' + key)
            elif recipe != permitted_recipe and queues[0][key] != queues[1][key]:
                blockers.append('Additional changed actual queue setting: ' + key)
    if recipe in ('prefill', 'buffer-limit'):
        for side, data, config in zip(('baseline', 'candidate'), (left, right), configs):
            runtime = data.get('queue_execution_options', {})
            if runtime.get('actual_configuration_available') is not True or runtime.get('environment_error') != 0:
                blockers.append(side + ': actual queue configuration unavailable or environment failed')
        actual = right.get('queue_execution_options', {})
        expected = 1 if recipe == 'prefill' else 8
        if actual.get('actual_prefill' if recipe == 'prefill' else 'actual_command_buffer_limit') != expected:
            blockers.append('candidate: requested queue treatment not observed')
        baseline = left.get('queue_execution_options', {})
        if baseline.get('actual_prefill' if recipe == 'prefill' else 'actual_command_buffer_limit') == expected:
            blockers.append('baseline already has selected actual queue treatment; no A/B contrast')
    if recipe == 'swapchain-images':
        for side, data in zip(('baseline', 'candidate'), (left, right)):
            runtime = data.get('swapchain_budget', {})
            if runtime.get('create_result_available') is not True or runtime.get('last_create_result') != 0 or runtime.get('returned_image_count_complete') is not True:
                blockers.append(side + ': complete actual swapchain image count unavailable')
        chosen = right.get('swapchain_budget', {})
        if chosen.get('override_applied') is not True or chosen.get('returned_image_count') != 2:
            blockers.append('candidate: two-image treatment not observed')
        if left.get('swapchain_budget', {}).get('returned_image_count') == 2:
            blockers.append('baseline already uses two images; no actual image-count contrast')
        warnings.append('Swapchain image count does not independently establish Vulkan frames in flight or display latency')
    if recipe == 'initialization-parking':
        info = right.get('initialization_waits', {})
        if info.get('requested') is not True or not finite(info.get('wait_entries_since_launch')) or info['wait_entries_since_launch'] <= 0:
            blockers.append('candidate: no observed parked initialization waits; treatment opportunity unverified')
        warnings.append('Initialization counters are since launch and can include excluded/loading work; compare whole launch and gameplay cost separately')
    metrics = [run_metrics(d, a) for d, a in zip((left, right), analyses)]
    delta = {key: metrics[1][key] - metrics[0][key] for key in ('retained_fps', 'p95_ms', 'p99_ms', 'cpu_weighted_percent_one_core',
               'over20_per1000_host_intervals', 'over33_per1000_host_intervals', 'over50_per1000_host_intervals')
             if finite(metrics[0].get(key)) and finite(metrics[1].get(key))}
    return {'comparison_version': 1, 'recipe': recipe, 'plan_ids': plan_ids,
            'status': 'BLOCKED FOR CONTROLLED INFERENCE' if blockers else 'METADATA PREFLIGHT ONLY; HUMAN/EVIDENCE REVIEW REQUIRED',
            'blockers': sorted(set(blockers)), 'warnings': sorted(set(warnings)), 'changed_launch_fields': changes,
            'baseline': metrics[0], 'candidate': metrics[1], 'candidate_minus_baseline': delta,
            'worker_treatment': treatment, 'detailed_diagnostics_off_both': clean,
            'user_supplied_context': context, 'unrecorded_context': gaps,
            'context_provenance': 'User supplied, not independently measured or verified by this tool',
            'power_watts': None, 'physical_temperature_c': None, 'displayed_frames': None,
            'energy_improvement': 'UNVERIFIED', 'roadmap_gates_automatically_passed': [],
            'limitations': ['One pair is descriptive; repeat important small effects at least3 times with matched conditions.',
                           'Full-session percentiles cannot be averaged into pooled percentiles or establish causality.',
                           'GPU sampled unions and overlapping work durations are not GPU utilisation or whole-session execution.',
                           'Unplugged flat/coarse battery readings are not zero watts or precise electrical savings.',
                           'Independent monitoring-off traces, physical correctness/quality and supported power/temperature evidence remain external/reviewed tasks.']}


def external_pair_audit(left, right, baseline, candidate, diagnostic_hashes):
    """Attach supplied electrical/surface evidence, with strict identity and coverage checks.

    This is descriptive one-pair arithmetic, never an automatic causal/gate decision.
    """
    from external_efficiency import identity, SCHEMA
    blockers, warnings = [], []
    results = (baseline, candidate)
    for side, data, result, sha in zip(('baseline', 'candidate'), (left, right), results, diagnostic_hashes):
        if result.get('schema') != SCHEMA or result.get('identity') != identity(data):
            blockers.append(side + ': external analysis identity/schema mismatch')
        if result.get('inputs_sha256', {}).get('diagnostics') != sha:
            blockers.append(side + ': external analysis does not hash this diagnostic file')
        if result.get('conditions', {}).get('charging_state') != 'unplugged':
            blockers.append(side + ': external electrical session is not unplugged')
        cover = result.get('power_coverage_fraction')
        if not finite(cover) or not .99 <= cover <= 1.000000001:
            blockers.append(side + ': external power covers less than99% of included intervals')
        power = result.get('power', {}).get('average_watts')
        if not finite(power) or power < 0:
            blockers.append(side + ': valid average external system power unavailable')
        if result.get('provenance', {}).get('power', {}).get('quantity') != 'whole_device_system_power':
            blockers.append(side + ': external power quantity is not whole-device system power')
        if result.get('configuration') != data.get('metadata', {}).get('launch_configuration', {}):
            blockers.append(side + ': external analysis configuration mismatch')
    for key in ('route', 'cache_state', 'brightness', 'case_accessories', 'starting_temperature', 'ambient_conditions'):
        values = [r.get('conditions', {}).get(key) for r in results]
        if any(v is None or v == '' for v in values) or values[0] != values[1]:
            blockers.append('External condition missing or different: ' + key)
    for key in ('power', 'temperature', 'displayed_frames'):
        provenance = [r.get('provenance', {}).get(key) for r in results]
        if provenance[0] != provenance[1]:
            # Raw source references should differ, but measurement methodology must match.
            methods = [{k: v for k, v in (p or {}).items() if k not in ('raw_source_reference', 'coverage_seconds')} for p in provenance]
            if methods[0] != methods[1]:
                blockers.append('External instrument/method differs: ' + key)
    durations = [r.get('power_covered_seconds') for r in results]
    if any(not finite(x) or x <= 0 for x in durations) or max(durations) > min(durations) * 1.1:
        blockers.append('External covered durations invalid or differ by more than10%')
    if baseline.get('alignment') != candidate.get('alignment'):
        warnings.append('Clock alignment differs; review whole-period uncertainty, clipping and exclusions')
    delta = {}
    for output, section, field in [('average_watts', 'power', 'average_watts'),
                                   ('max_sampled_surface_above_ambient_c', 'temperature', 'max_surface_above_ambient_c'),
                                   ('joules_per_displayed_frame', 'displayed_frames', 'energy_per_displayed_frame_joules')]:
        a, b = (r.get(section, {}).get(field) for r in results)
        if finite(a) and finite(b):
            delta[output] = b - a
    a, b = (r.get('power', {}).get('average_watts') for r in results)
    if finite(a) and finite(b) and a > 0:
        delta['average_watts_relative_change_percent'] = (b - a) / a * 100
    return {'status': 'BLOCKED FOR CONTROLLED INFERENCE' if blockers else 'DESCRIPTIVE EXTERNAL PAIR; REVIEW REPEATS AND CORRECTNESS',
            'blockers': sorted(set(blockers)), 'warnings': warnings, 'candidate_minus_baseline': delta,
            'energy_improvement': 'UNVERIFIED: inspect main preflight, matched visual/pacing correctness, instrument accuracy and at least3 repeats for small effects',
            'roadmap_gates_automatically_passed': [],
            'scope': 'Supplied whole-device electrical/surface evidence; no automatic app attribution or causal benefit claim'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('baseline', type=Path)
    p.add_argument('candidate', type=Path)
    p.add_argument('--recipe', choices=RECIPES, required=True)
    p.add_argument('--context', type=Path, help='Optional user-reported matched conditions; never taken as direct telemetry')
    p.add_argument('--output', type=Path)
    p.add_argument('--external-baseline', type=Path, help='Optional normalized external analysis for exact baseline diagnostic file')
    p.add_argument('--external-candidate', type=Path, help='Required together with --external-baseline')
    args = p.parse_args()
    inputs = [x.resolve() for x in (args.baseline, args.candidate, args.context, args.external_baseline, args.external_candidate) if x]
    if args.output and args.output.resolve() in inputs:
        p.error('Output must not overwrite input evidence')
    left, lp = load_export(args.baseline)
    right, rp = load_export(args.candidate)
    result = compare_pair(left, right, args.recipe, json.loads(args.context.read_text()) if args.context else None)
    result['inputs'] = {'baseline': lp, 'candidate': rp}
    if bool(args.external_baseline) != bool(args.external_candidate):
        p.error('External comparison requires both baseline and candidate analyses')
    if args.external_baseline:
        from external_efficiency import load_bytes, read_json
        eraw = [load_bytes(x) for x in (args.external_baseline, args.external_candidate)]
        result['external_measurements'] = external_pair_audit(left, right, *(read_json(x) for x in eraw),
                                                            [lp['decoded_sha256'], rp['decoded_sha256']])
        result['external_measurements']['analysis_files_sha256'] = [hashlib.sha256(x).hexdigest() for x in eraw]
        if result['external_measurements']['blockers']:
            result['status'] = 'BLOCKED FOR CONTROLLED INFERENCE'
    payload = json.dumps(result, indent=2, allow_nan=False) + '\n'
    if args.output:
        args.output.write_text(payload)
    else:
        print(payload, end='')


if __name__ == '__main__':
    main()
