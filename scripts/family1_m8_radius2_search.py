#!/usr/bin/env python3
"""Bounded m8 radius2 extension into ordinary shapes absent from the r1 pool."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

REPO=Path(__file__).resolve().parents[1]


def ref(path):
    path=Path(path).resolve()
    with path.open("rb") as stream:digest=hashlib.file_digest(stream,"sha256").hexdigest()
    return {"path":str(path),"sha256":digest}


def load(path):return json.loads(Path(path).read_text(encoding="utf-8-sig"))
def rows(path):
    with Path(path).open(encoding="utf-8-sig") as stream:
        for line in stream:
            if line.strip():yield json.loads(line)
def dump(path,value):
    temporary=path.with_suffix(path.suffix+".tmp");temporary.write_text(json.dumps(value,indent=2)+"\n",encoding="utf-8");temporary.replace(path)
def dump_rows(path,values):
    path.write_text("".join(json.dumps(value,separators=(",",":"))+"\n" for value in values),encoding="utf-8")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,default=REPO/"out/family1-m8-r2-search")
    parser.add_argument("--parents",type=Path,default=REPO/"out/family1-m8-search-v1/initial-screen-inputs/parents.jsonl")
    parser.add_argument("--exclude-r1",type=Path,default=REPO/"out/family1-m8-search-v1/generation-r1/candidates.jsonl")
    parser.add_argument("--edit-exe",type=Path,default=REPO/"out/build/msvc-vcpkg/Release/Family1Edit.exe")
    parser.add_argument("--score-exe",type=Path,default=REPO/"out/build/msvc-vcpkg/Release/Family1Sample.exe")
    parser.add_argument("--selected-roots",type=int,default=2048)
    parser.add_argument("--jobs",type=int,default=4)
    parser.add_argument("--budget-seconds",type=int,default=270)
    parser.add_argument("--resume",action="store_true")
    args=parser.parse_args()
    assert 1<=args.jobs<=32 and args.selected_roots>0 and args.budget_seconds>0
    output=args.out.resolve();output.mkdir(parents=True,exist_ok=True)
    binary=output/"binary";binary.mkdir(exist_ok=True)
    sources=output/"sources-used";sources.mkdir(exist_ok=True)
    source_names=["family1_rank_edit_candidates.py","family1_graph_candidate_search.py","family1_study.py"]
    for source in [Path(__file__),*[REPO/"scripts"/name for name in source_names]]:
        destination=sources/source.name
        if destination.exists():assert destination.read_bytes()==source.read_bytes(),"source changed; fresh output required"
        else:shutil.copy2(source,destination)
    for source in [args.edit_exe,args.score_exe,*args.score_exe.parent.glob("*.dll")]:
        destination=binary/source.name
        if destination.exists():assert ref(destination)["sha256"]==ref(source)["sha256"],"binary changed; fresh output required"
        else:shutil.copy2(source,destination)
    sys.path.insert(0,str(sources))
    import family1_rank_edit_candidates as ranker
    import family1_graph_candidate_search as scorer
    parent_rows=list(rows(args.parents));assert len(parent_rows)==55 and all(r["m"]==7 for r in parent_rows)
    exclude_rows=list(rows(args.exclude_r1));old_shapes={r["shape_key"] for r in exclude_rows}
    config={"schema":1,"method":"bounded-new-shape-radius2-eight-state-search",
            "parents":ref(args.parents),"excluded_complete_r1":ref(args.exclude_r1),"edit_executable":ref(binary/args.edit_exe.name),
            "score_executable":ref(binary/args.score_exe.name),"sources":[ref(sources/name) for name in [Path(__file__).name,*source_names]],
            "target_m":8,"radius":2,"seed":2027,"max_paths":16000,"max_candidates":4096,"root_closure":True,
            "selected_root_budget":args.selected_roots,"coarse_caps":[64,40],"samples":128,"beam":4,"window_k":6,
            "prefix_depth":16,"prefix_words":65536,"max_expansions":10000,"query_timeout_seconds":10,
            "jobs":args.jobs,"invocation_work_budget_seconds":args.budget_seconds,"no_global_claim":True}
    if (output/"run.json").exists():assert args.resume and load(output/"run.json")==config
    else:
        assert not args.resume;dump(output/"run.json",config)
    started=time.perf_counter()
    generated=output/"generated"
    command=[str(binary/args.edit_exe.name)]
    for parent in parent_rows:command += ["--graph",parent["key"]]
    command += ["--target-m","8","--radius","2","--seed","2027","--max-paths","16000","--max-candidates","4096","--root-closure","--out",str(generated)]
    if (generated/"run.json").exists():command.append("--resume")
    generation_process=subprocess.run(command,capture_output=True,text=True,check=True)
    (output/"generation.log").write_text(generation_process.stdout+generation_process.stderr,encoding="utf-8")
    native_summary=load(generated/"summary.json")
    candidates=list(rows(generated/"candidates.jsonl"));paths=list(rows(generated/"paths.jsonl"))
    ranked,features,ranking_summary=ranker.rank_rows(candidates,paths,parent_rows,strategy="parent-strata",seed=2027)
    ranked_dir=output/"ranked";ranked_dir.mkdir(exist_ok=True)
    dump_rows(ranked_dir/"candidates.jsonl",ranked);dump(ranked_dir/"features.json",features);dump(ranked_dir/"summary.json",ranking_summary)
    blocks=[]
    for row in ranked:
        if not blocks or blocks[-1][0]!=row["shape_key"]:blocks.append((row["shape_key"],[]))
        blocks[-1][1].append(row)
    selected=[];new_shapes=[]
    for shape,block in blocks:
        if shape in old_shapes:continue
        new_shapes.append(shape)
        if len(selected)<args.selected_roots:selected.extend(block)
    selected_keys={r["key"] for r in selected}
    input_dir=output/"inputs-used";input_dir.mkdir(exist_ok=True)
    shutil.copy2(args.parents,input_dir/"parents.jsonl");shutil.copy2(args.exclude_r1,input_dir/"excluded-r1-candidates.jsonl")
    dump_rows(output/"selected-candidates.jsonl",selected)
    def balanced(row):
        indegrees=[0]*8
        for a,b in row["canonical_table"]:indegrees[a]+=1;indegrees[b]+=1
        return all(d==2 for d in indegrees)
    linked_ids={origin["path_id"] for row in selected for origin in row.get("root_metadata",[])}
    linked_ids.update(pid for row in selected for pid in row.get("path_ids",[]))
    selected_paths=[path for path in paths if path["path_id"] in linked_ids]
    operation_counts={}
    for path in selected_paths:
        for step in path["steps"]:
            kind=step["operation"]["kind"];operation_counts[kind]=operation_counts.get(kind,0)+1
    plan={"schema":1,"generation_summary":native_summary,"generation_command":command,"generation":ref(generated/"run.json"),
          "all_generated":ref(generated/"candidates.jsonl"),"complete_path_provenance":ref(generated/"paths.jsonl"),
          "ranked":ref(ranked_dir/"candidates.jsonl"),"parent_proofs":ref(input_dir/"parents.jsonl"),
          "excluded_r1_shapes":len(old_shapes),"new_generated_shapes":len(new_shapes),
          "generated_rooted_classes":len(candidates),"generated_balanced":sum(map(balanced,candidates)),
          "generated_unbalanced":sum(not balanced(r) for r in candidates),"selected_roots":len(selected),
          "selected_shapes":len({r["shape_key"] for r in selected}),"selected_balanced":sum(map(balanced,selected)),
          "selected_unbalanced":sum(not balanced(r) for r in selected),"selected_linked_paths":len(selected_paths),
          "selected_path_operation_counts":operation_counts,"all_selected_shapes_absent_from_r1":True,
          "every_generated_and_unselected_class_retained":True,"selection_is_whole_shapes":True}
    dump(output/"plan.json",plan)
    stage_args=scorer.arguments(["--candidates",str(output/"selected-candidates.jsonl"),"--out",str(output),"--exe",str(binary/args.score_exe.name),
        "--beam-width","4","--stage1-samples","128","--stage1-prefix-pairs","128","--stage1-k","6",
        "--stage1-prefix-depth","16","--stage1-prefix-words","65536","--stage1-expansions","10000","--stage1-timeout","10"])
    print(json.dumps({"selected":len(selected),"balanced":plan["selected_balanced"],"unbalanced":plan["selected_unbalanced"],"new_shapes":len(new_shapes)}),flush=True)
    def evaluate(row):
        if time.perf_counter()-started>=args.budget_seconds:return row["key"],[]
        graph=scorer.graph_metadata(row);stages=scorer.stage_settings(graph,stage_args)
        attempts=scorer.score_graph(binary/args.score_exe.name,graph,stages,[64,40],40,output/"queries"/row["key"])
        return row["key"],attempts
    answers={};journal=(output/"progress.jsonl").open("a",encoding="utf-8")
    with ThreadPoolExecutor(max_workers=args.jobs) as workers:
        futures=[workers.submit(evaluate,row) for row in selected]
        for future in as_completed(futures):
            key,attempts=future.result();answers[key]=attempts
            journal.write(json.dumps({"key":key,"attempts":attempts},separators=(",",":"))+"\n");journal.flush()
            if len(answers)%128==0 or len(answers)==len(selected):print(json.dumps({"completed":len(answers),"selected":len(selected)}),flush=True)
    journal.close()
    records=[];observations=[]
    for row in ranked:
        record={**row,"status":"not-evaluated","lower_bound":1,"upper_bound":None,"merge_length":None,"witness":None,
                "selection":"selected-new-shape" if row["key"] in selected_keys else "already-r1-shape" if row["shape_key"] in old_shapes else "unselected-new-shape",
                "generation_sources":{"candidates":plan["all_generated"],"paths":plan["complete_path_provenance"],"parents":plan["parent_proofs"]}}
        attempts=answers.get(row["key"],[])
        if row["key"] in selected_keys:record["status"]="unresolved"
        accepted=[]
        for attempt in attempts:
            observation=attempt["observation"]
            observations.append({"m":8,"key":row["key"],"attempt":attempt,"source_candidate":ref(output/"selected-candidates.jsonl")})
            if observation["upper_bound"] is not None:accepted.append(observation)
        if accepted:
            best=min(accepted,key=lambda r:r["upper_bound"])
            record.update(status="bounded",upper_bound=best["upper_bound"],witness=best["witness"],verification=best["verification"])
        records.append(record)
    dump_rows(output/"records.jsonl",records);dump_rows(output/"observations.jsonl",observations)
    dump_rows(output/"unselected.jsonl",[r for r in records if r["key"] not in selected_keys])
    selected_records=[r for r in records if r["key"] in selected_keys]
    summary={"schema":1,"method":config["method"],"generated_classes":len(records),"selected_classes":len(selected),
             "selected_with_verified_upper":sum(r["upper_bound"] is not None for r in selected_records),
             "selected_unresolved":sum(r["upper_bound"] is None for r in selected_records),
             "selected_upper_at_most40":sum(r["upper_bound"] is not None and r["upper_bound"]<=40 for r in selected_records),
             "selected_upper_above40":sum(r["upper_bound"] is not None and r["upper_bound"]>40 for r in selected_records),
             "new_query_attempts_or_reused_observations":len(observations),"selected_queued_without_query":sum(not answers.get(r["key"]) for r in selected),
             "upper_histogram":{str(upper):sum(r["upper_bound"]==upper for r in selected_records) for upper in sorted({r["upper_bound"] for r in selected_records if r["upper_bound"] is not None})},
             "whole_invocation_seconds":time.perf_counter()-started,"plan":ref(output/"plan.json"),"run":ref(output/"run.json"),
             "native_enumeration_complete":native_summary["enumeration_complete"],"global_exhaustiveness_claimed":False,
             "unknowns_and_unselected_retained":True,"all_hits_full_family_independently_replayed":True}
    dump(output/"summary.json",summary);print(json.dumps(summary,indent=2))


if __name__=="__main__":main()
