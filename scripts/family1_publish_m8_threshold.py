#!/usr/bin/env python3
"""Publish bounded m8 threshold probes and independently check clone projections."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def reference(path):
    path = Path(path).resolve()
    return {"path":path.relative_to(REPO).as_posix(),"sha256":hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    output = REPO/"results/family1-m8-threshold-probes"
    output.mkdir(parents=True,exist_ok=True)
    probes=[];sources=[]
    for name in ["family1-m8-threshold34-calibration","family1-m8-threshold34-full"]:
        folder=REPO/"out"/name
        sources.append({"run":reference(folder/"run.json"),"summary":reference(folder/"summary.json")})
        for line in (folder/"observations.jsonl").read_text().splitlines():
            record=json.loads(line)
            native_path=REPO/record["native_result"]["path"]
            assert reference(native_path)==record["native_result"]
            record["batch"]=name;probes.append(record)
    proofs=[]
    base_summary=json.loads((REPO/"results/family1-m7/summary.json").read_text())
    assert base_summary["maximum_value_certified"] and base_summary["maximum_merge_length"]==34
    graph_source=REPO/"results/family1-edit-priority/root-lift-candidates.jsonl"
    for line in graph_source.read_text().splitlines():
        record=json.loads(line)
        if record["m"]!=8:continue
        construction=record["construction"]
        assert construction["base_key"] in base_summary["maximizer_keys"]
        flat=[int(construction["base_key"][i:i+2]) for i in range(0,28,2)]
        base=list(zip(flat[::2],flat[1::2]));child=record["canonical_table"]
        projection=construction["canonical_projection_to_base"]
        flips=construction["canonical_mask_lift_xor"]
        assert len(projection)==len(flips)==8 and projection[0]==0
        checks=0
        for mask in range(128):
            lift=sum((((mask>>projection[s])&1)^flips[s])<<s for s in range(8))
            for state in range(8):
                for bit in range(2):
                    child_next=child[state][bit^((lift>>state)&1)]
                    base_next=base[projection[state]][bit^((mask>>projection[state])&1)]
                    assert projection[child_next]==base_next
                    checks+=1
        proofs.append({"key":record["key"],"lower_bound":34,"base_key":construction["base_key"],
                       "projection":projection,"mask_lift_xor":flips,"static_transition_checks":checks,
                       "root_preserved":True,"all_checks_passed":True,
                       "source":reference(graph_source),"base_certificate":reference(REPO/"results/family1-m7/summary.json")})
    (output/"observations.jsonl").write_text("".join(json.dumps(r,separators=(",",":"))+"\n" for r in probes),encoding="utf-8")
    (output/"clone-projection-validation.json").write_text(json.dumps(proofs,indent=2)+"\n",encoding="utf-8")
    summary={"schema":1,"fixed_length":34,"queries":len(probes),
             "decisions":{decision:sum(r["decision"]==decision for r in probes) for decision in ["collision","no_collision","unknown"]},
             "sources":sources,"certified_H_ge35_from_these_SAT_queries":False,
             "clone_lower34_independently_validated":len(proofs),"global_maximum_claimed":False}
    (output/"summary.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    lines=["# Eight-state fixed-length SAT probes","",
           "All26 length-34 queries returned UNKNOWN. They establish neither a collision nor H≥35. The two cloning baselines retain their separately verified H≥34; the bounded SAT queries do not strengthen those bounds.","",
           "The calibration queries cover the first4 roots of the two selected edit shapes, each with16 and32 initial masks,15s aggregate/5s per-solve budgets,128 refinements and4 workers. The full batch covers all16 roots of those two shapes plus2 cloning-baseline roots, with32 initial masks and15s aggregate/per-solve budgets. It completed in75.358s wall time. Actual mask sets,0–1 refinement counts, reasons, timings and every native JSON/configuration hash are retained.","",
           "The cloning lower bounds were independently rechecked by4096 static transition tests:128 base masks ×8 child states ×2 input letters for each of the two roots. The projection preserves root0 and commutes with every transition under the explicitly lifted, fixed mask. Thus any equal-length collision in the child would also be one in the certified seven-state base, proving H(child)≥34. This is a per-graph lower bound and says nothing about global optimality at eight states.","",
           "Fixed-length semantics: no_collision at34 would exclude every earlier positive collision because a shorter pair can be extended by a common suffix. A collision would provide an upper bound34 and would be independently replayed over all256 masks. UNKNOWN adds no score bound. None of these queries returned a positive or negative SAT certificate.","",
           "`observations.jsonl` retains all graph tables, settings, decisions and native provenance; `clone-projection-validation.json` records the independently verified lifted-mask construction. The separate partitioned-layer verifier is independent work and its later results are not implied by this SAT report.","",
           "```powershell",
           "uv run --no-project python scripts/family1_m8_threshold.py --out out/family1-m8-threshold34-full-repeat --max-graphs 16 --projection-masks 32 --include-baseline --solve-timeout-ms 15000",
           "uv run --no-project python scripts/family1_publish_m8_threshold.py",
           "```",""]
    (output/"README.md").write_text("\n".join(lines),encoding="utf-8")
    print(json.dumps(summary,indent=2))


if __name__=="__main__":main()
