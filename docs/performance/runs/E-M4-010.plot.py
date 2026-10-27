#!/usr/bin/env python3
"""Standalone figure from original E-M4-010 observations; no image modification."""
from pathlib import Path
import gzip,json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
H=Path(__file__).resolve().parent
x=json.loads(gzip.decompress((H/'E-M4-010.diagnostics.json.gz').read_bytes()))
a=json.loads((H/'E-M4-010.analysis.json').read_text())
plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False})
f,axs=plt.subplots(5,1,figsize=(12,13),sharex=True,layout='constrained')
f.suptitle('Husk / Dungeons — E-M4-010: 21.6-minute M4 capture\n395ec7c-dirty · instrumented observation, not a controlled energy comparison',fontsize=14)
w=x['windows'];t=[(r['start']+r['end'])/120 for r in w]
axs[0].plot(t,[r['host_cadence_fps']for r in w],label='Host cadence',color='#166678');axs[0].axhline(60,color='gray',ls='--',lw=.7);axs[0].set_ylabel('Host FPS');axs[0].legend(loc='lower right')
axs[1].plot(t,[r['p95_ms']for r in w],label='Host p95',color='#166678')
axs[1].scatter(t,[r['worst_ms']for r in w],s=12,label='Worst retained interval',color='#bd483a')
e=a['pipeline']['included_logged_slow_events'];axs[1].scatter([r['finished_t']/60 for r in e],[r['host_ms']for r in e],marker='x',s=16,label='Logged slow pipeline call',color='#654d91');axs[1].set_yscale('log');axs[1].set_ylabel('Milliseconds (log)');axs[1].legend(ncol=3,fontsize=8)
s=[r for r in x['samples']if 'process_cpu_percent_one_core'in r];axs[2].plot([r['t']/60 for r in s],[r['process_cpu_percent_one_core']for r in s],label='Process CPU (% of one core)',color='#166678');axs[2].set_ylabel('One-core CPU %')
other=axs[2].twinx();m=a['memory']['samples'];other.plot([r['t']/60 for r in m],[r['footprint_bytes']/2**30 for r in m],color='#bd483a',label='Process footprint');other.set_ylabel('Footprint (GiB)',color='#bd483a');axs[2].legend(loc='upper left')
g=x['gpu_windows'];origin=x['gpu_sampling']['media_origin_seconds'];axs[3].bar([(r['sample_start_media_seconds']-origin)/60 for r in g],[r['sample_clipped_interval_union_seconds']for r in g],width=.10,color='#166678',label='Partial sampled-queue interval union / window');axs[3].set_ylim(0,1);axs[3].set_ylabel('Sampled GPU seconds');axs[3].legend(fontsize=8)
for axis in axs:
 for e in x['exclusions']:axis.axvspan(e['start']/60,e['end']/60,color='#e5b662',alpha=.3)
 axis.grid(alpha=.2)
 axs[3].axvline(a['gpu']['raw_recorded_t_range'][1]/60,color='#bd483a',ls='--',lw=.8) if axis is axs[3] else None
axs[3].text(12.7,.8,'Raw prefix filled; aggregates continue',fontsize=8,color='#bd483a')
b=[r for r in x['samples']if not r['excluded']and 'battery_fraction'in r];axs[4].step([r['t']/60 for r in b],[r['battery_fraction']*100 for r in b],where='post',color='#166678');axs[4].set_ylabel('Coarse battery %');axs[4].set_xlabel('Minutes since recording start');axs[4].set_xlim(0,x['duration_seconds']/60);axs[4].set_yticks([30,35,40]);axs[4].text(.3,31,'Shading: excluded interruptions/panels. GPU sampling: 1 s / 10 s, known queue only.\nPreparation occurred 15.88 s after recording ended; no post-preparation benefit measured.',fontsize=9)
f.savefig(H/'E-M4-010.timeline.png',dpi=150);f.savefig(H/'E-M4-010.timeline.pdf')
print('Wrote PNG/PDF from archived input')
