import subprocess,tempfile,json,statistics
from pathlib import Path
root=Path(__file__).resolve().parents[3]
harness=r'''
#define _POSIX_C_SOURCE 200809L
#include "husk-tl-render-inventory.c"
#include <time.h>
#include <stdio.h>
int main(void){husk_ue4_set_render_inventory(true);tl_ri_activate("Dungeons");image_info p={.type=14,.height=100,.depth=1};for(unsigned i=1;i<=300;i++){p.width=i;tl_ri_image(&p);}struct timespec a,b;clock_gettime(CLOCK_PROCESS_CPUTIME_ID,&a);for(unsigned i=0;i<500000;i++){p.width=1000+(i%256);tl_ri_image(&p);}clock_gettime(CLOCK_PROCESS_CPUTIME_ID,&b);printf("%.9f\n",(b.tv_sec-a.tv_sec)+(b.tv_nsec-a.tv_nsec)/1e9);return 0;}
'''
results={}
with tempfile.TemporaryDirectory() as d:
 for version in ['old','new']:
  p=Path(d)/version;p.mkdir()
  for name in ['husk-tl-render-inventory.c','husk-tl-render-inventory.h']:
   content=subprocess.check_output(['git','show','acff490:src/translation-layer-next/'+name],cwd=root,text=True) if version=='old' else (root/'src/translation-layer-next'/name).read_text()
   (p/name).write_text(content)
  (p/'main.c').write_text(harness)
  subprocess.run(['cc','-O2','-std=c11','-pthread',str(p/'main.c'),'-o',str(p/'bench')],check=True)
  values=[float(subprocess.check_output([str(p/'bench')],text=True)) for _ in range(5)]
  results[version]={'process_cpu_seconds':values,'median_seconds':statistics.median(values)}
results['scope']='Linux synthetic 500000 saturated asset misses, five repeats per version, -O2. Different retained quotas. Diagnostic search cost only; not iPad gameplay, GPU, energy or thermal evidence.'
print(json.dumps(results,indent=2))
