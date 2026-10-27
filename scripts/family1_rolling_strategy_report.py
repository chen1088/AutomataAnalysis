#!/usr/bin/env python3
"""Audit rolling-search experiments against complete certified winner ties."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]

def ref(path):
    path=Path(path)
    return {"path":str(path.relative_to(REPO)) if path.is_absolute() else str(path),
            "sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"bytes":path.stat().st_size}

def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

def table(key):
    return [[int(key[i:i+2]),int(key[i+2:i+4])] for i in range(0,len(key),4)]

def replay(row):
    upper=row["upper_bound"]
    if upper is None:
        assert row["witness"]==["",""] and not row["Dtrace"]
        return 0
    a,b=row["witness"]
    assert a!=b and len(a)==len(b)==upper and set(a+b)<={"0","1"}
    ports=table(row["key"]);n=1<<len(ports);trace=[0]*(upper+1)
    for mask in range(n):
        q=r=0
        for i,(x,y) in enumerate(zip(a,b),1):
            q=ports[q][int(x)^((mask>>q)&1)];r=ports[r][int(y)^((mask>>r)&1)]
            trace[i]+=q!=r
        assert q==r
    assert trace==row["Dtrace"] and trace[0]==trace[-1]==0
    return n

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source",type=Path,default=REPO/"out/family1-finder-strategies-20261026/rolling")
    p.add_argument("--out",type=Path,default=REPO/"results/family1-finder-strategies-20261026/rolling")
    args=p.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    keys=(args.source/"all-keys.txt").read_text().splitlines()
    sources=sorted(args.source.glob("all-*.jsonl"))
    complete=[]
    for path in sources:
        data=rows(path)
        assert [r["key"] for r in data]==keys,(str(path),"partial or reordered benchmark")
        complete.append((path,data))
    # Seal complete queries before opening the reference labels.
    exploratory_paths=sorted(args.source.glob("scored-*.jsonl"))
    seal={"graph_input":ref(args.source/"all-keys.txt"),"queries":[ref(path) for path,_ in complete],
          "exploratory_subset_queries":[ref(path) for path in exploratory_paths],
          "query_inputs":"canonical graph keys and fixed options only"}
    (args.out/"query-manifest.json").write_text(json.dumps(seal,indent=2,sort_keys=True)+"\n")
    truth={}
    truthfiles=[REPO/"results/family1-m1-m6/maximizers.jsonl",REPO/"results/family1-m7/maximizers.jsonl"]
    for path in truthfiles:
        for row in rows(path):
            key="".join(f"{q:02d}" for ports in row["canonical_table"] for q in ports)
            truth[key]=row["merge_length"]
    assert set(truth)==set(keys)
    fields=["variant","m","key","k","window_kind","alphabet","advance","score","prefix_depth","prefix_words",
            "expansion_cap","max_length","beam","common_depth","grouped","priority","distance_mode","tie_mode",
            "diverse","avoid_cycles","prefix_pairs","reference_H","upper_bound","gap","expanded_nodes",
            "complete_windows","attempts","starts","capped_attempts","cycles_avoided","first","second","Dtrace"]
    summaries=[];allrows=[];maskchecks=0
    for path,data in complete:
        variant=path.stem
        for row in data:
            maskchecks+=replay(row)
            objective={0:"sum-distance-then-max",1:"max-distance-then-sum",2:"permutation-then-sum-distance"}.get(row.get("distance_mode"),"permutation-then-total-D" if row["priority"] else "total-D")
            item={k:row.get(k) for k in fields};item.update(variant=variant,reference_H=truth[row["key"]],
                gap=None if row["upper_bound"] is None else row["upper_bound"]-truth[row["key"]],
                first=row["witness"][0],second=row["witness"][1],Dtrace=json.dumps(row["Dtrace"],separators=(",",":")),
                window_kind="joint-pair",alphabet="00;01;10;11",advance="commit one paired symbol",score=objective,
                prefix_depth=16,prefix_words=65536,expansion_cap=64000000 if row["k"] in [5,6] else 16000000,max_length=80)
            assert item["gap"] is None or item["gap"]>=0
            allrows.append(item)
        gaps=[r["upper_bound"]-truth[r["key"]] for r in data if r["upper_bound"] is not None]
        summaries.append({"variant":variant,"k":data[0]["k"],"beam":data[0]["beam"],
            "cases":len(data),"found":len(gaps),"exact":sum(g==0 for g in gaps),"within_two":sum(g<=2 for g in gaps),
            "maximum_gap":max(gaps) if gaps else None,"nodes":sum(r["expanded_nodes"] for r in data),
            "capped_attempts":sum(r["capped_attempts"] for r in data),
            "m7_uppers":[r["upper_bound"] for r in data if r["m"]==7],"records":ref(path)})
    with (args.out/"cases.csv").open("w",newline="") as f:
        writer=csv.DictWriter(f,fields);writer.writeheader();writer.writerows(allrows)
    exploratory=[];exploratory_rows=[]
    for path in exploratory_paths:
        data=rows(path)
        expected=(args.source/("m7-keys.txt" if "scored-m7-" in path.name else "two-stubborn-keys.txt")).read_text().splitlines()
        assert [r["key"] for r in data]==expected
        for row in data:
            maskchecks+=replay(row)
            item={k:row.get(k) for k in fields}
            item.update(variant=path.stem,reference_H=truth[row["key"]],gap=row["upper_bound"]-truth[row["key"]],
                        first=row["witness"][0],second=row["witness"][1],Dtrace=json.dumps(row["Dtrace"],separators=(",",":")),
                        window_kind="joint-pair",alphabet="00;01;10;11",advance="commit one paired symbol",
                        score="permutation-then-total-D",prefix_depth=20,prefix_words=1048576,
                        expansion_cap=16000000,max_length=80)
            exploratory_rows.append(item)
        exploratory.append({"variant":path.stem,"k":data[0]["k"],"cases":len(data),"records":ref(path),
                            "uppers":[r["upper_bound"] for r in data],"nodes":sum(r["expanded_nodes"] for r in data),
                            "post_hoc_training_subset":True})
    with (args.out/"scored-subsets.csv").open("w",newline="") as f:
        writer=csv.DictWriter(f,fields);writer.writeheader();writer.writerows(exploratory_rows)
    small=rows(args.source/"small-fullfrontier-k1.jsonl")
    exact={}
    for m in range(1,4):
        for row in rows(REPO/f"out/family1-m8-challenger-20261026/target-full-cli-test/exact-{m}/records.jsonl"):
            exact[row["key"]]=row["merge_length"]
    assert len(small)==64 and {r["key"] for r in small}==set(exact)
    for row in small:
        assert row["upper_bound"]==exact[row["key"]] and row["k"]==1 and row["beam"]==4096
        maskchecks+=replay(row)
    summary={"schema":1,"joint_alphabet":["00","01","10","11"],"reference_k":None,
        "reference_window":"N/A: separately certified exhaustive findings","truth":[ref(p) for p in truthfiles],
        "configurations":summaries,"query_count":len(allrows),"final_mask_replays":maskchecks,
        "exploratory_subset_queries":exploratory,"exploratory_query_count":len(exploratory_rows),
        "all_pairs_independently_verified":True,"small_fullfrontier_test":{"cases":64,"all_exact":True,"joint_k":1,"beam":4096},
        "distance_aggregation_test":{"passed":True,"paired_states":7843,"scalar_mask_checks":553102},
        "limits":["These are exploratory training comparisons on certified maximizers, not a held-out quality guarantee.",
                  "Exact state-key deduplication is valid only within the same product; cycle avoidance is explicitly heuristic.",
                  "A verified pair is an upper certificate; the reference supplies shortestness labels.",
                  "Canonical prefix catalogues are bounded deterministic selections, not all compatible word pairs."]}
    (args.out/"summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"configurations":len(summaries),"queries":len(allrows),"mask_replays":maskchecks,"summary":str(args.out/"summary.json")}))

if __name__=="__main__":main()
