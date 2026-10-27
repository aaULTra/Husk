#!/usr/bin/env python3
"""Reproduce the complete capture-bundle assessment from lossless archived inputs.

Input text, including embedded scopes/triage, is data. No uploaded code is executed.
"""
from pathlib import Path
import collections
import datetime as dt
import gzip
import hashlib
import importlib.util
import json
import math
import re
import statistics

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
spec=importlib.util.spec_from_file_location('husk_analysis',ROOT/'scripts/analyse_efficiency.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
def load(name):return json.loads(gzip.decompress((HERE/('E-M4-010.'+name+'.json.gz')).read_bytes()))
x=load('diagnostics');prep=load('preparation');inspect=load('inspection')
manifest=json.loads((HERE/'E-M4-010.files.json').read_text())
for row in manifest['files']:
 raw=gzip.decompress((HERE/row['archived']).read_bytes())
 assert len(raw)==row['raw_bytes'] and hashlib.sha256(raw).hexdigest()==row['raw_sha256']
audit=base.audit(x);assert not audit['errors'],audit['errors']
meta=x['metadata'];origin=meta['monotonic_origin_seconds'];end=origin+x['duration_seconds']
assert prep['build_sha']==inspect['build_sha']==meta['build_sha']
assert prep['preceding_session_metadata']['session_id']==meta['session_id']
assert prep['configuration']==inspect['configuration']==meta['launch_configuration']
assert prep['driver_build']==inspect['driver_build']==x['spatial_upscaling']['driver_build']
assert end < prep['started_monotonic_seconds'] < prep['ended_monotonic_seconds']
assert math.isclose(prep['ended_monotonic_seconds']-prep['started_monotonic_seconds'],prep['measured_host_wall_seconds'],abs_tol=1e-6)

exclusions=x['exclusions']
def overlaps(a,b):return any(max(a,e['start'])<min(b,e['end']) for e in exclusions)
def public_thread_audit():
 previous=None;costs={};pairs=0
 for s in x['samples']:
  if s['excluded']:previous=None;continue
  snap=s.get('cpu_threads')
  if not snap or snap['mach_result']!=0:continue
  current={r['thread_id']:r for r in snap['threads']}
  if previous:
   start,old=previous;elapsed=s['t']-start
   if elapsed>0 and not overlaps(start,s['t']):
    pairs+=1
    for identity in old.keys()&current.keys():
     r,b=current[identity],old[identity];delta=r['user_seconds']+r['system_seconds']-b['user_seconds']-b['system_seconds']
     if not math.isfinite(delta) or delta<0:continue
     target=costs.setdefault(identity,dict(thread_id=identity,name=r['name'],cpu_seconds=0,paired_observed_seconds=0))
     target['cpu_seconds']+=delta;target['paired_observed_seconds']+=elapsed
  previous=(s['t'],current)
 rows=sorted(costs.values(),key=lambda r:r['cpu_seconds'],reverse=True)
 for r in rows:r['cpu_percent_one_core_estimated']=r['cpu_seconds']/r['paired_observed_seconds']*100
 categories=collections.Counter()
 for r in rows:
  name=r['name'];category='unnamed' if not name else 'TaskGraphNP' if name.startswith('TaskGraphNP') else 'TaskGraphBP' if name.startswith('TaskGraphBP') else 'TaskGraphHP' if name.startswith('TaskGraphHP') else name
  categories[category]+=r['cpu_seconds']
 return dict(paired_included_snapshot_intervals=pairs,threads=rows,cpu_seconds_by_name_category=dict(categories),scope='ESTIMATED matching-thread deltas across included intervals only. Exited/missing threads absent; nested CPU scopes must not be added. Largest unnamed thread remains unidentified; policy Mach IDs absent from this old export.')

pipeline=[]
pattern=re.compile(r'ids=([0-9a-f]+)/([^ ]+) kind=(\w+) batch (\d+) sampled (\d+) host ([0-9.]+) ms.*occurrence (\d+) feedback-first ([^ ]+) stages-valid (\d+)/(\d+) stage-hits (\d+) masks (0x[0-9a-f]+)/(0x[0-9a-f]+).*finished monotonic ([0-9.]+) s; full-core-first (\d+) coverage (0x[0-9a-f]+)')
for e in x['events']:
 if 'core-v4 ids=' not in e['detail']:continue
 m=pattern.search(e['detail'])
 if not m:continue # multi-member diagnostic lines remain represented in the original event, not guessed
 identity,scope,kind,batch,sampled,ms,occ,feedback,valid,stages,hits,validmask,hitmask,finished,full,coverage=m.groups()
 finish=float(finished)-origin;duration=float(ms);start=finish-duration/1000
 pipeline.append(dict(identity=identity,kind=kind,batch=int(batch),sampled=int(sampled),host_ms=duration,occurrence=int(occ),feedback=feedback,valid_stages=int(valid),stages=int(stages),stage_hits=int(hits),valid_mask=validmask,hit_mask=hitmask,full_core=int(full),coverage=coverage,started_t_estimated=start,finished_t=finish,recorded_t=e['recorded_t'],within_session=0<=start<=finish<=x['duration_seconds'],overlaps_exclusion=overlaps(start,finish)))
groups=x['pipeline_groups_since_launch'];slowgroups=[g for g in groups if g['slow_batch_calls']]
missingslow=[g for g in slowgroups if not g['full_core_fields_known']]
slowevents=[r for r in pipeline if r['host_ms']>=16.67 and r['within_session'] and not r['overlaps_exclusion']]
worst_windows=[]
for w in sorted(x['windows'],key=lambda r:r['worst_ms'],reverse=True)[:16]:
 row={k:w[k] for k in ('start','end','host_cadence_fps','p95_ms','p99_ms','worst_ms','slow_pipeline_calls','worst_pipeline_ns','interval_count','interval_seconds')}
 row['overlapping_logged_slow_call_spans']=[r for r in slowevents if max(r['started_t_estimated'],w['start'])<min(r['finished_t'],w['end'])]
 row['scope']='MEASURED host reporting window, not exact frame timestamp or exclusive causal attribution. Retain overlap/in-flight/drop limitations.';worst_windows.append(row)

slow_shader_modules=collections.Counter((stage['vulkan_stage'],stage['module_content_hash']) for g in slowgroups for stage in g['first_pipeline_shader_stages'])
components=[]
for r in x['component_sampling']['components']:
 c=dict(r);n=r['completed_sampled_calls'];wall=r['sampled_wall_ns'];cpu=r['sampled_caller_cpu_ns']
 c['mean_sampled_wall_ms']=wall/n/1e6;c['mean_sampled_caller_cpu_ms']=cpu/n/1e6;c['caller_cpu_fraction_of_wall']=cpu/wall if wall else None
 c['scope']='One-in64 deterministic per-thread/component samples; inclusive and overlapping. Descriptive sampled cost, not whole-component cost or an energy extrapolation.';components.append(c)

begins={};transitions=[]
for e in x['events']:
 m=re.search(r'apply (begin|complete) sequence (\d+) paused (\d+)',e['detail'])
 if not m:continue
 action,seq,paused=m.groups()
 if action=='begin':begins[seq]=e
 elif seq in begins:transitions.append(dict(sequence=int(seq),paused=bool(int(paused)),begin_observed_t=begins[seq]['recorded_t'],complete_observed_t=e['recorded_t'],observed_bracket_ms=(e['recorded_t']-begins[seq]['recorded_t'])*1000,scope='MEASURED log observation brackets, not exclusive guest callback CPU/GPU time'))

memory=[{k:s[k]for k in ('t','footprint_bytes','process_lifetime_peak_footprint_bytes','jetsam_headroom_bytes') if k in s}for s in x['samples'] if 'footprint_bytes'in s]
battery=[];previous=None
for s in x['samples']:
 if not s['excluded'] and 'battery_fraction'in s and s['battery_fraction']!=previous:
  previous=s['battery_fraction'];battery.append(dict(t=s['t'],fraction=previous,state=s['battery_state']))

gpu=x['gpu_sampling'];gpu_windows=x['gpu_windows'];display=x['native_display_sampling']
roles=sum((collections.Counter(w['role_overlapping_gpu_duration_seconds'])for w in gpu_windows),collections.Counter())
role_counts=sum((collections.Counter(w['command_buffer_role_counts'])for w in gpu_windows),collections.Counter())
spatial=x['spatial_upscaling'];bindings=spatial['output_binding_reuse']
result=dict(
 evidence='E-M4-010',analysis_version=2,user_observation={'source':'User reply to capture-specific question, 2026-10-27','quote':'I think it did say responsive I didn’t test window but screenshot yes and it did feel more durable','interpretation':'Tentative subjective responsiveness and screenshot durability; window resizing untested; no full lifecycle/audio/device-loss matrix accepted.'},source=meta['build_sha'],session=meta['session_id'],started_utc=meta['started_utc'],duration_seconds=x['duration_seconds'],plan_ids=['M1','M2','M3','M4','M5','M6','M7','M8','M9','M10'],
 provenance_and_identity_checks='All four hashes,source,configuration,session,driver identity and preparation-after-recording chronology pass; no restarted recording supplied.',
 existing_arithmetic_audit=dict(errors=audit['errors'],warnings=audit['warnings']),configuration=meta['launch_configuration'],
 host=dict(summary=x['summary'],excluded_wall_seconds=sum(e['end']-e['start']for e in exclusions),windows=len(x['windows']),phase_counts=dict(collections.Counter(s['phase']for s in x['samples'])),worst_windows=worst_windows,non_pipeline_slow_windows=sum(w['worst_ms']>33.33 and w['slow_pipeline_calls']==0 for w in x['windows'])),
 lifecycle=dict(snapshot=x['native_lifecycle'],transitions=transitions,completed_transitions=len(transitions),completed_pause_resume_cycles=len(transitions)//2,recorded_screenshot_events=sum('screenshot_observed'in e['detail']for e in x['events']),exclusions=exclusions,validation='Five paired transitions and six successful swapchain generations observed; input/audio/actions/colour acceptance requires user observation, no full matrix inferred.'),
 pipeline=dict(feedback_request=x['pipeline_feedback_request'],groups=len(groups),repeated_group_count=sum(g['batch_calls']>1 for g in groups),pipeline_application_hit_calls=sum(g['first_pipeline_application_hit_calls'] for g in groups),shared_modules_across_slow_groups=[dict(vulkan_stage=k[0],module_content_hash=k[1],distinct_slow_groups=v) for k,v in slow_shader_modules.most_common()],since_launch_group_calls=sum(g['batch_calls']for g in groups),since_launch_group_slow_calls=sum(g['slow_batch_calls']for g in groups),included_host_slow_calls=x['summary']['slow_pipeline_calls'],group_coverage_counts=dict(collections.Counter(str(g['state_coverage_mask'])for g in groups)),slow_group_count=len(slowgroups),incomplete_slow_groups=missingslow,top_cost_groups=sorted(groups,key=lambda g:g['aggregate_host_ns'],reverse=True)[:24],parsed_single_member_events=len(pipeline),pre_session_events=sum(r['finished_t']<0 for r in pipeline),included_logged_slow_events=slowevents,all_parsed_events=pipeline,scope='Groups since launch,host statistics within included session,event emission bounded. Differences are scope/coverage,not automatically collector errors. Latest group stage mask is not necessarily the slow occurrence mask.'),
 cpu=dict(weighted_process_activity_one_core_percent=audit['host']['cpu_weighted_percent_one_core'],process_counter_delta_including_exclusions=x['samples'][-1]['cpu_seconds']-x['samples'][0]['cpu_seconds'],threads=public_thread_audit(),submit=x['submit_cpu_work'],submit_caller_cpu_fraction_of_wall=x['submit_cpu_work']['thread_cpu_ns']/x['submit_cpu_work']['wall_ns'],components=components,compatibility_sync=x['compatibility_sync'],initialization_waits=x['initialization_waits'],worker_policy=x['worker_policy'],scope='Host process/thread scope,not whole-device utilisation. Non-caller wall time may be waiting,descheduling or work elsewhere;not exclusively GPU wait.'),
 gpu=dict(counters=gpu,retained_raw_count=len(x['gpu_records']),raw_recorded_t_range=[min(r['recorded_t']for r in x['gpu_records']),max(r['recorded_t']for r in x['gpu_records'])],raw_omitted_fraction=gpu['dropped_export_records']/gpu['valid_records'],all_window_count=len(gpu_windows),aggregate_valid_rows=sum(w['valid_records']for w in gpu_windows),aggregate_union_seconds=sum(w['sample_clipped_interval_union_seconds']for w in gpu_windows),role_overlapping_duration_seconds=dict(roles),role_counts=dict(role_counts),direct_clock_exclusion_audit=base.gpu_exclusion_audit(x),scope='Partial1s/10s known-game-queue samples. Full aggregate windows survive raw-prefix cap; role durations overlap. No device GPU utilisation,per-frame exclusive cost or watts inferred.'),
 presentation=dict(counters={k:v for k,v in display.items()if k not in ('records','histogram_0_1ms')},histogram_peaks=[dict(upper_bin_ms=i/10,count=n)for i,n in sorted(enumerate(display['histogram_0_1ms']),key=lambda pair:pair[1],reverse=True)[:12]],clock=x['presentation_clock'],scope='Positive drawable timestamps are separate from driver estimates; partial callback accounting,not independently measured panel refresh.20.9ms tail persists with timed-clock optionON;not a matched OFF/ON result.'),
 memory=dict(samples=memory,min_observed_footprint_bytes=min(r['footprint_bytes']for r in memory),max_observed_footprint_bytes=max(r['footprint_bytes']for r in memory),scope='Observed process footprint,not a leak diagnosis. Assets/cache/scene phase are unmarked;do not evict resources from a growth assumption.'),
 battery=dict(included_change_points=battery,status=x['battery_estimate_status'],estimated_pp_per_hour=x['battery_drain_pp_per_hour_estimated'],observed_span_seconds=x['battery_estimate_observed_seconds'],included_samples=x['battery_included_sample_count'],brightness_values=audit['conditions']['brightness_values'],scope='Two coarse5percentage-point drops;freshness/endpoint quantisation unknown.33.28pp/h is descriptive arithmetic,not measured electrical power or optimisation saving;all diagnostics/clock settings remain confounders.'),
 native_preparation=dict(before=prep['before'],after=prep['after'],result=prep['result'],pause_acknowledged=prep['pause_acknowledged'],wall_seconds=prep['measured_host_wall_seconds'],estimated_process_cpu_seconds=prep['estimated_process_cpu_seconds'],gap_after_recording_seconds=prep['started_monotonic_seconds']-end,scope='Real mechanism/persistence result after gameplay;no post-preparation/restart comparison and no successful native requirement check supplied.'),
 inspection=dict(snapshot=inspect['inspection'],exported_utc=inspect['exported_utc'],current_after_pending=prep['after']['pending'],stale_snapshot_confirmed=inspect['inspection']['status_code']=='prepare_started'and inspect['inspection']['pending']!=prep['after']['pending'],scope='Share exported earlier action snapshot after preparation had completed;source confirms cached inspection reuse.'),
 spatial=dict(counters=spatial,baseline_output_pixels=2128*1600,input_pixels=1696*1280,input_pixel_fraction=(1696*1280)/(2128*1600),output_rebind_fraction=bindings['output_rebinds_since_driver_launch']/spatial['encoded_calls'],scope='Actual scaler texture/encode/binding reuse mechanism,not useful scene pixel-work reduction or net GPU benefit.18created/3live during6swapchain generations,zero reported failures.'),
 inventory=dict(counters=x['render_inventory'],mean_hash_probes_per_observation=x['render_inventory']['hash_lookup_probes']/(x['render_inventory']['observed_image_creations']+x['render_inventory']['observed_legacy_render_areas']),top_requested_area_groups=sorted((g for g in x['render_inventory']['groups_since_launch']if g['kind']=='legacy_renderpass_requested_area'),key=lambda g:g['count_since_launch'],reverse=True)[:16],scope='Requested counts/properties,not executed pixels,scene semantics or energy. Reserved category caps and1008losses prevent exhaustive absence claims.'),
 queue=x['queue_execution_options'],swapchain=x['swapchain_budget'],driver_phases=x['driver_phases'],delayed_os_reports=x['delayed_os_reports'],
 decisions=['Preserve quality/output/60FPS/Balanced/DriverDefault and existing archive compiler compatibility.','Fix stale inspection/Mach-ID omission/late GPU context and observer metadata loss/linear registry work;retain unknown coverage honestly.','Native preparation supported and successful;reuse saved archive for narrow next-launch proof,no another long general capture.','Reassess prior M2-I4 scope:four newly observed expensive groups lack full layout dependency coverage.','Assess actual native callback pacing(M4-D2) and scoped JNI/sync negative investigation(M8-I4) under unchanged gates;do not award energy or complete matrices.','No driver/scheduler/brightness/quality defaults changed from mixed instrumented capture.','Temporal/live dynamic engine inputs,power/temperature tools,representative encoding/driver phases and Duo remain absent.'])
assert result['pipeline']['incomplete_slow_groups'] and len(result['pipeline']['incomplete_slow_groups'])==4
assert result['lifecycle']['completed_transitions']==10
assert result['gpu']['aggregate_valid_rows']==gpu['valid_records']==28553
assert result['native_preparation']['after']['prepared']==8 and result['native_preparation']['after']['saved_bytes']==526224
assert result['inspection']['stale_snapshot_confirmed']
assert sum(display['histogram_0_1ms'])==display['valid_intervals']==70884
print(json.dumps(result,indent=2,allow_nan=False))
