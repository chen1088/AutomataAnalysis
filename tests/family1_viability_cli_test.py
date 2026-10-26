#!/usr/bin/env python3
"""Independent closed-proof and cache-budget regressions for native viability."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


def key(table):
    return ''.join(f'{t:02d}' for row in table for t in row)


def verify(result):
    table=result['canonical_table'];n=len(table)
    assert result['decision']=='unknown' and result['witness'] is None and result['upper_bound'] is None
    assert result['lower_bound']==1
    for proof in result['viability']['proof_examples']:
        mask=proof['mask'];closed={tuple(p) for p in proof['closed_pairs']}
        assert tuple(proof['endpoints']) in closed
        assert all(0<=a<n and 0<=b<n and a!=b for a,b in closed)
        for a,b in closed:
            for x in (0,1):
                pair=(table[a][x^((mask>>a)&1)],table[b][x^((mask>>b)&1)])
                assert pair in closed
    return result


def exercise(exe,folder):
    folder.mkdir(parents=True,exist_ok=True);counter=0
    def run(table,checks,partial=False):
        nonlocal counter
        counter+=1;out=folder/f'case-{counter}'
        command=[str(exe),'--graph',key(table),'--out',str(out),'--mode','finder','--length','6',
                 '--samples','4','--seed','1088','--window-k','1','--beam-width','2','--tail-threshold','0',
                 '--first-prefix','0','--second-prefix','1','--best-of-seeds','--viability-checks',str(checks)]
        if partial:command+=['--limit-samples','1']
        completed=subprocess.run(command,capture_output=True,text=True,timeout=30)
        assert completed.returncode==0,(completed.stdout,completed.stderr)
        result=verify(json.loads(completed.stdout))
        assert result['viability']['coordinate_limit']==checks
        return result,out,command

    dead=((1,2),(1,1),(2,2))
    blocked,_,_=run(dead,1)
    assert blocked['module_stats']['expanded_nodes']==0
    assert blocked['module_stats']['obstruction_pruned_nodes']==4
    assert blocked['viability']['proven_obstructions']==4
    assert blocked['guided_attempt']['proven_obstruction'] is True
    disabled,_,_=run(dead,0)
    assert disabled['module_stats']['expanded_nodes']>0
    assert disabled['module_stats']['obstruction_pruned_nodes']==0

    # First unmerged mask0 is locally mergeable; mask1 is not. With N=1,
    # a cached mask0 must still consume the coordinate budget and prevent
    # a spurious extra initial-coordinate check on a warm cache.
    warm=((0,1),(0,2),(0,1))
    full,_,_=run(warm,1)
    assert full['viability']['cache_hits']>0
    partial,out,command=run(warm,1,True)
    assert partial['samples_completed']==1 and not partial['traversal_complete']
    continued=subprocess.run(command+['--resume','--limit-samples','0'],capture_output=True,text=True,timeout=30)
    assert continued.returncode==0,continued.stderr
    resumed=verify(json.loads(continued.stdout))
    assert resumed['module_stats']==full['module_stats'],(resumed['module_stats'],full['module_stats'])
    assert resumed['guided_attempt']==full['guided_attempt']
    assert resumed['samples_completed']==full['samples_completed']==4
    result_bytes=(out/'result.json').read_bytes()
    assert (out/'result.sha256').read_text().strip()==hashlib.sha256(result_bytes).hexdigest()
    print(json.dumps({'passed':True,'negative_closed_proofs_verified':True,
                      'disabled_viability_never_prunes':True,'cache_hits_consume_fixed_coordinate_budget':True,
                      'warm_uninterrupted_matches_cold_resumed_branch_decisions':True,
                      'no_graph_score_bound_from_pruned_prefix':True}))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--exe',required=True,type=Path);p.add_argument('--work-dir',type=Path);a=p.parse_args()
    exe=a.exe.resolve()
    if a.work_dir:exercise(exe,a.work_dir.resolve())
    else:
        with tempfile.TemporaryDirectory(prefix='family1-viability-cli-')as temp:exercise(exe,Path(temp))


if __name__=='__main__':main()
