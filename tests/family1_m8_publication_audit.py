#!/usr/bin/env python3
"""Independent full path replay and interval/count audit of the m8 publication."""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/"scripts"))
from family1_publish_edit_candidate_pilot import check_paths,check_step,canon
from family1_study import canonical_table,fixed_key,validate_table


def digest(path):
    with Path(path).open("rb") as stream:return hashlib.file_digest(stream,"sha256").hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding="utf-8-sig"))
def rows(path):
    opener=gzip.open if str(path).endswith(".gz") else open
    with opener(path,"rt",encoding="utf-8-sig") as stream:
        for line in stream:
            if line.strip():yield json.loads(line)
def ref(path):
    path=Path(path).resolve();return {"path":str(path),"sha256":digest(path),"bytes":path.stat().st_size}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publication",type=Path,default=REPO/"results/family1-m8-search")
    args=parser.parse_args();folder=args.publication.resolve();started=time.perf_counter()
    pinned_manifest=ref(folder/"manifest.json");manifest=read(folder/"manifest.json")
    for name,expected in manifest.items():
        path=folder/name
        assert digest(path)==expected["sha256"] and path.stat().st_size==expected["bytes"],name
    parents_file=REPO/"out/family1-m8-search-v1/initial-screen-inputs/parents.jsonl"
    parents=list(rows(parents_file));assert len(parents)==55
    parent_keys={p["key"] for p in parents};assert len(parent_keys)==55 and all(p["m"]==7 for p in parents)
    path_stats=[]
    for path,radius in [(folder/"generation-paths.jsonl.gz",1),(folder/"extra-generation-0-paths.jsonl.gz",2)]:
        values=list(rows(path));check_paths(values,parent_keys,radius)
        kinds=Counter(s["operation"]["kind"] for p in values for s in p["steps"])
        path_stats.append({"file":ref(path),"radius":radius,"paths_checked":len(values),
                           "unit_steps_checked":sum(kinds.values()),"operation_counts":dict(kinds),
                           "all_root_fixed_paths_and_primitive_tables_valid":True})
        print(json.dumps({"path_audit":radius,"paths":len(values),"steps":sum(kinds.values())}),flush=True)
    inputs=read(folder/"inputs.json");expected_keys=set();upper_candidates=defaultdict(list);lower_candidates=defaultdict(lambda:1)
    supplied_tables={};source_record_rows=0
    for source in inputs["records"]:
        path=Path(source["path"]);assert digest(path)==source["sha256"]
        # A layer report is a separate lower proof, not graph-table JSONL.
        if path.suffix==".json":
            value=read(path)
            if value.get("method")=="independent-partitioned-complement-orbit-layer-v1":
                assert value["status"]=="collision-free" and value["reason"]=="" and value["phase"]=="complete"
                lower_candidates[value["key"]]=max(lower_candidates[value["key"]],value["lower_bound"])
                continue
        for row in rows(path):
            source_record_rows+=1;key=row["key"]
            table=validate_table(row["canonical_table"]);assert len(table)==8 and fixed_key(table)==key
            assert key not in supplied_tables or supplied_tables[key]==table
            supplied_tables[key]=table;expected_keys.add(key)
            lower_candidates[key]=max(lower_candidates[key],row.get("lower_bound",1))
            if row.get("upper_bound") is not None:
                upper_candidates[key].append((row["upper_bound"],row["witness"]))
    actual=list(rows(folder/"records.jsonl.gz"));by_key={r["key"]:r for r in actual}
    assert len(by_key)==len(actual) and set(by_key)==expected_keys
    evaluation_counts=Counter();observation_count=0;observation_upper=defaultdict(list)
    for row in rows(folder/"observations.jsonl.gz"):
        graph=row.get("graph",row.get("observation",{}));key=graph.get("key",row.get("key"))
        assert key in by_key;observation_count+=1;evaluation_counts[key]+=1
        observation=row.get("observation",row.get("attempt",{}).get("observation"))
        if observation is None and row.get("upper_bound") is not None:observation=row
        if observation and observation.get("upper_bound") is not None:
            observation_upper[key].append(observation["upper_bound"])
    inputs_observation_rows=0
    for source in inputs["observations"]:
        path=Path(source["path"]);assert digest(path)==source["sha256"]
        inputs_observation_rows+=sum(1 for _ in rows(path))
    assert inputs_observation_rows==observation_count
    for row in actual:
        key=row["key"];table=validate_table(row["canonical_table"])
        assert tuple(map(tuple,table))==supplied_tables[key] and canonical_table(table)==table
        expected_upper=min((v[0] for v in upper_candidates[key]),default=None)
        assert row["upper_bound"]==expected_upper,(key,row["upper_bound"],expected_upper)
        assert row["lower_bound"]==lower_candidates[key]
        assert row["evaluation_count"]==evaluation_counts[key]
        assert expected_upper is None or row["lower_bound"]<=expected_upper
        if expected_upper is None:assert row["witness"] is None and row["status"]=="incomplete"
        else:
            assert len(row["witness"][0])==len(row["witness"][1])==expected_upper and row["witness"][0]!=row["witness"][1]
            assert row["witness"] in [v[1] for v in upper_candidates[key] if v[0]==expected_upper]
            assert row["status"]==("exact" if expected_upper==row["lower_bound"] else "bounded")
        assert row["merge_length"]==(row["lower_bound"] if row["status"]=="exact" else None)
    # A positive observation must not be lost when deriving the final interval.
    observation_minimum_not_reflected=[]
    for key,values in observation_upper.items():
        if by_key[key]["upper_bound"] is None or min(values)<by_key[key]["upper_bound"]:
            observation_minimum_not_reflected.append({"key":key,"exported_upper":by_key[key]["upper_bound"],"observation_upper":min(values)})
    summary=read(folder/"summary.json");best=max(r["lower_bound"] for r in actual)
    potential={r["key"] for r in actual if r["upper_bound"] is None or r["upper_bound"]>=best}
    challengers={r["key"] for r in actual if r["upper_bound"] is None or r["upper_bound"]>best}
    best_keys={r["key"] for r in actual if r["lower_bound"]==best}
    assert {r["key"] for r in rows(folder/"potential-maximizers.jsonl.gz")}==potential
    assert {r["key"] for r in rows(folder/"unresolved-challengers.jsonl.gz")}==challengers
    assert {r["key"] for r in rows(folder/"best-certified-lower.jsonl.gz")}==best_keys
    counts={"exported_rooted_classes":len(actual),"native_attempts":observation_count,
            "evaluated_rooted_classes":sum(v>0 for v in evaluation_counts.values()),
            "best_certified_lower_bound":best,"graphs_with_best_certified_lower_bound":len(best_keys),
            "potential_maximizers_retained":len(potential),"unresolved_strict_challengers":len(challengers),
            "no_verified_upper":sum(r["upper_bound"] is None for r in actual),"exact_scores":sum(r["status"]=="exact" for r in actual)}
    for field,value in counts.items():assert summary[field]==value,(field,summary[field],value)
    assert summary["upper_histogram"]=={str(k):v for k,v in sorted(Counter(r["upper_bound"] for r in actual if r["upper_bound"] is not None).items())}
    for filename,field in [("generation-candidates.jsonl.gz","generated_local_rooted_classes"),("extra-generation-0-candidates.jsonl.gz",None)]:
        generated=list(rows(folder/filename));keys={r["key"] for r in generated}
        assert len(keys)==len(generated) and keys<=by_key.keys()
        if field:assert summary[field]==len(keys)
        else:assert summary["additional_neighborhoods"][0]["rooted_classes"]==len(keys)
    assert summary["global_enumeration_complete"] is False and summary["global_maximum_certified"] is False
    assert summary["sampling_misses_are_lower_certificates"] is False
    assert ref(folder/"manifest.json")==pinned_manifest,"Manifest changed during audit"
    result={"schema":1,"method":"independent-m8-complete-primitive-path-and-export-count-audit",
            "status":"passed" if not observation_minimum_not_reflected else "discrepancy",
            "publisher_manifest_before_audit":pinned_manifest,"auditor":ref(Path(__file__)),"parents":ref(parents_file),
            "parent_count":55,"path_audits":path_stats,"all_primitive_paths_replayed":True,
            "unique_canonical_tables_cached":canon.cache_info().currsize,"unique_primitive_steps_cached":check_step.cache_info().currsize,
            "source_record_rows":source_record_rows,"summary_counts_recomputed":counts,
            "record_union_and_all_generated_inclusion_checked":True,"source_record_interval_minima_checked":True,
            "all_observation_evaluation_counts_checked":True,"potential_ties_and_strict_challengers_exactly_retained":True,
            "observation_upper_minima_not_reflected":observation_minimum_not_reflected,
            "elapsed_seconds":time.perf_counter()-started,"no_global_maximum_claim":True}
    (folder/"path-audit.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2))
    if observation_minimum_not_reflected:raise SystemExit(1)


if __name__=="__main__":main()
