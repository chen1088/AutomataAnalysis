#!/usr/bin/env python3
"""Second blind quality grid for prefix matching plus proven viability.

The first benchmark and its driver remain unchanged. This version additionally
records prefix preprocessing and viability work;128 is the outer seed budget,
not a claim of identical total computation to the first version.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import time

from family1_finder_benchmark import REPO, endpoint, load_cases, reference


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--exe',required=True,type=Path)
    p.add_argument('--output',type=Path,default=REPO/'results/family1-finder-prefixmatch-version-benchmark')
    p.add_argument('--work-dir',type=Path,default=REPO/'out/family1-finder-prefixmatch-version-benchmark')
    p.add_argument('--seeds',type=int,default=128)
    p.add_argument('--viability-checks',type=int,default=8)
    p.add_argument('--tail-grid',type=int,nargs='+',default=[0,2,8])
    p.add_argument('--timeout',type=int,default=120)
    p.add_argument('--case',action='append')
    a=p.parse_args();a.exe=a.exe.resolve();assert a.exe.is_file()
    exe_reference=reference(a.exe);cases,sources=load_cases()
    if a.case:
        assert set(a.case)<={case['label'] for case in cases}
        cases=[case for case in cases if case['label'] in a.case]
    a.output.mkdir(parents=True,exist_ok=True);rows=[]
    for case in cases:
        for threshold in a.tail_grid:
            output=a.work_dir/case['label']/f'tail-{threshold}'
            command=[str(a.exe),'--graph',case['key'],'--out',str(output),'--mode','finder',
                     '--length',str(2*case['H']+8),'--samples',str(a.seeds),'--seed','1088',
                     '--window-k','2','--beam-width','4','--tail-threshold',str(threshold),
                     '--tail-max-states','100000','--best-of-seeds','--viability-checks',str(a.viability_checks),
                     '--prefix-depth','16','--prefix-max-words','65536','--prefix-max-pairs','128',
                     '--prefix-samples-per-depth','16384']
            reused=(output/'run.json').exists()
            if reused:command.append('--resume')
            start=time.perf_counter();run=subprocess.run(command,capture_output=True,text=True,timeout=a.timeout);wall=time.perf_counter()-start
            assert run.returncode==0,(case['label'],threshold,run.stdout,run.stderr)
            result=json.loads(run.stdout);data=(output/'result.json').read_bytes()
            assert json.loads(data)==result
            assert (output/'result.sha256').read_text().strip()==hashlib.sha256(data).hexdigest()
            assert result['canonical_table']==case['canonical_table'] and result['lower_bound']==1
            found=result['decision']=='collision';length=result['upper_bound'] if found else None
            if found:
                first,second=result['witness'];assert first!=second and len(first)==len(second)==length
                assert case['H']<=length<=2*case['H']+8
                assert all(endpoint(case['canonical_table'],mask,first)==endpoint(case['canonical_table'],mask,second)
                           for mask in range(1<<case['m']))
            else:assert result['decision']=='unknown' and result['upper_bound'] is None and result['witness'] is None
            module=result['module_stats'];prefix=result['prefix_seed_stats'];viability=result['viability'];tail=result['exact_tail']
            config=json.loads((output/'run.json').read_text())
            row={'case':case['label'],'kind':case['kind'],'m':case['m'],'H':case['H'],'key':case['key'],
                 'tail_threshold':threshold,'found_length':length,'gap':length-case['H'] if found else None,
                 'ratio':length/case['H'] if found else None,'miss':not found,'witness':result['witness'],
                 'automatic_seed_budget':a.seeds,'samples_completed':result['samples_completed'],
                 'native_seconds':result['seconds'],'whole_invocation_seconds':wall,'reused_result':reused,
                 'tail_calls':module['tail_calls'],'tail_states':module['tail_states'],
                 'prefix_seeds_checked':module['prefix_seeds_checked'],
                 'permutation_seeds_blocked':result['permutation_prefix_seeds_blocked'],
                 'prefix_seed_stats':prefix,'viability':viability,'module_stats':module,'exact_tail':tail,
                 'native_configuration':config,'native_result':reference(output/'result.json'),'native_command':command}
            rows.append(row)
            (a.output/'runs.jsonl').write_text(''.join(json.dumps(r,separators=(',',':'))+'\n' for r in rows),encoding='utf-8')
            print(json.dumps({'case':row['case'],'T':threshold,'H':row['H'],'L':length,'gap':row['gap'],
                              'seconds':row['native_seconds'],'tail_states':row['tail_states']}),flush=True)
    assert reference(a.exe)==exe_reference,'native executable changed during benchmark'
    baseline_path=REPO/'results/family1-finder-blind-benchmark/summary.json'
    baseline=json.loads(baseline_path.read_text())
    summary={'schema':1,'version':'prefix-profile-matching-plus-proven-pair-viability',
             'cases':len(cases),'runs':len(rows),'predeclared_tail_grid':a.tail_grid,
             'automatic_seed_budget':a.seeds,'viability_checks_per_state':a.viability_checks,
             'witness_or_witness_derived_prefix_hints_used':False,
             'prefix_preprocessing_is_additional_work_not_part_of_outer_seed_count':True,
             'quality_caution':'Comparison is between complete algorithm versions, not a causal prefix-only or viability-only experiment.',
             'source_scores':sources,'native_executable':exe_reference,'driver':reference(Path(__file__)),
             'headers':[reference(REPO/name) for name in ('HardPairFinder.h','HardPairPrefixSeeds.h','HardPairViability.h')],
             'first_version':reference(baseline_path),'all_accepted_pairs_independently_replayed_on_all_static_masks':True,
             'comparisons':[],'aggregate':[],'global_shortestness_inferred_from_conditional_BFS':False}
    for threshold in a.tail_grid:
        current=[r for r in rows if r['tail_threshold']==threshold];hits=[r for r in current if not r['miss']]
        summary['aggregate'].append({'tail_threshold':threshold,'hits':len(hits),'misses':len(current)-len(hits),
                                     'matches_H':sum(r['gap']==0 for r in hits),
                                     'mean_hit_ratio':statistics.fmean(r['ratio'] for r in hits) if hits else None,
                                     'max_hit_ratio':max((r['ratio'] for r in hits),default=None),
                                     'native_seconds':sum(r['native_seconds'] for r in current),
                                     'tail_states':sum(r['tail_states'] for r in current)})
    for case in cases:
        old=next(item for item in baseline['comparisons'] if item['case']==case['label'])
        current={str(r['tail_threshold']):{k:r[k] for k in ('found_length','gap','ratio','miss','native_seconds','tail_states')}
                 for r in rows if r['case']==case['label']}
        summary['comparisons'].append({'case':case['label'],'m':case['m'],'H':case['H'],
                                       'new_version':current,'first_version':old['all_settings']})
    (a.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    columns=['case','kind','m','H','tail_threshold','found_length','gap','ratio','miss','samples_completed',
             'native_seconds','whole_invocation_seconds','tail_calls','tail_states','prefix_seeds_checked','permutation_seeds_blocked']
    with (a.output/'runs.csv').open('w',newline='',encoding='utf-8')as stream:
        writer=csv.DictWriter(stream,fieldnames=columns,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    lines=['# New-version blind quality benchmark','',
           'This is the second predeclared24-graph threshold grid. The first72-row report remains unchanged. The new version includes both full-profile prefix matching and a proven pair-viability gate. It is not a causal prefix-only comparison. No saved witness or witness-derived prefix is supplied.','',
           'The same outer budget128, k2, beam4, thresholds0/2/8, pair cap2H+8 and exact-tail state cap100,000 are used. Prefix preprocessing is additional work: complete layers through16 and16,384 deterministic sampled words at each configured longer depth20/24/28/32 when within the length cap. Every run.json configuration and preprocessing statistic is retained.','',
           '| Graph | H | First T0/T2/T8 | New T0/T2/T8 |','|---|---:|---|---|']
    for item in summary['comparisons']:
        format_values=lambda group:' / '.join(str(group.get(str(t),{}).get('found_length')) if group.get(str(t),{}).get('found_length') is not None else 'miss' for t in a.tail_grid)
        lines.append(f"| {item['case']} | {item['H']} | {format_values(item['first_version'])} | {format_values(item['new_version'])} |")
    lines.extend(['','All new-version outcomes, including misses and regressions, remain in runs.jsonl/runs.csv. Every positive pair is independently replayed over every static mask. A shortest conditional suffix certificate is not a global shortest-pair proof.',''])
    (a.output/'README.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({'completed_cases':len(cases),'runs':len(rows),'aggregate':summary['aggregate']}))


if __name__=='__main__':main()
