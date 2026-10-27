#!/usr/bin/env python3
"""Publish complete SAT and full-profile-cycle comparisons; references join last."""
from __future__ import annotations
import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def reference(path):
    return {"path":str(path.relative_to(REPO)),"bytes":path.stat().st_size,
            "sha256":hashlib.sha256(path.read_bytes()).hexdigest()}


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work",type=Path,default=REPO/"out/family1-finder-strategies-20261026/profile")
    parser.add_argument("--out",type=Path,default=REPO/"results/family1-finder-strategies-20261026/alternative")
    args=parser.parse_args()
    args.work=args.work.resolve();args.out=args.out.resolve()
    spec=importlib.util.spec_from_file_location("sat",REPO/"scripts/family1_sat_pair_experiment.py")
    sat=importlib.util.module_from_spec(spec);spec.loader.exec_module(sat)
    cases=rows(args.work/"cases.jsonl")
    bykey={row["key"]:row for row in cases}
    satpath=args.work/"onehot-final-matrix/records.jsonl"
    cyclepath=args.work/"cycles-final-matrix.jsonl"
    satrows,cyclerows=rows(satpath),rows(cyclepath)
    assert [row["key"] for row in satrows]==[case["key"] for case in cases]
    assert [row["key"] for row in cyclerows]==[case["key"] for case in cases]
    # Only after both query sets are complete, load the exact reference labels.
    truthpaths=[REPO/"results/family1-m1-m6/maximizers.jsonl",REPO/"results/family1-m7/maximizers.jsonl"]
    truth={}
    for path in truthpaths:
        for row in rows(path):
            key="".join(f"{q:02d}" for ports in row["canonical_table"] for q in ports)
            truth[key]=row["merge_length"]
    assert set(truth)==set(bykey)
    output=[];verification=0
    for method,values in [("SAT-CEGAR",satrows),("profile-cycle-BFS",cyclerows)]:
        for row in values:
            key=row["key"];upper=row["upper_bound"]
            trace=[]
            if upper is not None:
                trace,failed=sat.verify(bykey[key]["canonical_table"],*row["witness"])
                assert not failed and trace==row.get("witness_metric_trace",row.get("Dtrace"))
                assert upper==len(row["witness"][0]) and upper>=truth[key]
                verification+=1<<row["m"]
            output.append({"method":method,"m":row["m"],"key":key,"k":"N/A",
                           "reference_H":truth[key],"upper_bound":upper,
                           "gap":None if upper is None else upper-truth[key],
                           "query_minimality_certified":row.get("minimality_certified",False),
                           "first":row["witness"][0] if upper is not None else "",
                           "second":row["witness"][1] if upper is not None else "",
                           "D_trace":json.dumps(trace,separators=(",",":")) if trace else "",
                           "conflicts":row.get("total_conflicts"),
                           "propagations":row.get("total_propagations"),
                           "profiles":row.get("profiles"),"graph_edges":row.get("graph_edges"),
                           "return_edges":row.get("return_edges"),"state_capped":row.get("state_capped"),
                           "solver_statuses":json.dumps([[t["requested_length"],t["status"]] for t in row.get("attempts",[])],separators=(",",":")),
                           "observed_seconds":row["seconds"]})
    args.out.mkdir(parents=True,exist_ok=True)
    with (args.out/"cases.csv").open("w",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(output[0]));writer.writeheader();writer.writerows(output)
    summary=[]
    for method in ["SAT-CEGAR","profile-cycle-BFS"]:
        selected=[row for row in output if row["method"]==method]
        summary.append({"method":method,"k":None,"cases":len(selected),
                        "positive_count":sum(row["upper_bound"] is not None for row in selected),
                        "miss_count":sum(row["upper_bound"] is None for row in selected),
                        "matching_reference_count":sum(row["gap"]==0 for row in selected),
                        "largest_positive_gap":max(row["gap"] for row in selected if row["gap"] is not None),
                        "m6_m7_positive_count":sum(row["m"]>=6 and row["upper_bound"] is not None for row in selected),
                        "total_conflicts":sum(row["conflicts"] or 0 for row in selected),
                        "total_propagations":sum(row["propagations"] or 0 for row in selected),
                        "total_profiles":sum(row["profiles"] or 0 for row in selected),
                        "total_graph_edges":sum(row["graph_edges"] or 0 for row in selected)})
    sources=[REPO/"scripts/family1_sat_pair_experiment.py",REPO/"Family1ProfileCycles.h",REPO/"tests/Family1ProfileCyclesBenchmark.cpp",
             REPO/"scripts/family1_alternative_strategy_publish.py"]
    manifest={"schema":1,"k":None,"randomness":False,"reference_labels_joined_after_complete_queries":True,
              "comparisons":summary,"sat_limits":{"max_length":80,"conflicts_per_length":20000,"propagations_per_length":5000000,
                                                "encoding":"onehot+inverse-support","input_decisions_only":True,
                                                "initial_masks":"all permutation masks, else 0","refinement":"all failing masks in numeric order",
                                                "schedule":"powers of two to 80, then bracket/near-upper refinement"},
              "cycle_limits":{"max_states":262144,"max_roots":64,"max_length":80,"max_return_edges":10000000},
              "verification":{"final_positive_mask_replays":verification,"all_passed":True},
              "semantic_validation":json.loads((args.work/"semantic-validation.json").read_text()),
              "backend_build":json.loads((args.work/"native/build.json").read_text()),
              "query_sources":[reference(satpath),reference(cyclepath),reference(args.work/"cases.jsonl")],
              "truth_sources":[reference(path) for path in truthpaths],"source_files":[reference(path) for path in sources],
              "records":reference(args.out/"cases.csv"),
              "limits":["Neither alternative recovers the m6/m7 champions at these budgets.",
                        "Full-profile cycle BFS is bounded; unseen states/cycles are not excluded.",
                        "SAT UNKNOWN is a work-limit result, never UNSAT.",
                        "SAT query lower/minimality claims are CNF-solver conclusions; exact reference labels are independent.",
                        "Observed runtime was collected alongside other experiments and is not a controlled speed comparison."]}
    (args.out/"summary.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps(summary))


if __name__=="__main__":main()
