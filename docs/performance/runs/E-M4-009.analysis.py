#!/usr/bin/env python3
"""Reproduce single-gameplay-log analysis; ignore replay and avoid mirrored duplicates."""
from pathlib import Path
import collections
import gzip
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parent
raw = gzip.decompress((ROOT/'E-M4-009.husk-prev.log.gz').read_bytes())
lines = [line for line in raw.decode().splitlines() if '[prev]' not in line]
pattern = re.compile(r'ids=([0-9a-f]+)/([^ ]+) kind=(\w+) batch (\d+) sampled (\d+) host ([0-9.]+) ms.*occurrence (\d+) feedback-first ([^ ]+) stages-valid (\d+)/(\d+) stage-hits (\d+) masks (0x[0-9a-f]+)/(0x[0-9a-f]+).*finished monotonic ([0-9.]+) s; full-core-first (\d+) coverage (0x[0-9a-f]+)')
rows = []
for number, line in enumerate(lines, 1):
    if 'core-v4 ids=' not in line:
        continue
    m = pattern.search(line)
    if not m:
        raise ValueError('Unparsed identity line: '+line)
    identity,scope,kind,batch,sampled,ms,occ,feedback,valid,stages,hits,valid_mask,hit_mask,t,full,coverage = m.groups()
    rows.append(dict(identity=identity,scope=scope,kind=kind,batch=int(batch),sampled=int(sampled),host_ms=float(ms),occurrence=int(occ),feedback=feedback,stages=int(stages),stages_valid=int(valid),stage_hits=int(hits),stage_valid_mask=valid_mask,stage_hit_mask=hit_mask,finished_monotonic_seconds=float(t),full_core=int(full),coverage=coverage,filtered_line_number=number))
slow = [r for r in rows if r['host_ms'] >= 16.67]
report = {
    'schema':1,'evidence':'E-M4-009','plan_ids':['M1','M2','M6','M9'],
    'source':'e9835d95ec530da3efd515ac298200b6d386f46e-dirty',
    'input':'E-M4-009.husk-prev.log.gz','uncompressed_sha256':hashlib.sha256(raw).hexdigest(),
    'analysis_scope':'Single main gameplay log, [prev] removed; native mirrored copy deliberately not added. Filtered line numbers count non-replay nonempty and empty physical lines as decoded splitlines.',
    'identity_rows':len(rows),'coverage_rows':dict(collections.Counter(r['coverage'] for r in rows)),
    'feedback_rows':dict(collections.Counter(r['feedback'] for r in rows)),
    'stage_feedback_rows':dict(collections.Counter(str(r['stages_valid'])+'/'+str(r['stages'])+' valid, '+str(r['stage_hits'])+' hits' for r in rows)),
    'slow_threshold_ms':16.67,'identified_slow_rows':slow,
    'identified_slow_coverage_sufficient':bool(slow) and all(r['full_core']==1 and r['coverage']=='0x1f' and r['batch']==r['sampled']==1 for r in slow),
    'drop_reports':[l for l in lines if 'unavailable/dropped' in l],
    'lifecycle_tail':[l for l in lines if 'ue4: pausing' in l or 'ue4: resuming' in l],
    'fatal_records':[l for l in lines if 'FATAL SIGNAL' in l or '=== CRASH:' in l or '=== FATAL signal' in l or 'uncaught exception:' in l],
    'warning_and_frame_context':[l for l in lines if 'expansion file (OBB) is missing' in l or 'main.42.' in l or 'invalid mode' in l]+lines[-9:],
    'limitations':['Only identified emitted calls assessed;34 incomplete identity records and bounded event drops remain.','Core coverage describes diagnostic discrimination, not complete replay or compilation recipes.','Valid stage hits do not attribute persisted seed reuse or prove cheap pipeline creation.','No phase-correlated first/repeat/restart campaign, whole-pipeline hit or energy benefit established.','No OS/host termination cause recorded.']}
assert report['identity_rows']==346 and len(slow)==9 and report['identified_slow_coverage_sufficient']
assert not report['fatal_records']
print(json.dumps(report,indent=2)+'\n',end='')
