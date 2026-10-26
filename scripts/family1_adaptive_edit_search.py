#!/usr/bin/env python3
"""Crowding-triggered, bounded edit-radius expansion with a resumable scorer.

The active view contains only best refined estimate ties. Every generated,
unselected, unknown and checkpoint-only class remains in the archived corpus.
No sampled miss changes a lower bound or certifies graph-space coverage.
"""
from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor,as_completed
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

REPO=Path(__file__).resolve().parents[1]


def read(path):return json.loads(Path(path).read_text(encoding="utf-8-sig"))
def rows(path):
    opener=gzip.open if str(path).endswith(".gz") else open
    with opener(path,"rt",encoding="utf-8-sig") as stream:
        for line in stream:
            if line.strip():yield json.loads(line)
def digest(path):
    with Path(path).open("rb") as stream:return hashlib.file_digest(stream,"sha256").hexdigest()
def reference(path):
    path=Path(path).resolve();return {"path":str(path),"sha256":digest(path)}
def json_out(path,value):
    temporary=path.with_suffix(path.suffix+".tmp");temporary.write_text(json.dumps(value,indent=2)+"\n",encoding="utf-8");temporary.replace(path)
def jsonl_out(path,values):
    if str(path).endswith(".gz"):
        with path.open("wb") as raw,gzip.GzipFile(filename="",mode="wb",fileobj=raw,mtime=0) as stream:
            for value in values:stream.write((json.dumps(value,sort_keys=True,separators=(",",":"))+"\n").encode())
    else:path.write_text("".join(json.dumps(value,sort_keys=True,separators=(",",":"))+"\n" for value in values),encoding="utf-8")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,default=REPO/"out/family1-m8-adaptive-edit-r3")
    parser.add_argument("--trigger-state",type=Path,default=REPO/"out/family1-m8-adaptive-v3-pending")
    parser.add_argument("--corpus",type=Path,default=REPO/"results/family1-m8-search/records.jsonl.gz")
    parser.add_argument("--parents",type=Path,default=REPO/"out/family1-m8-search-v1/initial-screen-inputs/parents.jsonl")
    parser.add_argument("--prior-r1",type=Path,default=REPO/"out/family1-m8-search-v1/generation-r1")
    parser.add_argument("--prior-r2",type=Path,default=REPO/"out/family1-m8-r2-search/generated")
    parser.add_argument("--generation",type=Path,help="Optional intact existing generation with identical pinned radius/parents/settings.")
    parser.add_argument("--edit-exe",type=Path,default=REPO/"out/build/msvc-vcpkg/Release/Family1Edit.exe")
    parser.add_argument("--score-exe",type=Path,default=REPO/"out/build/msvc-vcpkg/Release/Family1Sample.exe")
    parser.add_argument("--roots",type=int,default=256)
    parser.add_argument("--jobs",type=int,default=12)
    parser.add_argument("--wall-seconds",type=int,default=240)
    parser.add_argument("--resume",action="store_true")
    args=parser.parse_args();assert args.roots>0 and 1<=args.jobs<=32 and args.wall_seconds>=30
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);started=time.monotonic()
    trigger=read(args.trigger_state/"summary.json")
    current=list(rows(args.trigger_state/"records.jsonl"))
    maximum_k=max([b.get("window_k",0) for b in trigger.get("batches",[])]+[r.get("max_attempted_k") or 0 for r in current])
    prior_radius=read(args.prior_r2/"run.json")["radius"];radius=prior_radius+1
    assert trigger["crowded_top_band"]>=trigger.get("crowding_threshold",3) and maximum_k>=16 and radius==3,"No supported radius3 escalation trigger."
    sources=out/"sources-used";sources.mkdir(exist_ok=True)
    modules=["family1_adaptive_candidate_search.py","family1_graph_candidate_search.py","family1_rank_edit_candidates.py","family1_study.py"]
    for source in [Path(__file__),*[REPO/"scripts"/name for name in modules]]:
        destination=sources/source.name
        if destination.exists():assert source.read_bytes()==destination.read_bytes(),"Changed source requires fresh output."
        else:shutil.copy2(source,destination)
    native=out/"native-used";native.mkdir(exist_ok=True)
    for source in [args.edit_exe,args.score_exe,*args.score_exe.parent.glob("*.dll")]:
        destination=native/source.name
        if destination.exists():assert digest(destination)==digest(source),"Changed native executable/dependency."
        else:shutil.copy2(source,destination)
    sys.path.insert(0,str(sources))
    import family1_adaptive_candidate_search as adaptive
    import family1_rank_edit_candidates as ranker
    scoring=adaptive.scoring
    parent_rows=list(rows(args.parents));assert len(parent_rows)==55 and all(r["m"]==7 for r in parent_rows)
    generation=args.generation.resolve() if args.generation else out/"generated"
    if not args.generation:
        command=[str(native/args.edit_exe.name)]
        for parent in parent_rows:command += ["--graph",parent["key"]]
        command += ["--target-m","8","--radius","3","--seed","65537","--max-paths","16000","--max-candidates","4096","--root-closure","--out",str(generation)]
        if (generation/"run.json").exists():command.append("--resume")
        process=subprocess.run(command,capture_output=True,text=True,check=True)
        (out/"generation.log").write_text(process.stdout+process.stderr,encoding="utf-8")
    generation_run=read(generation/"run.json");generation_summary=read(generation/"summary.json")
    for field,value in {"target_m":8,"radius":3,"seed":65537,"max_paths":16000,"max_candidates":4096,"root_closure":True}.items():assert generation_run[field]==value
    assert set(generation_run["source_keys"])=={r["key"] for r in parent_rows}
    for stem,extension in [("run",".json"),("summary",".json"),("candidates",".jsonl"),("paths",".jsonl")]:
        assert (generation/(stem+".sha256")).read_text().strip()==digest(generation/(stem+extension))
    candidates=list(rows(generation/"candidates.jsonl"));paths=list(rows(generation/"paths.jsonl"))
    ranked,features,ranking_summary=ranker.rank_rows(candidates,paths,parent_rows,strategy="parent-strata",seed=65537)
    jsonl_out(out/"ranked-candidates.jsonl",ranked);json_out(out/"ranking-features.json",features);json_out(out/"ranking-summary.json",ranking_summary)
    excluded_paths=[args.prior_r1/"candidates.jsonl",args.prior_r2/"candidates.jsonl"]
    previous_shapes={r["shape_key"] for path in excluded_paths for r in rows(path)}
    selected=[];selected_shapes=set()
    for row in ranked:
        if row["shape_key"] in previous_shapes:continue
        if len(selected)<args.roots or row["shape_key"] in selected_shapes:
            selected.append(row);selected_shapes.add(row["shape_key"])
    jsonl_out(out/"selected-candidates.jsonl",selected)
    corpus_rows=list(rows(args.corpus));corpus={r["key"]:r for r in corpus_rows}
    queries=[]
    for row in selected:
        graph=scoring.graph_metadata(row);upper=corpus.get(graph["key"],{}).get("upper_bound")
        cap=min(64,upper-1) if upper is not None else 64
        if cap<1:continue
        stage=adaptive.build_stage(graph,8,cap,seed=1088,samples=1024,beam=16,seconds=20,minimum=100000)
        queries.append({"graph":graph,"stage":stage,"cap":cap})
    plan={"schema":1,"method":"crowding-triggered-radius3-expansion","trigger":scoring.reference(args.trigger_state/"summary.json"),
          "prior_refined":scoring.reference(args.trigger_state/"records.jsonl"),"parents":scoring.reference(args.parents),
          "generation":scoring.reference(generation/"run.json"),"generation_candidates":scoring.reference(generation/"candidates.jsonl"),
          "generation_paths":scoring.reference(generation/"paths.jsonl"),"excluded_generations":[scoring.reference(p) for p in excluded_paths],
          "seed":65537,"radius":3,"root_budget":args.roots,"selected_roots":len(selected),"selected_shapes":len(selected_shapes),"queries":queries,"new_only_shapes":True}
    plan=json.loads(scoring.compact(plan))
    if (out/"selection-plan.json").exists():assert args.resume and read(out/"selection-plan.json")==plan,"Changed selection plan."
    else:json_out(out/"selection-plan.json",plan)
    plan_sha=digest(out/"selection-plan.json")
    config={"schema":1,"method":"bounded-crowding-adaptive-edit-radius-controller","selection_plan_sha256":plan_sha,
            "trigger_band":trigger["crowded_top_band"],"trigger_maximum_attempted_k":maximum_k,"prior_radius":prior_radius,
            "requested_radius":radius,"score_executable":reference(native/args.score_exe.name),"edit_executable":reference(native/args.edit_exe.name),
            "source_snapshots":[reference(sources/name) for name in [Path(__file__).name,*modules]],"corpus":reference(args.corpus),
            "jobs":args.jobs,"wall_seconds":args.wall_seconds,"new_query_launch_reserve_seconds":25,
            "qualification":"completed strong stage AND independently verified finite new pair; timeout positives remain pending",
            "global_optimality_claimed":False}
    if (out/"run.json").exists():assert args.resume and read(out/"run.json")==config,"Changed controller settings."
    else:json_out(out/"run.json",config)
    inputs=out/"inputs-used";inputs.mkdir(exist_ok=True)
    for source,name in [(args.parents,"parents.jsonl"),(args.trigger_state/"summary.json","trigger-summary.json"),(args.trigger_state/"records.jsonl","prior-refined.jsonl"),
                        (args.corpus,"sealed-corpus.jsonl.gz"),*( (p,f"excluded-{i}.jsonl") for i,p in enumerate(excluded_paths))]:
        if (inputs/name).exists():assert digest(inputs/name)==digest(source)
        else:shutil.copy2(source,inputs/name)
    answers=[]
    def evaluate(q):
        directory=out/"queries"/q["graph"]["key"]/'k8'
        if not (directory/"observation.json").exists() and time.monotonic()-started>args.wall_seconds-25:return None
        return adaptive.query(native/args.score_exe.name,q["graph"],q["stage"],q["cap"],directory,plan_sha)
    with ThreadPoolExecutor(max_workers=args.jobs) as workers:
        futures=[workers.submit(evaluate,q) for q in queries]
        for index,future in enumerate(as_completed(futures),1):
            answer=future.result()
            if answer is not None:answers.append(answer)
            if index%32==0 or index==len(queries):print(json.dumps({"processed":index,"selected":len(queries),"verified_observations":len(answers)}),flush=True)
    archive=adaptive.load_archive(args.corpus,[args.trigger_state/"records.jsonl"],8)
    old_eligible={r["key"] for r in current}
    for row in current:
        for field in ["completed_k","max_attempted_k","observations"]:
            if field in row:archive[row["key"]][field]=row[field]
    candidate_ref=scoring.reference(generation/"candidates.jsonl");path_ref=scoring.reference(generation/"paths.jsonl")
    for row in candidates:
        graph=scoring.graph_metadata(row)
        if graph["key"] not in archive:archive[graph["key"]]={**graph,"lower_bound":1,"upper_bound":None,"witness":None,"eligible":False,"completed_k":None,"max_attempted_k":None,"provenance":[],"observations":[]}
        archive[graph["key"]]["generation_provenance"]={"candidates":candidate_ref,"paths":path_ref,"path_ids":row["path_ids"],"root_metadata":row["root_metadata"],"rooted_edit_distance_upper_bound":row["rooted_edit_distance_upper_bound"]}
    for answer in answers:
        key=answer["query"]["graph"]["key"];row=archive[key];positive=answer["best_positive"]
        row["max_attempted_k"]=max(row.get("max_attempted_k") or 0,8)
        if positive:
            if row["upper_bound"] is None or positive["upper_bound"]<row["upper_bound"]:
                row.update(upper_bound=positive["upper_bound"],witness=positive["witness"],upper_certificate={**positive,"stage":answer["query"]["stage"],"native_configuration":answer["native_configuration"]})
            assert row["upper_bound"]>=row["lower_bound"],"Verified upper contradicts supplied lower certificate."
        if answer["completed_stage"] and positive:
            row["eligible"]=True;row["completed_k"]=max(row.get("completed_k") or 0,8)
        row["observations"].append({"k":8,"outcome":answer["outcome"],"completed_stage":answer["completed_stage"],"native_configuration":answer["native_configuration"],"query_plan_sha256":plan_sha})
    def decorate(row):
        result={**row,"status":"exact" if row["lower_bound"]==row["upper_bound"] else "bounded" if row["upper_bound"] is not None else "incomplete","merge_length":row["lower_bound"] if row["lower_bound"]==row["upper_bound"] else None}
        if row["upper_bound"] is not None:
            L=row["upper_bound"];exact=result["status"]=="exact"
            result["estimate"]={"point":L if exact else max(row["lower_bound"],L-1),"rough_band":[L,L] if exact else [max(1,L-2,row["lower_bound"]),L],"certified":exact,"rule":"user heuristic: H approximately L-1, rough[L-2,L]"}
        return result
    eligible=sorted([decorate(row) for row in archive.values() if row["eligible"] and row["upper_bound"] is not None],key=lambda r:(-r["estimate"]["point"],-r["upper_bound"],r["key"]))
    active=[r for r in eligible if r["estimate"]["point"]==eligible[0]["estimate"]["point"]] if eligible else []
    new=[r for r in eligible if r["key"] not in old_eligible]
    jsonl_out(out/"records.jsonl",eligible);jsonl_out(out/"qualified-records.jsonl",eligible);jsonl_out(out/"new-qualified-records.jsonl",new)
    jsonl_out(out/"active-best.jsonl",active);jsonl_out(out/"observations.jsonl",answers)
    jsonl_out(out/"archive-records.jsonl.gz",[decorate(archive[k]) for k in sorted(archive)])
    jsonl_out(out/"pending-records.jsonl.gz",[decorate(archive[k]) for k in sorted(archive) if not archive[k]["eligible"]])
    summary={"schema":1,"method":config["method"],"trigger":{"crowded_top_band":trigger["crowded_top_band"],"threshold":trigger.get("crowding_threshold",3),"maximum_attempted_k":maximum_k,"prior_radius":prior_radius,"expanded_radius":radius},
        "generated_rooted_classes":len(candidates),"generated_ordinary_shapes":generation_summary["ordinary_shape_count"],"generation_complete":generation_summary["enumeration_complete"],
        "selected_roots":len(selected),"selected_new_shapes":len(selected_shapes),"verified_observations":len(answers),"selected_without_query":len(queries)-len(answers),
        "outcomes":dict(Counter(a["outcome"] for a in answers)),"completed_stages":sum(a["completed_stage"] for a in answers),
        "positive_observations":sum(a["best_positive"] is not None for a in answers),"new_qualified_classes":len(new),"total_qualified_classes":len(eligible),
        "archived_classes":len(archive),"active_best_ties":len(active),"active_verified_upper_length":active[0]["upper_bound"] if active else None,"active_estimate":active[0]["estimate"] if active else None,
        "all_generated_unselected_unknowns_retained":True,"timeout_checkpoint_positives_qualified":False,"misses_raise_lower_bound":False,"global_maximum_claimed":False,
        "selection_plan":reference(out/"selection-plan.json"),"run":reference(out/"run.json"),"whole_invocation_seconds":time.monotonic()-started}
    json_out(out/"summary.json",summary);print(json.dumps(summary,indent=2))


if __name__=="__main__":main()
