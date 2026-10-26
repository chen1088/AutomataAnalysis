#!/usr/bin/env python3
"""Independent path, selection, witness and read-only resume audit for the R3 run."""
import argparse
from collections import Counter
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import time

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'scripts'))
from family1_publish_edit_candidate_pilot import check_paths

def rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]

def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def normalized(value):return json.loads(json.dumps(value))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,default=REPO/'out/family1-m8-adaptive-edit-r3')
    parser.add_argument('--generation',type=Path,default=REPO/'out/family1-m8-r3-instant-generated')
    args=parser.parse_args();run=args.run.resolve();generation=args.generation.resolve();start=time.monotonic()
    parents=rows(run/'inputs-used/parents.jsonl');paths=rows(generation/'paths.jsonl')
    check_paths(paths,{r['key'] for r in parents},3)
    selected=rows(run/'selected-candidates.jsonl');generated=rows(generation/'candidates.jsonl')
    selected_shapes={r['shape_key'] for r in selected}
    old_shapes={r['shape_key'] for name in ['excluded-0.jsonl','excluded-1.jsonl'] for r in rows(run/'inputs-used'/name)}
    assert not selected_shapes&old_shapes
    assert {r['key'] for r in selected}=={r['key'] for r in generated if r['shape_key'] in selected_shapes}
    qualified=rows(run/'records.jsonl');new=rows(run/'new-qualified-records.jsonl');prior=rows(run/'inputs-used/prior-refined.jsonl')
    assert {r['key'] for r in qualified}=={r['key'] for r in prior}|{r['key'] for r in new}
    observations=rows(run/'observations.jsonl')
    assert len(observations)==len(selected)==261 and all(r['completed_stage'] and r['best_positive'] for r in observations)
    artifacts=[p for p in (run/'queries').rglob('*') if p.is_file() and p.name in ['run.json','result.json','result.sha256','observation.json']]
    before={str(p):digest(p) for p in artifacts}
    spec=importlib.util.spec_from_file_location('audited_outer',run/'sources-used/family1_adaptive_edit_search.py')
    outer=importlib.util.module_from_spec(spec);spec.loader.exec_module(outer)
    outer.REPO=REPO
    captured={}
    outer.json_out=lambda p,v:captured.__setitem__(str(p),normalized(v))
    outer.jsonl_out=lambda p,v:captured.__setitem__(str(p),normalized(list(v)))
    calls=[]
    def blocked(*args,**kwargs):
        calls.append(args);raise AssertionError('Read-only resume launched a backend.')
    outer.subprocess.run=blocked
    sys.argv=[str(run/'sources-used/family1_adaptive_edit_search.py'),'--out',str(run),'--generation',str(generation),
              '--score-exe',str(run/'native-used/Family1Sample.exe'),'--edit-exe',str(run/'native-used/Family1Edit.exe'),'--resume']
    with contextlib.redirect_stdout(io.StringIO()):outer.main()
    for name in ['records.jsonl','qualified-records.jsonl','new-qualified-records.jsonl','active-best.jsonl']:
        assert captured[str(run/name)]==rows(run/name),name
    keyed=lambda values:{r['query']['graph']['key']:r for r in values}
    assert keyed(captured[str(run/'observations.jsonl')])==keyed(observations)
    assert not calls and before=={str(p):digest(p) for p in artifacts}
    linked={meta['path_id'] for row in selected for meta in row['root_metadata']}
    kinds=Counter(step['operation']['kind'] for index in linked for step in paths[index]['steps'])
    result={'schema':1,'passed':True,'all_paths_replayed':len(paths),'all_primitive_steps_replayed':sum(len(r['steps']) for r in paths),
            'all_source_parents':len(parents),'selected_whole_shape_roots':len(selected),'selected_novel_shapes':len(selected_shapes),
            'selected_linked_paths':len(linked),'selected_linked_primitive_counts':dict(kinds),
            'prior_qualified':len(prior),'new_qualified':len(new),'qualified_union':len(qualified),
            'full_mask_observations_revalidated':len(observations),'mask_count':256,
            'resume_backend_subprocesses':len(calls),'unchanged_native_artifacts':len(artifacts),
            'resume_semantic_records_and_active_ties_identical':True,'observation_multiset_identical':True,
            'tuple_list_json_normalization_applied':True,'historical_pinned_executable_used':True,
            'seconds':time.monotonic()-start,'auditor_sha256':digest(Path(__file__))}
    (run/'independent-audit.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
