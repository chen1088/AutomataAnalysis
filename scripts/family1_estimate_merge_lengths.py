#!/usr/bin/env python3
"""Apply the requested L-1 estimate; publish every highest refined-point tie.

Certified scores, bounds and statuses are copied unchanged. Complete derivative
estimates, their finite ranking and unknowns are versioned under out/, while the
public result contains only the currently best estimated tier and its provenance.
"""
from __future__ import annotations
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

REPO = Path(__file__).resolve().parents[1]
ASSUMPTION = "User assumption: shortest merge length is approximately one or two below the verified finder length L; use point L-1 and rough band [L-2,L], clipped to certified bounds. This is not a validation guarantee."


def reference(path):
    path = Path(path).resolve()
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream,"sha256").hexdigest()
    return {"path":str(path),"sha256":digest,"bytes":path.stat().st_size}


def read_rows(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path,"rt",encoding="utf-8-sig") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def write_json(path,value):
    path.write_text(json.dumps(value,sort_keys=True,indent=2)+"\n",encoding="utf-8")


def write_rows(path,values):
    with path.open("wb") as raw:
        if str(path).endswith(".gz"):
            with gzip.GzipFile(filename="",mode="wb",fileobj=raw,mtime=0) as stream:
                for value in values:
                    stream.write((json.dumps(value,sort_keys=True,separators=(",",":"))+"\n").encode())
        else:
            for value in values:
                raw.write((json.dumps(value,sort_keys=True,separators=(",",":"))+"\n").encode())


def numerical_estimate(lower,upper,status,exact):
    assert type(lower) is int and lower>=1
    assert upper is None or (type(upper) is int and upper>=lower)
    if status=="exact":
        assert exact==lower==upper
        return {"point":exact,"band":[exact,exact],"method":"certified-exact-score","is_certified":True,"verified_finder_length":upper}
    if upper is None:
        return {"point":None,"band":None,"method":"no-verified-upper-no-estimate","is_certified":False,"verified_finder_length":None}
    return {"point":max(lower,upper-1),"band":[max(1,upper-2,lower),upper],
            "method":"user-assumed-one-or-two-below-verified-upper","is_certified":False,"verified_finder_length":upper}


def self_test():
    assert numerical_estimate(35,52,"bounded",None)["point"]==51
    assert numerical_estimate(35,52,"bounded",None)["band"]==[50,52]
    assert numerical_estimate(1,1,"exact",1)["band"]==[1,1]
    assert numerical_estimate(1,1,"exact",1)["point"]==1
    assert numerical_estimate(51,52,"bounded",None)["band"]==[51,52]
    assert numerical_estimate(35,None,"incomplete",None)["point"] is None
    assert numerical_estimate(35,None,"incomplete",None)["band"] is None
    try:
        numerical_estimate(53,52,"bounded",None)
    except AssertionError:
        pass
    else:
        raise AssertionError("Contradictory certificate interval accepted")


def verify_refined_witness(row):
    words=row.get("witness");upper=row.get("upper_bound")
    if upper is None:
        assert words is None
        return None
    assert isinstance(words,list) and len(words)==2 and words[0]!=words[1]
    assert len(words[0])==len(words[1])==upper and set(words[0]+words[1])<={"0","1"}
    table=row["canonical_table"];m=row["m"]
    for mask in range(1<<m):
        endpoints=[]
        for word in words:
            state=0
            for bit in word:state=table[state][int(bit)^((mask>>state)&1)]
            endpoints.append(state)
        assert endpoints[0]==endpoints[1],"Refined witness fails full static-mask replay."
    return {"method":"independent-postprocess-scalar-static-mask-replay","mask_count":1<<m,"passed":True}


def preserve_publication(public, archive_root):
    """Keep the complete preceding public view before replacing its leaders."""
    manifest=public/"manifest.json"
    if not manifest.is_file():
        return
    history=archive_root/"publication-history"/reference(manifest)["sha256"]
    history.mkdir(parents=True,exist_ok=True)
    for source in sorted(public.iterdir()):
        if not source.is_file():
            continue
        target=history/source.name
        if target.exists():
            assert target.read_bytes()==source.read_bytes(),"A preserved publication changed."
        else:
            shutil.copy2(source,target)


def build(args):
    source=args.input.resolve();public=args.out.resolve();archive_root=args.archive.resolve()
    assert public!=source.parent and archive_root!=source.parent,"Never write into the sealed source publication."
    source_reference=reference(source);script_reference=reference(Path(__file__))
    inputs_reference=reference(args.inputs)
    inputs=json.loads(args.inputs.read_text(encoding="utf-8-sig"))
    source_pins={item["sha256"]:item for item in inputs.get("records",[])}
    source_pins.update({item["sha256"]:item for item in inputs.get("observations",[])})
    original=list(read_rows(source));identities=[(r["m"],r["key"]) for r in original]
    assert len(set(identities))==len(original)
    records_by_identity={(r["m"],r["key"]):r for r in original}
    refinements={};refined_source_pins=[]
    for path in args.refined_records:
        source_pin=reference(path);refined_source_pins.append(source_pin)
        for row in read_rows(path):
            identity=(row["m"],row["key"])
            assert identity in records_by_identity,"Refined graph must first be present in the sealed graph corpus."
            assert row["canonical_table"]==records_by_identity[identity]["canonical_table"]
            validation=verify_refined_witness(row)
            refinements.setdefault(identity,[]).append({"source":source_pin,"upper_bound":row.get("upper_bound"),
                "witness":row.get("witness"),"upper_certificate":row.get("upper_certificate"),
                "refinement_sources":row.get("refinement_sources"),"verification":validation,
                "provenance":row.get("provenance",[]),"observations":row.get("observations",[]),
                "completed_k":row.get("completed_k"),"max_attempted_k":row.get("max_attempted_k")})
    budgets={identity:[] for identity,row in records_by_identity.items() if row["upper_bound"] is not None}
    if args.observations.is_file():
        for attempt in read_rows(args.observations):
            nested=attempt.get("attempt",{})
            observation=attempt.get("observation",nested.get("observation"))
            if observation is None and attempt.get("upper_bound") is not None:
                observation=attempt
            if not observation or observation.get("upper_bound") is None:
                continue
            graph=attempt.get("graph",nested.get("graph",observation))
            identity=(graph.get("m",observation.get("m",8)),graph.get("key",attempt.get("key",observation.get("key"))))
            if identity not in records_by_identity or observation["upper_bound"]!=records_by_identity[identity]["upper_bound"]:
                continue
            budgets[identity].append({"upper_bound":observation["upper_bound"],"length_cap":attempt.get("length_cap",nested.get("length_cap",observation.get("length_cap"))),
                "stage":attempt.get("stage",nested.get("stage")),
                "native_result":attempt.get("native_result",nested.get("native_result")),
                "native_configuration":attempt.get("native_configuration",nested.get("native_configuration")),
                "source_observation_file":source_pins.get(attempt.get("source_sha256")),
                "outcome":attempt.get("outcome",nested.get("outcome"))})
    estimates=[];unchanged=0
    for source_line,row in enumerate(original,1):
        m,key=row["m"],row["key"];table=row["canonical_table"]
        assert len(table)==m and all(len(t)==2 and all(type(v) is int and 0<=v<m for v in t) for t in table)
        assert "".join(f"{v:02d}" for t in table for v in t)==key
        lower,source_upper=row["lower_bound"],row["upper_bound"]
        row_refinements=refinements.get((m,key),[])
        eligible=bool(row_refinements)
        verified_lengths=[value for value in [source_upper,*[item["upper_bound"] for item in row_refinements]] if value is not None]
        upper=min(verified_lengths) if verified_lengths else None
        estimate=numerical_estimate(lower,upper,row["status"],row["merge_length"])
        upper_pins=[]
        if source_upper is not None:
            assert row["witness"] and len(row["witness"][0])==len(row["witness"][1])==source_upper
            certificates=row.get("upper_certificates")
            if certificates is not None:
                assert certificates and min(c["upper_bound"] for c in certificates)==source_upper
                for certificate in certificates:
                    if certificate["upper_bound"]==upper:
                        source_hash=certificate["source_sha256"]
                        assert source_hash in source_pins,"Upper certificate source is not pinned by the source publication."
                        upper_pins.append({"source_sha256":source_hash,"source_record_file":source_pins[source_hash],
                                           "upper_bound":upper,"verification":certificate.get("verification")})
            elif source_upper==upper:
                # Adaptive archives retain their witnesses and transitive source
                # provenance rather than the older publisher's certificate array.
                upper_pins.append({"source_sha256":source_reference["sha256"],"source_record_file":source_reference,
                                   "source_record_line":source_line,"upper_bound":upper,
                                   "upper_certificate":row.get("upper_certificate"),
                                   "provenance":row.get("provenance",[]),
                                   "observations":row.get("observations",[]),
                                   "verification":{"method":"imported-pinned-archive-witness"}})
        for item in row_refinements:
            if item["upper_bound"] is not None and item["upper_bound"]==upper:
                upper_pins.append({"source_sha256":item["source"]["sha256"],"source_record_file":item["source"],
                                   "upper_bound":upper,"verification":item["verification"],
                                   "upper_certificate":item["upper_certificate"],"refinement_sources":item["refinement_sources"],
                                   "provenance":item["provenance"],"observations":item["observations"],
                                   "completed_k":item["completed_k"],"max_attempted_k":item["max_attempted_k"]})
        if upper is not None:
            assert upper_pins
            assert lower<=estimate["band"][0]<=estimate["point"]<=estimate["band"][1]==upper
        else:
            assert estimate["point"] is None and estimate["band"] is None
        merged_witness=row["witness"] if source_upper==upper else next((item["witness"] for item in row_refinements if item["upper_bound"]==upper and upper is not None),None)
        result={**row,"estimated_merge_length":estimate["point"],"estimated_band":estimate["band"],
                "verified_finder_length":upper,"verified_finder_witness":merged_witness,
                "certificate_interval":[lower,source_upper],"merged_verified_interval":[lower,upper],
                "estimate_method":estimate["method"],"estimate_is_certified":estimate["is_certified"],
                "estimate_assumption":None if estimate["is_certified"] else ASSUMPTION,
                "refinement_eligible":eligible,
                "refinement_status":"refined" if eligible else "certified-exact" if row["status"]=="exact" else "coarse-pending-refinement" if upper is not None else "unknown-no-upper",
                "refined_record_sources":[item["source"] for item in row_refinements],
                "refinement_evaluation_count":sum(len(item["observations"]) for item in row_refinements),
                "upper_source_pins":upper_pins,"upper_budget_provenance":[item for item in budgets.get((m,key),[]) if item["upper_bound"]==upper]}
        # Every field in the original sealed record is retained verbatim.
        assert all(result[field]==value for field,value in row.items())
        unchanged+=1;estimates.append(result)
    estimates.sort(key=lambda row:(row["m"],row["key"]))
    finite=[r for r in estimates if r["estimated_merge_length"] is not None]
    finite.sort(key=lambda row:(-row["estimated_merge_length"],-row["verified_finder_length"],row["m"],row["key"]))
    ranked=[{**row,"estimate_rank":index+1} for index,row in enumerate(finite)]
    unknown=[r for r in estimates if r["estimated_merge_length"] is None]
    refined_finite=[r for r in finite if r["refinement_eligible"]]
    pending=[r for r in finite if not r["refinement_eligible"] and r["status"]!="exact"]
    best_point=max((r["estimated_merge_length"] for r in refined_finite),default=None)
    best=[r for r in refined_finite if r["estimated_merge_length"]==best_point]
    version=hashlib.sha256(json.dumps({"script":script_reference["sha256"],"refined":refined_source_pins},sort_keys=True).encode()).hexdigest()[:12]
    archive=archive_root/(source_reference["sha256"][:16]+"-"+version)
    archive.mkdir(parents=True,exist_ok=True);public.mkdir(parents=True,exist_ok=True)
    preserve_publication(public,archive_root)
    write_rows(archive/"all-estimates.jsonl.gz",estimates)
    write_rows(archive/"ranked-finite-estimates.jsonl.gz",ranked)
    write_rows(archive/"unknown-estimates.jsonl.gz",unknown)
    write_rows(archive/"pending-refinement.jsonl.gz",pending)
    write_rows(archive/"ranked-refined-estimates.jsonl.gz",refined_finite)
    audit={"schema":1,"all_original_fields_preserved_records":unchanged,"source_record_count":len(original),
           "all_points_and_bands_inside_certified_interval":True,"exact_scores_kept_exact":sum(r["status"]=="exact" for r in estimates),
           "unknown_estimates_are_null":len(unknown),"unknown_is_not_infinity_or_active_best":True,
           "all_highest_refined_estimate_ties_retained":True,"refined_eligible_records":len(refined_finite),
           "refined_finite_witnesses_independently_scalar_replayed":sum(item["upper_bound"] is not None for items in refinements.values() for item in items),
           "synthetic_exact1_unknown_clipping_contradiction_tests":"passed"}
    write_json(archive/"audit.json",audit)
    archive_manifest={"schema":1,"input":source_reference,"source_inputs":inputs_reference,"script":script_reference,"refined_record_inputs":refined_source_pins,
        "observation_input":reference(args.observations) if args.observations.is_file() else None,
        "files":{p.name:reference(p) for p in sorted(archive.iterdir()) if p.is_file() and p.name!="manifest.json"}}
    write_json(archive/"manifest.json",archive_manifest)
    write_rows(public/"best-candidates.jsonl",best)
    best_length=max((r["verified_finder_length"] for r in best),default=None)
    summary={"schema":1,"selection":"all ties for highest requested estimated point among explicitly refined eligible graphs with verified finite upper bounds",
             "assumption":ASSUMPTION,"best_estimated_point":best_point,"best_tie_count":len(best),
             "best_keys":[r["key"] for r in best],"best_verified_finder_lengths":[r["verified_finder_length"] for r in best],
             "best_estimated_bands":[r["estimated_band"] for r in best],"input_record_count":len(original),
             "finite_estimate_count":len(finite),"unknown_estimate_count_archived":len(unknown),
             "refined_eligible_count":len(refinements),"refined_eligible_finite_count":len(refined_finite),
             "refined_record_inputs":refined_source_pins,"coarse_pending_refinement_count":len(pending),
             "pending_larger_upper_count":sum(r["verified_finder_length"]>best_length for r in pending) if best_length is not None else len(pending),
             "certified_bounds_scores_and_statuses_changed":False,"global_maximum_claimed":False,
             "full_derivative_archive":reference(archive/"manifest.json"),"input":source_reference,"script":script_reference}
    write_json(public/"summary.json",summary)
    write_json(public/"manifest.json",{"schema":1,"input":source_reference,"source_inputs":inputs_reference,"script":script_reference,
               "refined_record_inputs":refined_source_pins,
               "archive_manifest":reference(archive/"manifest.json"),
               "files":{name:reference(public/name) for name in ["best-candidates.jsonl","summary.json"]}})
    assert reference(source)==source_reference,"Sealed source changed during postprocessing."
    return summary,archive


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",type=Path,default=REPO/"results/family1-m8-search/records.jsonl.gz")
    parser.add_argument("--inputs",type=Path,default=REPO/"results/family1-m8-search/inputs.json")
    parser.add_argument("--observations",type=Path,default=REPO/"results/family1-m8-search/observations.jsonl.gz")
    parser.add_argument("--out",type=Path,default=REPO/"results/family1-m8-estimates")
    parser.add_argument("--archive",type=Path,default=REPO/"out/family1-m8-estimates-archive")
    parser.add_argument("--refined-records",type=Path,action="append",help="Explicit source of graphs eligible for active estimates; repeat for additional refinement batches.")
    args=parser.parse_args()
    defaults=[REPO/"results/family1-m8-upper-refinement/records.jsonl",REPO/"results/family1-m8-fresh-prefix-refinement/records.jsonl"]
    args.refined_records=sorted(set(path.resolve() for path in defaults+(args.refined_records or [])))
    self_test();summary,archive=build(args)
    print(json.dumps({"best_estimated_point":summary["best_estimated_point"],"best_tie_count":summary["best_tie_count"],
                      "best_keys":summary["best_keys"],"archive":str(archive)},indent=2))


if __name__=="__main__":main()
