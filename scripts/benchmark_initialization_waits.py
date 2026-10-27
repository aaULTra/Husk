#!/usr/bin/env python3
"""Actual guest once contention: synthetic CPU/wall evidence, never device energy."""
import argparse,hashlib,json,statistics,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests/translation-layer'))
from test_publication_wait import build_harness

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path);a=p.parse_args()
 result={'scope':'Synthetic actual Bionic once:12 threads wait on one100ms initializer,3repeats per mode. Linux/Apple host CPU/wall only; not Dungeons/M4/iPhone performance or watts/temperature. Completed fast path checked separately.',
         'source_hashes':{str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()for path in [ROOT/'src/translation-layer-next/husk-tl-bionic-pthread.c',ROOT/'src/translation-layer-next/husk-tl-publication-wait.c']},'runs':{},'energy_benefit':'UNVERIFIED'}
 with tempfile.TemporaryDirectory()as d:
  exe=build_harness(d)
  for mode in ['bench-off','bench-on']:
   rows=[json.loads(subprocess.check_output([str(exe),mode],text=True,timeout=15))for _ in range(3)]
   result['runs'][mode]={'samples':rows,'median_cpu_seconds':statistics.median(r['cpu_seconds']for r in rows),'median_wall_seconds':statistics.median(r['wall_seconds']for r in rows)}
 text=json.dumps(result,indent=2)+'\n'
 if a.output:a.output.write_text(text)
 else:print(text,end='')
if __name__=='__main__':main()
