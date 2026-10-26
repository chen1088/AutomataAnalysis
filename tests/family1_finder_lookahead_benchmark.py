#!/usr/bin/env python3
"""Append-safe blind lookahead grid on every certified seven-state maximizer."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import datetime
import hashlib
import itertools
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

REPO=Path(__file__).resolve().parents[1]


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def reference(path):
    path=Path(path).resolve()
    try:name=path.relative_to(REPO).as_posix()
    except ValueError:name=str(path)
    return {'path':name,'sha256':digest(path)}
def endpoint(table,mask,word):
    s=0
    for c in word:s=table[s][int(c)^((mask>>s)&1)]
    return s
def atomic_json(path,value):
    path=Path(path);temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8');os.replace(temporary,path)
def snapshot(exe,work):
    folder=work/'binary';manifest=folder/'manifest.json';folder.mkdir(parents=True,exist_ok=True)
    if manifest.exists():
        data=json.loads(manifest.read_text());assert data['source_exe']['sha256']==digest(exe),'Use a new artifact directory for a different binary.'
        target=REPO/data['snapshot_exe']['path'];assert digest(target)==data['source_exe']['sha256']
        for item in data['dlls']:assert digest(REPO/item['path'])==item['sha256']
        return target,data
    target=folder/exe.name;shutil.copy2(exe,target);assert digest(target)==digest(exe)
    dlls=[]
    for source in sorted(exe.parent.glob('*.dll')):
        copied=folder/source.name;shutil.copy2(source,copied);dlls.append(reference(copied))
    data={'source_exe':reference(exe),'snapshot_exe':reference(target),'dlls':dlls}
    atomic_json(manifest,data);return target,data


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--exe',type=Path,required=True)
    p.add_argument('--output',type=Path,default=REPO/'results/family1-finder-lookahead-grid-v1')
    p.add_argument('--work-dir',type=Path,default=REPO/'out/family1-finder-lookahead-grid-v1')
    p.add_argument('--window-grid','--k-grid',type=int,nargs='+',default=list(range(1,7)))
    p.add_argument('--beam-grid',type=int,nargs='+',default=[4])
    p.add_argument('--tail-grid',type=int,nargs='+',default=[0,2,8])
    p.add_argument('--samples','--seeds',type=int,default=128)
    p.add_argument('--seed-grid',type=int,nargs='+',default=[1088])
    p.add_argument('--length-cap',type=int,default=76)
    p.add_argument('--max-expansions',type=int)
    p.add_argument('--prefix-max-pairs',type=int,default=128)
    p.add_argument('--prefix-depth',type=int,default=16)
    p.add_argument('--prefix-max-words',type=int,default=65536)
    p.add_argument('--prefix-samples-per-depth',type=int,default=16384)
    p.add_argument('--viability-checks',type=int,default=8)
    p.add_argument('--tail-max-states',type=int,default=100000)
    p.add_argument('--jobs',type=int,default=4)
    p.add_argument('--timeout',type=int,default=180)
    a=p.parse_args();a.exe=a.exe.resolve();a.output=a.output.resolve();a.work_dir=a.work_dir.resolve()
    assert a.exe.is_file() and a.jobs>=1 and a.samples>=1 and a.length_cap>=1
    a.output.mkdir(parents=True,exist_ok=True);a.work_dir.mkdir(parents=True,exist_ok=True)
    executable,binary=snapshot(a.exe,a.work_dir)
    source=REPO/'results/family1-m7/maximizers.jsonl'
    graphs=[json.loads(s) for s in source.read_text().splitlines() if s.strip()]
    assert len(graphs)==8 and all(g['merge_length']==34 and g['status']=='exact' for g in graphs)
    fixed={'binary':binary,'graph_source':reference(source),'samples':a.samples,'prefix_depth':a.prefix_depth,
           'prefix_max_words':a.prefix_max_words,'prefix_max_pairs':a.prefix_max_pairs,
           'prefix_samples_per_depth':a.prefix_samples_per_depth,'viability_checks':a.viability_checks,
           'tail_max_states':a.tail_max_states,'max_expansions':a.max_expansions,'length_cap':a.length_cap,
           'witness_or_witness_derived_prefix_hints_used':False}
    # Run IDs include every quality option. Appending another k/beam/seed grid
    # is safe; changing a fixed budget requires a separate artifact directory.
    binding=a.output/'binding.json'
    if binding.exists():assert json.loads(binding.read_text())==fixed,'Fixed settings differ; use a new output directory.'
    else:atomic_json(binding,fixed)
    rows_path=a.output/'runs.jsonl';previous=[]
    if rows_path.exists():previous=[json.loads(s) for s in rows_path.read_text().splitlines() if s.strip()]
    rows={r['run_id']:r for r in previous}

    def execute(job):
        graph,k,beam,tail,seed=job
        run_id=f"m7-{graph['ordinal']}-k{k}-w{beam}-t{tail}-n{a.samples}-s{seed}"
        if run_id in rows:
            row=rows[run_id];assert digest(REPO/row['native_result']['path'])==row['native_result']['sha256'];return row,True
        output=a.work_dir/'queries'/run_id
        command=[str(executable),'--graph',graph['key'],'--out',str(output),'--mode','finder',
                 '--length',str(a.length_cap),'--samples',str(a.samples),'--seed',str(seed),
                 '--window-k',str(k),'--beam-width',str(beam),'--tail-threshold',str(tail),
                 '--tail-max-states',str(a.tail_max_states),'--best-of-seeds',
                 '--viability-checks',str(a.viability_checks),'--prefix-depth',str(a.prefix_depth),
                 '--prefix-max-words',str(a.prefix_max_words),'--prefix-max-pairs',str(a.prefix_max_pairs),
                 '--prefix-samples-per-depth',str(a.prefix_samples_per_depth)]
        if a.max_expansions is not None:command+=['--max-expansions',str(a.max_expansions)]
        if (output/'run.json').exists():command.append('--resume')
        start=time.perf_counter();result=subprocess.run(command,capture_output=True,text=True,timeout=a.timeout);wall=time.perf_counter()-start
        assert result.returncode==0,(run_id,result.stdout,result.stderr)
        native=json.loads(result.stdout);data=(output/'result.json').read_bytes()
        assert json.loads(data)==native and (output/'result.sha256').read_text().strip()==hashlib.sha256(data).hexdigest()
        assert native['canonical_table']==graph['canonical_table'] and native['lower_bound']==1
        length=native['upper_bound'];found=native['decision']=='collision'
        if found:
            u,v=native['witness'];assert u!=v and len(u)==len(v)==length<=a.length_cap
            assert all(endpoint(graph['canonical_table'],s,u)==endpoint(graph['canonical_table'],s,v) for s in range(128))
            assert length>=34,'Valid pair below certified H: stop and inspect both proofs.'
        else:assert native['decision']=='unknown' and length is None and native['witness'] is None
        module=native['module_stats']
        row={'run_id':run_id,'ordinal':graph['ordinal'],'key':graph['key'],'H':34,'window_k':k,'beam_width':beam,
             'tail_threshold':tail,'seed':seed,'samples':a.samples,'length_cap':a.length_cap,
             'found_length':length,'gap':length-34 if found else None,'ratio':length/34 if found else None,
             'miss':not found,'matches_H':length==34,'native_seconds':native['seconds'],'whole_invocation_seconds':wall,
             'witness':native['witness'],'module_stats':module,'exact_tail':native['exact_tail'],
             'prefix_seed_stats':native['prefix_seed_stats'],'viability':native['viability'],
             'native_configuration':json.loads((output/'run.json').read_text()),
             'native_result':reference(output/'result.json'),'command':command}
        return row,False

    jobs=list(itertools.product(graphs,a.window_grid,a.beam_grid,a.tail_grid,a.seed_grid))
    with ThreadPoolExecutor(max_workers=a.jobs)as pool:
        futures=[pool.submit(execute,job)for job in jobs]
        for future in as_completed(futures):
            row,reused=future.result();rows[row['run_id']]=row
            if not reused:
                temporary=rows_path.with_suffix('.jsonl.tmp')
                temporary.write_text(''.join(json.dumps(r,separators=(',',':'))+'\n'for _,r in sorted(rows.items())),encoding='utf-8');os.replace(temporary,rows_path)
            print(json.dumps({k:row[k]for k in ('ordinal','window_k','beam_width','tail_threshold','found_length','gap','native_seconds')}),flush=True)
            if row['matches_H']:print('EXACT_H_MATCH '+row['run_id'],flush=True)
    groups=[]
    for k,beam,tail,seed in sorted({(r['window_k'],r['beam_width'],r['tail_threshold'],r['seed'])for r in rows.values()}):
        group=[r for r in rows.values()if(r['window_k'],r['beam_width'],r['tail_threshold'],r['seed'])==(k,beam,tail,seed)]
        groups.append({'window_k':k,'beam_width':beam,'tail_threshold':tail,'seed':seed,'graphs':len(group),
                       'H_matches':sum(r['matches_H']for r in group),'misses':sum(r['miss']for r in group),
                       'lengths_by_ordinal':{str(r['ordinal']):r['found_length']for r in sorted(group,key=lambda r:r['ordinal'])},
                       'native_seconds':sum(r['native_seconds']for r in group)})
    summary={'schema':1,'binding':fixed,'total_preserved_runs':len(rows),'current_requested_runs':len(jobs),
             'current_grid':{'window':a.window_grid,'beam':a.beam_grid,'tail':a.tail_grid,'seed':a.seed_grid},
             'groups':groups,'matches_H':[r['run_id']for r in rows.values()if r['matches_H']],
             'driver':reference(Path(__file__)),'all_positive_pairs_independently_scalar_verified_on_128_masks':True,
             'scope':'Heuristic calibration against independently known H34; conditional BFS alone proves no global minimum.'}
    atomic_json(a.output/'summary.json',summary)
    with(a.output/'batches.jsonl').open('a',encoding='utf-8')as stream:stream.write(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'requested_runs':len(jobs),'grid':summary['current_grid']})+'\n')
    print(json.dumps({'preserved_runs':len(rows),'H_matches':len(summary['matches_H']),'summary':str(a.output/'summary.json')}))


if __name__=='__main__':main()
