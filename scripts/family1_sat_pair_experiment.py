#!/usr/bin/env python3
"""Deterministic SAT/CEGAR hard-pair experiment (k=N/A).

MiniSat 2.2 is compiled locally after removing its RNG implementation and all
RNG calls. Budgets count conflicts/propagations, never elapsed time. This
experimental solver takes graph tables only; reference answers are not inputs.
"""
from __future__ import annotations
import argparse
from array import array
import ctypes as C
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import time

REPO = Path(__file__).resolve().parents[1]
WRAPPER = r'''
#include "core/Solver.h"
#include <cstdint>
using namespace Minisat;
extern "C" {
void* sp_new(int phases) {
    auto* s = new Solver; s->verbosity=0; s->random_var_freq=0;
    s->rnd_pol=false; s->rnd_init_act=false; s->phase_saving=phases;
    return s;
}
void sp_del(void* p) { delete static_cast<Solver*>(p); }
void sp_add(void* p, const int* data, int count, int variables) {
    auto& s=*static_cast<Solver*>(p);
    while(s.nVars()<variables) s.newVar();
    vec<Lit> clause;
    for(int i=0;i<count;++i) {
        if(data[i]) { int x=data[i]; clause.push(mkLit((x<0?-x:x)-1,x<0)); }
        else { s.addClause(clause); clause.clear(); }
    }
}
int sp_solve(void* p, std::int64_t conflicts, std::int64_t props) {
    auto& s=*static_cast<Solver*>(p); s.setConfBudget(conflicts); s.setPropBudget(props);
    vec<Lit> assumptions; auto result=s.solveLimited(assumptions);
    return result==l_True?1:result==l_False?0:-1;
}
int sp_value(void* p,int variable) {
    auto& s=*static_cast<Solver*>(p); return s.modelValue(variable-1)==l_True;
}
void sp_inputs_only(void* p,int count) {
    auto& s=*static_cast<Solver*>(p);
    for(int q=0;q<s.nVars();++q) s.setDecisionVar(q,q<count);
}
std::uint64_t sp_stat(void* p,int which) {
    auto& s=*static_cast<Solver*>(p);
    switch(which) {
      case 0:return s.conflicts; case 1:return s.propagations;
      case 2:return s.decisions; case 3:return s.starts;
      case 4:return s.nVars();case 5:return s.nClauses();case 6:return s.rnd_decisions;
    } return 0;
}
}
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(archive, out):
    out.mkdir(parents=True, exist_ok=True)
    source = out / "minisat"
    if not source.exists():
        with tarfile.open(archive) as package:
            package.extractall(out, filter="data")
    cc, header = source / "core/Solver.cc", source / "core/Solver.h"
    value = cc.read_text()
    value = value.replace("rnd_init_act ? drand(random_seed) * 0.00001 : 0", "0")
    start = value.find("    // Random decision:")
    end = value.find("    // Activity based decision:", start)
    if start >= 0:
        value = value[:start] + "    // Random choices are compiled out.\n" + value[end:]
    value = value.replace("rnd_pol ? drand(random_seed) < 0.5 : polarity[next]", "polarity[next]")
    cc.write_text(value)
    value = header.read_text()
    start = value.find("    // Returns a random float")
    if start >= 0:
        end = value.index("\n};", start)
        value = value[:start] + value[end:]
    header.write_text(value)
    assert all("drand(" not in p.read_text() and "irand(" not in p.read_text() for p in [cc, header])
    wrapper = out / "wrapper.cpp"
    wrapper.write_text(WRAPPER)
    library = out / "libdeterministic_minisat.so"
    command = ["g++", "-O3", "-std=c++11", "-fPIC", "-shared", "-fpermissive",
               "-I", str(source), str(wrapper), str(cc),
               str(source / "utils/Options.cc"), str(source / "utils/System.cc"),
               "-o", str(library)]
    subprocess.run(command, check=True, capture_output=True)
    manifest = {"archive": str(archive), "archive_sha256": sha(archive),
                "patched_solver_sha256": sha(cc), "patched_header_sha256": sha(header),
                "wrapper_sha256": sha(wrapper), "library_sha256": sha(library),
                "random_calls_compiled_out": True, "command": command}
    (out / "build.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return library


class Solver:
    def __init__(self, library, phases=2):
        self.lib = C.CDLL(str(library.resolve()))
        self.lib.sp_new.argtypes = [C.c_int]; self.lib.sp_new.restype = C.c_void_p
        self.lib.sp_del.argtypes = [C.c_void_p]
        self.lib.sp_add.argtypes = [C.c_void_p, C.POINTER(C.c_int), C.c_int, C.c_int]
        self.lib.sp_solve.argtypes = [C.c_void_p, C.c_int64, C.c_int64]; self.lib.sp_solve.restype = C.c_int
        self.lib.sp_value.argtypes = [C.c_void_p, C.c_int]; self.lib.sp_value.restype = C.c_int
        self.lib.sp_inputs_only.argtypes = [C.c_void_p, C.c_int]
        self.lib.sp_stat.argtypes = [C.c_void_p, C.c_int]; self.lib.sp_stat.restype = C.c_uint64
        self.ptr = self.lib.sp_new(phases); self.variables = 0; self.pending = array("i"); self.clauses = 0
        self.decision_prefix = None
    def close(self):
        if self.ptr:
            self.lib.sp_del(self.ptr); self.ptr = None
    def new(self):
        self.variables += 1; return self.variables
    def clause(self, values):
        self.pending.extend(values); self.pending.append(0); self.clauses += 1
    def flush(self):
        if self.pending:
            data = (C.c_int * len(self.pending)).from_buffer(self.pending)
            self.lib.sp_add(self.ptr, data, len(self.pending), self.variables)
            if self.decision_prefix is not None:
                self.lib.sp_inputs_only(self.ptr, self.decision_prefix)
            del data; self.pending = array("i")
    def stats(self):
        return {name: int(self.lib.sp_stat(self.ptr, i)) for i, name in enumerate(
            ["conflicts", "propagations", "decisions", "restarts", "variables", "active_clauses", "random_decisions"])}
    def solve(self, conflicts, props):
        self.flush(); return self.lib.sp_solve(self.ptr, conflicts, props)
    def value(self, v):
        return self.lib.sp_value(self.ptr, v)


def base_formula(solver, length, different_prefix=0):
    u = [solver.new() for _ in range(length)]
    prefix = min(length, different_prefix or length)
    v = [solver.new() for _ in range(prefix)] + u[prefix:]
    truth = solver.new(); solver.clause([truth])
    solver.clause([-u[0]])  # Safe simultaneous input complement for the full mask family.
    equal = truth
    differences = []
    for a, b in zip(u, v):
        d = solver.new(); differences.append(d)
        for clause in [[-a,-b,-d],[a,b,-d],[a,-b,d],[-a,b,d]]:
            solver.clause(clause)
        solver.clause([-equal,-a,b])  # Lexical pair orientation.
        nxt = solver.new()
        for clause in [[-nxt,equal],[-nxt,-d],[-equal,d,nxt]]:
            solver.clause(clause)
        equal = nxt
    solver.clause(differences)
    return u, v, truth


def add_mask_binary(solver, table, mask, u, v, truth):
    width = max(1, (len(table) - 1).bit_length())
    ends = []
    for inputs in [u, v]:
        state = [-truth] * width
        for x in inputs:
            nxt = [solver.new() for _ in range(width)]
            for q, ports in enumerate(table):
                mismatch = [-b if (q >> i) & 1 else b for i, b in enumerate(state)]
                for bit in [0, 1]:
                    target = ports[bit ^ ((mask >> q) & 1)]
                    guard = mismatch + [-x if bit else x]
                    for i, b in enumerate(nxt):
                        solver.clause(guard + [b if (target >> i) & 1 else -b])
            state = nxt
        ends.append(state)
    for a, b in zip(*ends):
        solver.clause([-a,b]); solver.clause([a,-b])


def add_mask_onehot(solver, table, mask, u, v, truth):
    ends = []
    for inputs in [u, v]:
        state = [truth] + [-truth] * (len(table) - 1)
        for x in inputs:
            nxt = [solver.new() for _ in table]
            # Starting from a single source, these force a single next target.
            solver.clause(nxt)
            for a in range(len(nxt)):
                for b in range(a):
                    solver.clause([-nxt[a],-nxt[b]])
            for q, ports in enumerate(table):
                for bit in [0,1]:
                    target = ports[bit ^ ((mask >> q) & 1)]
                    solver.clause([-state[q],-x if bit else x,nxt[target]])
            # Redundant inverse support clauses improve unit propagation.
            for target in range(len(table)):
                for bit in [0, 1]:
                    sources = [state[q] for q, ports in enumerate(table)
                               if ports[bit ^ ((mask >> q) & 1)] == target]
                    solver.clause([-nxt[target], -x if bit else x] + sources)
            state = nxt
        ends.append(state)
    for a,b in zip(*ends):
        solver.clause([-a,b]); solver.clause([a,-b])


def verify(table, first, second):
    assert first != second and len(first) == len(second)
    trace = [0] * (len(first) + 1)
    failed = []
    for mask in range(1 << len(table)):
        left = right = 0
        for i, (a, b) in enumerate(zip(first, second), 1):
            left = table[left][int(a) ^ ((mask >> left) & 1)]
            right = table[right][int(b) ^ ((mask >> right) & 1)]
            trace[i] += left != right
        if left != right: failed.append(mask)
    return trace, failed


def permutation_masks(table):
    return [mask for mask in range(1 << len(table)) if all(
        len({ports[bit ^ ((mask >> q) & 1)] for q, ports in enumerate(table)}) == len(table)
        for bit in [0, 1])]


def solve_length(table, length, args, library, inherited_masks):
    solver = Solver(library, args.phases)
    try:
        u, v, truth = base_formula(solver, length, args.different_prefix)
        if args.inputs_only:
            solver.decision_prefix = len(set(u + v))
        add = add_mask_binary if args.encoding == "binary" else add_mask_onehot
        initial = sorted(set(inherited_masks) | ({0} if args.initial == "zero" else set(permutation_masks(table)) or {0}))
        if args.initial == "full": initial = list(range(1 << len(table)))
        masks = []
        for mask in initial:
            add(solver, table, mask, u, v, truth); masks.append(mask)
        iterations = 0
        while True:
            stats = solver.stats()
            conflicts = args.conflicts - stats["conflicts"]
            props = args.propagations - stats["propagations"]
            if conflicts <= 0 or props <= 0:
                result = {"status":"unknown", "reason":"fixed-work-budget"}; break
            sat = solver.solve(conflicts, props); iterations += 1
            if sat < 0:
                result = {"status":"unknown", "reason":"fixed-work-budget"}; break
            if not sat:
                result = {"status":"unsat", "reason":"complete-CNF-refutation"}; break
            first = "".join(str(solver.value(x)) for x in u)
            second = "".join(str(solver.value(x)) for x in v)
            trace, failures = verify(table, first, second)
            if not failures:
                # A valid collision remains valid under every common suffix;
                # the earliest distinct zero is itself an upper certificate.
                first_difference = next(i + 1 for i,(a,b) in enumerate(zip(first,second)) if a != b)
                size = next(i for i in range(first_difference,len(trace)) if trace[i] == 0)
                result = {"status":"sat","witness":[first[:size],second[:size]],
                          "upper_bound":size,"witness_metric_trace":trace[:size+1]}; break
            fresh = [mask for mask in failures if mask not in masks]
            assert fresh
            chosen = fresh if args.refinement == "all" else fresh[:1]
            for mask in chosen:
                add(solver, table, mask, u, v, truth); masks.append(mask)
        result.update({"requested_length":length,"masks":masks,"iterations":iterations,
                       "stats":solver.stats(),"clauses_added":solver.clauses})
        assert result["stats"]["random_decisions"] == 0
        return result
    finally:
        solver.close()


def search(table, args, library):
    attempts = []; masks = []; upper = None; lower = 1; best = None
    schedule = []
    value = 1
    while value < args.max_length:
        schedule.append(value); value *= 2
    schedule.append(args.max_length)
    if args.schedule == "descending": schedule = [args.max_length]
    if args.schedule == "linear4": schedule = sorted(set([1,2] + list(range(4,args.max_length+1,4)) + [args.max_length]))
    for length in schedule:
        record = solve_length(table, length, args, library, masks)
        attempts.append(record); masks = sorted(set(masks) | set(record["masks"]))
        if record["status"] == "unsat" and not args.different_prefix: lower = max(lower,length+1)
        if record["status"] == "sat":
            upper, best = record["upper_bound"], record; break
    tested = {row["requested_length"] for row in attempts}
    while upper is not None and lower < upper:
        length = upper - 1 if args.schedule == "descending" else (lower + upper - 1)//2
        if length in tested: break
        tested.add(length)
        record = solve_length(table,length,args,library,masks); attempts.append(record)
        masks = sorted(set(masks) | set(record["masks"]))
        if record["status"] == "unsat":
            if not args.different_prefix: lower = max(lower,length+1)
            else: break
        elif record["status"] == "sat": upper,best=record["upper_bound"],record
        else:
            # Deterministic next probe nearer the positive; UNKNOWN is never
            # interpreted as UNSAT and never raises the certified lower.
            if length != upper-1 and upper-1 not in tested:
                next_record=solve_length(table,upper-1,args,library,masks);attempts.append(next_record);tested.add(upper-1)
                if next_record["status"]=="sat":upper,best=next_record["upper_bound"],next_record;continue
                if next_record["status"]=="unsat" and not args.different_prefix:lower=max(lower,upper)
            break
    return {"k":None,"window_kind":"SAT-CEGAR","upper_bound":upper,"lower_bound":lower,
            "witness":None if best is None else best["witness"],
            "witness_metric_trace":None if best is None else best["witness_metric_trace"],
            "minimality_certified":upper is not None and upper==lower and not args.different_prefix,"attempts":attempts,
            "total_conflicts":sum(row["stats"]["conflicts"] for row in attempts),
            "total_propagations":sum(row["stats"]["propagations"] for row in attempts),
            "randomness":False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive",type=Path,default=REPO/"out/family1-finder-strategies-20261026/profile/source/unpacked/python_sat-1.9.dev17/solvers/minisat22.tar.gz")
    parser.add_argument("--build",type=Path,default=REPO/"out/family1-finder-strategies-20261026/profile/native")
    parser.add_argument("--cases",type=Path)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--encoding",choices=["binary","onehot"],default="binary")
    parser.add_argument("--initial",choices=["zero","permutation","full"],default="permutation")
    parser.add_argument("--refinement",choices=["first","all"],default="all")
    parser.add_argument("--schedule",choices=["bracket","descending","linear4"],default="bracket")
    parser.add_argument("--different-prefix",type=int,default=0,help="0 full joint; otherwise restrict differing letters to first N positions")
    parser.add_argument("--phases",type=int,choices=[0,1,2],default=2)
    parser.add_argument("--inputs-only",action="store_true",help="Allow decisions only on input-word variables; all auxiliaries propagate")
    parser.add_argument("--max-length",type=int,default=80)
    parser.add_argument("--conflicts",type=int,default=100000)
    parser.add_argument("--propagations",type=int,default=50000000)
    parser.add_argument("--build-only",action="store_true")
    parser.add_argument("--rebuild",action="store_true")
    args=parser.parse_args()
    library=args.build/"libdeterministic_minisat.so"
    if not library.exists() or args.rebuild: build(args.archive,args.build)
    if args.build_only:return
    assert args.cases and not args.out.exists()
    cases=[json.loads(line) for line in args.cases.read_text().splitlines() if line.strip()]
    args.out.mkdir(parents=True)
    config={key:str(value) if isinstance(value,Path) else value for key,value in vars(args).items()}
    config.update(cases_sha256=sha(args.cases),script_sha256=sha(Path(__file__)),library_sha256=sha(library),k=None,randomness=False)
    (args.out/"run.json").write_text(json.dumps(config,indent=2)+"\n")
    records=[]
    with (args.out/"records.jsonl").open("w") as stream:
        for case in cases:
            table=case["canonical_table"];start=time.monotonic()
            row=search(table,args,library);row.update(m=len(table),key=case["key"],canonical_table=table,seconds=time.monotonic()-start)
            stream.write(json.dumps(row,separators=(",",":"))+"\n");stream.flush();records.append(row)
            print(json.dumps({k:row[k] for k in ["m","key","k","upper_bound","lower_bound","minimality_certified","total_conflicts","total_propagations","seconds"]}),flush=True)
    summary={"cases":len(records),"found":sum(row["upper_bound"] is not None for row in records),
             "exact":sum(row["minimality_certified"] for row in records),"k":None,
             "records_sha256":sha(args.out/"records.jsonl"),"randomness":False}
    (args.out/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")


if __name__=="__main__":main()
