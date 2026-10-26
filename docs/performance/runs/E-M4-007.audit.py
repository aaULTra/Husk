#!/usr/bin/env python3
"""Reproduce this archived pair's descriptive evidence; never grant energy gates."""
import collections
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'scripts'))
from compare_efficiency import compare_pair, included_point, load_export


def thread_costs(data):
    previous = None
    costs = {}
    snapshots = []
    for sample in data['samples']:
        if sample['excluded']:
            previous = None
            continue
        snapshot = sample.get('cpu_threads')
        if not snapshot or snapshot['mach_result'] != 0:
            continue
        snapshots.append({k: snapshot[k] for k in ('returned', 'failures', 'truncated')})
        rows = {r['thread_id']: r for r in snapshot['threads']}
        if previous:
            old_t, old_rows = previous
            elapsed = sample['t'] - old_t
            for key in rows.keys() & old_rows.keys():
                row, old = rows[key], old_rows[key]
                delta = row['user_seconds'] + row['system_seconds'] - old['user_seconds'] - old['system_seconds']
                if elapsed > 0 and math.isfinite(delta) and delta >= 0:
                    cost = costs.setdefault(key, {'thread_id': key, 'name': row['name'], 'cpu_seconds': 0., 'observed_seconds': 0.})
                    cost['cpu_seconds'] += delta
                    cost['observed_seconds'] += elapsed
        previous = sample['t'], rows
    rows = sorted(costs.values(), key=lambda row: -row['cpu_seconds'])
    for row in rows:
        row['cpu_percent_one_core'] = 100 * row['cpu_seconds'] / row['observed_seconds']
    normal = [r for r in rows if r['name'].startswith('TaskGraphNP')]
    total = sum(r['cpu_seconds'] for r in rows)
    return {'method': 'Cumulative user+system deltas for intersecting Mach thread identities; reset at excluded samples. Missing/exited threads omitted.',
            'included_snapshot_count': len(snapshots), 'snapshots': snapshots, 'threads': rows,
            'normal_workers': normal, 'normal_worker_sum_percent_one_core': sum(r['cpu_percent_one_core'] for r in normal),
            'normal_worker_percent_of_matched_thread_cpu': 100 * sum(r['cpu_seconds'] for r in normal) / total if total else None,
            'scope': 'Observed process-thread CPU only, including host; individual coverage varies. Names do not prove roles or P/E residency; these percentages are not energy shares.'}


def native_feedback(data):
    exclusions = [(r['gpu_media_start_before_seconds'], r['gpu_media_end_after_seconds']) for r in data['exclusions']]
    rows = data['presentation_clock']['feedback_last256']
    def included(row):
        actual, observed = row['raw_native_actual_ns']/1e9, row['observed_media_ns']/1e9
        return 0 < actual <= observed and all(not (a <= actual <= b or a <= observed <= b) for a, b in exclusions)
    diffs = []
    for a, b in zip(rows, rows[1:]):
        if included(a) and included(b) and b['sequence'] == a['sequence'] + 1 and b['present_id'] == (a['present_id'] + 1) % 2**32:
            delta = (b['raw_native_actual_ns'] - a['raw_native_actual_ns'])/1e6
            if delta > 0:
                diffs.append(delta)
    ordered = sorted(diffs)
    return {'status': 'MEASURED native feedback; source may be driver-estimated, local tail only',
            'method': 'Consecutive retained sequence/present IDs; raw actual and observation media timestamps both outside conservative direct exclusion brackets.',
            'retained_records': len(rows), 'included_consecutive_intervals': len(diffs),
            'total_interval_span_seconds': sum(diffs)/1000,
            'nearest_rank_p50_ms': ordered[math.ceil(.5*len(ordered))-1] if ordered else None,
            'nearest_rank_p95_ms': ordered[math.ceil(.95*len(ordered))-1] if ordered else None,
            'worst_ms': max(diffs) if diffs else None,
            'rounded_interval_counts_ms': dict(collections.Counter(round(x, 2) for x in diffs)),
            'scope': 'Last256 overwrite ring, not full-session displayed frames. Driver source estimation and actual display refresh/GPU cause remain unverified; never calculate energy per displayed frame from this subset.'}


def extra(data):
    s, work = data['summary'], data['submit_cpu_work']
    ns = work['thread_cpu_ns']
    windows = data['windows']
    caps = [tuple(map(int, m)) for e in data['events'] for m in re.findall(r'engine cap (\d+), host cap (\d+)', e.get('detail', ''))]
    return {'runtime_engine_host_caps': sorted(set(caps)),
            'process_cpu_max_percent_one_core': max(r.get('process_cpu_percent_one_core') or 0 for r in data['samples']),
            'largest_observed_footprint_bytes': max(r.get('footprint_bytes') or 0 for r in data['samples']),
            'host_sleep_seconds': s['host_ns'][3]/1e9, 'host_sleep_calls': s['host_calls'][3],
            'submit_cpu_seconds': ns/1e9, 'submit_wall_seconds': work['wall_ns']/1e9,
            'submit_cpu_per_call_ms': ns/work['calls']/1e6,
            'submit_cpu_per_host_interval_ms': ns/s['interval_count']/1e6,
            'submit_cpu_fraction_of_caller_wall': ns/work['wall_ns'],
            'submit_scope': 'Wall can overlap, wait, deschedule or include work elsewhere; its non-caller-CPU portion is not measured GPU execution.',
            'graphics_creation_total_ms': s['host_ns'][4]/1e6, 'graphics_creation_calls': s['host_calls'][4],
            'no_pipeline_windows': [{k: w[k] for k in ('start','end','interval_count','host_cadence_fps','p95_ms','worst_ms')} for w in windows if w['host_calls'][4] == 0 and w['interval_count'] >= 100],
            'pipeline_events': [{'occurred_t': e.get('occurred_t'), 'recorded_t': e.get('recorded_t'),
                                 'occurrence_included': included_point(data, e.get('occurred_t')), 'detail': e['detail']}
                                for e in data['events'] if e.get('subsystem') == 'pipeline'],
            'battery_samples': [{k: r[k] for k in ('t','excluded','battery_fraction','battery_state')} for r in data['samples'] if 'battery_fraction' in r],
            'battery_scope': 'A flat40% is unresolved. B one40->35% step cannot establish sustained79.65pp/hour or a causal energy difference.',
            'threads': thread_costs(data), 'native_feedback': native_feedback(data)}


def main():
    here = Path(__file__).parent
    inputs, provenance, data = {}, json.loads((here/'E-M4-007.provenance.json').read_text()), []
    for side in ['A','B']:
        path = here/f'E-M4-007{side}.diagnostics.json.gz'
        raw = gzip.decompress(path.read_bytes())
        report = (here/f'E-M4-007{side}.report.md').read_bytes()
        p = provenance[side]
        assert hashlib.sha256(raw).hexdigest() == p['raw_sha256']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == p['gzip_sha256']
        assert hashlib.sha256(report).hexdigest() == p['report_sha256']
        d, source = load_export(path)
        source['path'] = str(path.relative_to(ROOT))
        inputs[side] = source
        text = report.decode()
        assert ('Build: '+d['metadata']['build_sha']) in text
        for pattern, expected in [(r'MEASURED host cadence: ([\d.]+)',d['summary']['host_cadence_fps']),
                                  (r'MEASURED worst interval: ([\d.]+)',d['summary']['worst_ms']),
                                  (r'Slow pipeline calls: (\d+)',d['summary']['slow_pipeline_calls'])]:
            assert math.isclose(float(re.search(pattern,text)[1]),expected,abs_tol=1e-6)
        data.append(d)
    result = {'evidence_id':'E-M4-007','audit_version':1,'inputs':inputs,'reports_reconcile':True,
              'comparison':compare_pair(*data,'engine-only'),'A':extra(data[0]),'B':extra(data[1]),
              'roadmap_gates_automatically_passed':[],'energy_improvement':'UNVERIFIED'}
    (here/'E-M4-007.audit.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print('E-M4-007 hashes, report/JSON arithmetic and paired audits verified; no inferred energy benefit.')


if __name__ == '__main__':
    main()
