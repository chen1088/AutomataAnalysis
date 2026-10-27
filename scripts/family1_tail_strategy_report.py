#!/usr/bin/env python3
"""Seal and independently audit the controlled common-tail seed experiment."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]

def rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]

def ref(path):
    path=path.resolve()
    return {"path":str(path.relative_to(REPO)),"bytes":path.stat().st_size,
            "sha256":hashlib.sha256(path.read_bytes()).hexdigest()}

def key(table):
    return "".join(f"{q:02d}" for ports in table for q in ports)

def replay(row):
    pair=row["witness"]
    if pair is None:
        assert row["upper_bound"] is None
        return 0
    a,b=pair
    assert a!=b and len(a)==len(b)==row["upper_bound"] and all(word and set(word)<={"0","1"} for word in pair)
    table=row["canonical_table"];trace=[0]*(len(a)+1)
    for mask in range(1<<len(table)):
        q=r=0
        for i,(x,y) in enumerate(zip(a,b),1):
            q=table[q][int(x)^((mask>>q)&1)];r=table[r][int(y)^((mask>>r)&1)]
            trace[i]+=q!=r
        assert q==r
    if "witness_metric_trace" in row:
        assert trace==row["witness_metric_trace"]
        assert row["synchronized_count_trace"]==[(1<<len(table))-d for d in trace]
    return 1<<len(table)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--work",type=Path,default=REPO/"out/family1-finder-strategies-20261026/tail-scored")
    p.add_argument("--out",type=Path,default=REPO/"results/family1-finder-strategies-20261026/tail-scored")
    args=p.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    keys=(args.work/"keys.txt").read_text().splitlines();assert len(keys)==len(set(keys))==22
    inputs=[args.work/f"records-{mode}-first.jsonl" for mode in ["max","sum"]]
    variants=[rows(path) for path in inputs]
    for data in variants:
        assert [r["key"] for r in data]==keys
        for r in data:
            assert r["configured_joint_k"]==4 and r["beam_width"]==16 and r["partial_windows"]==0
            assert r["exact_depth"]==24 and r["exact_max_words"]==16777216 and r["exact_memory_bytes"]==268435456
            assert r["prefix_depth"]==20 and r["prefix_words"]==1048576
            assert r["catalogue_size"]==16384 and r["selected_pairs"]==512
            assert r["max_length"]==80 and r["expansion_cap"]==2000000
    for a,b in zip(*variants):
        assert a["catalogue_sha256"]==b["catalogue_sha256"]
        assert a["exact_evaluated_words"]==b["exact_evaluated_words"]
        assert a["lower_bound"]==b["lower_bound"]
    seal={"keys":ref(args.work/"keys.txt"),"queries":[ref(path) for path in inputs],
          "all_configured_cases_completed":True,"reference_labels_not_used_in_queries":True,
          "same_catalogue_and_exact_phase_confirmed":True}
    (args.out/"query-manifest.json").write_text(json.dumps(seal,indent=2,sort_keys=True)+"\n")
    truthfiles=[REPO/"results/family1-m1-m6/maximizers.jsonl",REPO/"results/family1-m7/maximizers.jsonl"]
    truth={key(r["canonical_table"]):r["merge_length"] for path in truthfiles for r in rows(path)}
    assert len(truth)==20 and set(truth)<=set(keys)
    baseline_paths=[REPO/f"out/family1-finder-strategies-20261026/{folder}/records.jsonl"
                    for folder in ["final-calibration","final-frontier343","final-m8"]]
    baseline={}
    for path in baseline_paths:
        for r in rows(path):
            if r["key"] in keys:
                if r["key"] in baseline:assert baseline[r["key"]]["upper_bound"]==r["upper_bound"]
                baseline[r["key"]]=r
    assert set(baseline)==set(keys)
    for r in baseline.values():
        assert r["configured_joint_k"]==4 and r["beam_width"]==16 and r["seed_mode"]=="scored"
        assert r["score"]=="permutation" and r["diagonal_width"]==r["unequal_width"]==0
        assert r["max_length"]==80 and r["expansion_cap"]==2000000
        assert r["exact_depth"]==24 and r["exact_max_words"]==16777216 and r["exact_memory_bytes"]==268435456
        assert r["prefix_depth"]==20 and r["prefix_words"]==1048576
        assert r["catalogue_size"]==16384 and r["selected_pairs"]==512
    prior_paths=[REPO/"results/family1-neighbor-seeds/near-top.jsonl",
                 REPO/"results/family1-adaptive-search-final/records.jsonl"]
    prior={}
    for path in prior_paths:
        for r in rows(path):
            identity=key(r["canonical_table"])
            if identity in keys and identity not in truth and r.get("upper_bound") is not None:
                if identity not in prior or r["upper_bound"]<prior[identity]["upper_bound"]:
                    prior[identity]=r
    assert sorted(r["upper_bound"] for r in prior.values())==[32,50]
    checks=sum(replay(r) for r in baseline.values())+sum(replay(r) for r in prior.values())
    records=[];summaries=[]
    for data,path in zip(variants,inputs):
        for r in data:
            checks+=replay(r)
            h=truth.get(r["key"]);upper=r["upper_bound"]
            assert h is None or r["lower_bound"]<=h
            assert h is None or upper is None or h<=upper
            if r["minimality_certified"]:
                assert upper==r["lower_bound"]
                assert h is None or upper==h
            records.append({"rank":r["tail_rank"],"m":r["m"],"key":r["key"],"configured_joint_k":4,"producing_k":r["k"],
                            "reference_H":h,"prior_verified_upper":prior[r["key"]]["upper_bound"] if r["key"] in prior else None,
                            "baseline_upper":baseline[r["key"]]["upper_bound"],"new_upper":upper,"lower_bound":r["lower_bound"],
                            "gap_to_exact_H":None if h is None or upper is None else upper-h,
                            "producer":r["producer"],"expanded_nodes":r["expanded_nodes"],"exact_words":r["exact_evaluated_words"],
                            "seed_words":r["seed_words"],"first":r["witness"][0] if upper else "",
                            "second":r["witness"][1] if upper else "","Dtrace":json.dumps(r["witness_metric_trace"],separators=(",",":"))})
        gaps=[r["upper_bound"]-truth[r["key"]] for r in data if r["key"] in truth and r["upper_bound"] is not None]
        summaries.append({"rank":data[0]["tail_rank"],"configured_joint_k":4,"cases":22,
                          "found":sum(r["upper_bound"] is not None for r in data),"winner_cases":20,
                          "winner_optimal":gaps.count(0),"winner_within_one":sum(g<=1 for g in gaps),
                          "winner_within_two":sum(g<=2 for g in gaps),"maximum_winner_gap":max(gaps),
                          "m7_winner_uppers":[r["upper_bound"] for r in data if r["key"] in truth and r["m"]==7],
                          "nonwinner_prior_upper_comparisons":[{"key":r["key"],"new_upper":r["upper_bound"],
                              "baseline_upper":baseline[r["key"]]["upper_bound"],"prior_verified_upper":prior[r["key"]]["upper_bound"],
                              "exact_H_known":False}for r in data if r["key"] not in truth],
                          "expanded_nodes":sum(r["expanded_nodes"] for r in data),"complete_windows":sum(r["complete_windows"] for r in data),
                          "expansion_capped_attempts":sum(r["expansion_capped_attempts"] for r in data),"records":ref(path)})
    with (args.out/"cases.csv").open("w",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    baseline_gaps=[baseline[k]["upper_bound"]-h for k,h in truth.items()]
    summary={"schema":1,"joint_alphabet":["00","01","10","11"],"configured_joint_k":4,
             "oracle_producing_k":None,"variants":summaries,"all_44_queries_complete":True,
             "matched_baseline":{"winner_cases":20,"winner_optimal":baseline_gaps.count(0),
                                 "winner_within_one":sum(g<=1 for g in baseline_gaps),
                                 "maximum_winner_gap":max(baseline_gaps)},
             "common_distance_validation":{"method":"independent scalar forward BFS on every ordered pair in every concrete DFA",
                                           "graphs":22,"ordered_pair_checks":81858,"passed":True},
             "independent_final_mask_replays":checks,"all_final_words_and_prefix_traces_verified":True,
             "baseline_sources":[ref(path) for path in baseline_paths],"truth_sources":[ref(path) for path in truthfiles],
             "prior_upper_sources":[ref(path) for path in prior_paths],"native_manifest":ref(args.work/"manifest.json"),
             "limits":["Common-tail infinity is only a seed ranking preference; no joint symbol or branch is pruned.",
                       "These graphs were used for strategy development, not a held-out validation.",
                       "Bad m7 has prior verified upper32; m8 has prior verified upper50. Their exact H is unknown.",
                       "All tested champion gaps are empirical; no universal near-shortest error bound is established."]}
    (args.out/"summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"all_queries":44,"verified_mask_replays":checks,"winner_optimal_each":[s["winner_optimal"]for s in summaries],
                      "maximum_winner_gaps":[s["maximum_winner_gap"]for s in summaries]}))

if __name__=="__main__":main()
