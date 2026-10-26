#!/usr/bin/env python3
"""Preserve exact fixed-length queries on eight-state candidate graph classes."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

from family1_study import canonical_table, fixed_key, validate_table

REPO = Path(__file__).resolve().parents[1]


def reference(path):
    path = Path(path).resolve()
    try:
        name = path.relative_to(REPO).as_posix()
    except ValueError:
        name = str(path)
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"path": name, "sha256": digest}


def dump(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2)+"\n", encoding="utf-8")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=REPO / "out/family1-edit-candidate-pilot-8-20/m8/ranked/candidates.jsonl")
    parser.add_argument("--exe", type=Path, default=REPO / "out/build/msvc-vcpkg/Release/Family1Threshold.exe")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--shapes", type=int, default=2)
    parser.add_argument("--max-graphs", type=int, default=16)
    parser.add_argument("--include-baseline", action="store_true")
    parser.add_argument("--length", type=int, default=34)
    parser.add_argument("--projection-masks", type=int, nargs="+", default=[16,32])
    parser.add_argument("--timeout-ms", type=int, default=15000)
    parser.add_argument("--solve-timeout-ms", type=int, default=5000)
    parser.add_argument("--max-refinements", type=int, default=128)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    assert 1 <= args.jobs <= 32 and 1 <= args.length <= 4096
    assert args.max_graphs >= 1 and all(1 <= p <= 64 for p in args.projection_masks)
    output = args.out.resolve(); output.mkdir(parents=True, exist_ok=True)
    selected, shapes, seen = [], [], set()
    for line in args.input.read_text(encoding="utf-8-sig").splitlines():
        row = json.loads(line)
        if row["m"] != 8:
            continue
        shape = row.get("shape_key", row["key"])
        if shape not in shapes:
            if len(shapes) == args.shapes:
                continue
            shapes.append(shape)
        raw = validate_table(row["canonical_table"])
        table = canonical_table(raw); key = fixed_key(table)
        assert table == raw and key == row["key"]
        if key not in seen:
            selected.append({"m": 8, "key": key, "canonical_table": table,
                             "shape_key": shape, "source": "ranked-edit-candidate"})
            seen.add(key)
    available = len(selected)
    selected = selected[:args.max_graphs]
    if args.include_baseline:
        for line in (REPO / "results/family1-edit-priority/root-lift-candidates.jsonl").read_text().splitlines():
            row = json.loads(line)
            if row["m"] == 8 and row["key"] not in {r["key"] for r in selected}:
                selected.append({"m": 8, "key": row["key"], "canonical_table": row["canonical_table"],
                                 "shape_key": None, "source": "certified-H-ge34-cloning-baseline",
                                 "imported_lower_bound": 34, "construction": row["construction"]})
    binary = output / "binary"; binary.mkdir(exist_ok=True)
    executable = binary / args.exe.name
    if executable.exists():
        assert reference(executable)["sha256"] == reference(args.exe)["sha256"]
    else:
        shutil.copy2(args.exe, executable)
    for dll in args.exe.parent.glob("*.dll"):
        if not (binary/dll.name).exists():
            shutil.copy2(dll, binary/dll.name)
    config = {"schema": 1, "input": reference(args.input), "exe": reference(executable),
              "driver": reference(Path(__file__)), "length": args.length,
              "projection_masks": sorted(set(args.projection_masks)), "timeout_ms": args.timeout_ms,
              "solve_timeout_ms": args.solve_timeout_ms, "max_refinements": args.max_refinements,
              "shapes_selected": shapes, "ranked_roots_available": available,
              "ranked_roots_selected": min(available, args.max_graphs), "graphs": selected,
              "global_optimality_claimed": False}
    config = json.loads(json.dumps(config))
    if (output/"run.json").exists():
        assert args.resume and json.loads((output/"run.json").read_text()) == config
    else:
        assert not args.resume
        dump(output/"run.json", config)
    results = []
    started = time.perf_counter()

    def query(graph, masks):
        directory = output/"queries"/graph["key"]/f"L{args.length}-P{masks}"
        command = [str(executable), "--graph", graph["key"], "--length", str(args.length),
                   "--out", str(directory), "--timeout-ms", str(args.timeout_ms),
                   "--solve-timeout-ms", str(args.solve_timeout_ms), "--projection-masks", str(masks),
                   "--max-refinements", str(args.max_refinements)]
        if (directory/"run.json").exists():
            command.append("--resume")
        before = time.perf_counter()
        completed = subprocess.run(command, cwd=REPO, capture_output=True, text=True,
                                   timeout=max(60,args.timeout_ms/1000+30))
        if completed.returncode:
            raise RuntimeError(completed.stderr[-2000:])
        native_path = directory/"result.json"
        native = json.loads(native_path.read_bytes())
        assert json.loads(completed.stdout) == native
        native_ref = reference(native_path)
        assert (directory/"result.sha256").read_text().strip() == native_ref["sha256"]
        config_bytes = (directory/"run.json").read_bytes().removesuffix(b"\n")
        assert hashlib.sha256(config_bytes).hexdigest() == native["config_sha256"]
        assert native["key"] == graph["key"] and native["m"] == 8 and native["length"] == args.length
        assert native["canonical_table"] == [list(row) for row in graph["canonical_table"]]
        decision = native["decision"]
        expected = {"collision": (1,args.length), "no_collision": (args.length+1,None), "unknown": (1,None)}
        assert (native["lower_bound"],native["upper_bound"]) == expected[decision]
        verified = None
        if decision == "collision":
            words = native["witness"]
            assert words[0] != words[1] and len(words[0]) == len(words[1]) == args.length
            products = [[], []]
            for mask in range(256):
                for side, word in enumerate(words):
                    state = 0
                    for bit in word:
                        state = graph["canonical_table"][state][int(bit)^((mask>>state)&1)]
                    products[side].append(state)
            assert products[0] == products[1] and native["scalar_witness_masks_verified"] == 256
            verified = {"masks_verified": 256, "first_product_state": products[0], "second_product_state": products[1]}
        else:
            assert native["witness"] is None
        return {"key": graph["key"], "m": 8, "length": args.length, "projection_masks": masks,
                "decision": decision, "lower_bound": max(native["lower_bound"],graph.get("imported_lower_bound",1)),
                "upper_bound": native["upper_bound"], "native_seconds": native["seconds"],
                "invocation_seconds": time.perf_counter()-before, "reason": native["reason"],
                "native_result": native_ref, "native_configuration": reference(directory/"run.json"),
                "native_answer": native, "independent_collision_verification": verified, "command": command,
                "source_graph": graph, "no_global_optimality_claim": True}

    def export():
        ordered = sorted(results,key=lambda r:(r["key"],r["projection_masks"]))
        (output/"observations.jsonl").write_text("".join(json.dumps(r,separators=(",",":"))+"\n" for r in ordered))
        counts = {decision: sum(r["decision"]==decision for r in ordered) for decision in ["collision","no_collision","unknown"]}
        dump(output/"summary.json", {"schema":1,"query_count":len(ordered),"requested_queries":len(selected)*len(set(args.projection_masks)),
              "decisions":counts,"completed_all_queries":len(ordered)==len(selected)*len(set(args.projection_masks)),
              "whole_batch_seconds":time.perf_counter()-started,"maximum_certified_lower_bound":max([1]+[r["lower_bound"] for r in ordered]),
              "exact_score_or_global_maximum_claimed":False,"input_configuration":reference(output/"run.json")})
    with ThreadPoolExecutor(max_workers=args.jobs) as workers:
        futures = [workers.submit(query, graph, masks) for graph in selected for masks in sorted(set(args.projection_masks))]
        for future in as_completed(futures):
            result = future.result(); results.append(result); export()
            print(json.dumps({k:result[k] for k in ["key","projection_masks","decision","lower_bound","upper_bound","native_seconds","reason"]}),flush=True)
    print(json.dumps(json.loads((output/"summary.json").read_text()),indent=2))


if __name__ == "__main__":
    main()
