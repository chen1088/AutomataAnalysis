#!/usr/bin/env python3
"""Independently check a Family 1 union witness and lower-bound certificate.

Only Python's standard library is used. No native search code is loaded or
executed. Complete successor coverage is checked by scalar transitions under
the original static seed masks. Layers and accepted signature sets may be
supersets: successor closure and terminal inclusion are the proof obligations.

Exit codes: 0 checked, 1 invalid certificate, 2 checker resource limit reached.
An interrupted check never certifies an endpoint.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SCHEMA = "family1-certified-v1"
MASK_CONVENTION = "a_xor_bit_q"
DEFAULT_MAX_WORK = 10_000_000
DEFAULT_MAX_STATES = 1_000_000


class CertificateError(ValueError):
    """A certificate's data or proof obligation is invalid."""


class CheckIncomplete(RuntimeError):
    """A configured checker resource limit prevented a complete check."""


class Budget:
    def __init__(self, max_work: int, max_states: int):
        self.max_work = integer(max_work, "max_work", minimum=0)
        self.max_states = integer(max_states, "max_states", minimum=0)
        self.work = 0
        self.states = 0

    def charge(self, work: int = 1, states: int = 0) -> None:
        if self.work + work > self.max_work:
            raise CheckIncomplete("checker max-work limit reached")
        if self.states + states > self.max_states:
            raise CheckIncomplete("checker max-states limit reached")
        self.work += work
        self.states += states


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CertificateError(message)


def integer(value: Any, label: str, minimum: int = 0, maximum: int | None = None) -> int:
    require(type(value) is int, f"{label} must be an integer")
    require(value >= minimum, f"{label} must be at least {minimum}")
    if maximum is not None:
        require(value <= maximum, f"{label} exceeds {maximum}")
    return value


def array(value: Any, label: str) -> list:
    require(type(value) is list, f"{label} must be an array")
    return value


def obj(value: Any, label: str) -> dict:
    require(type(value) is dict, f"{label} must be an object")
    return value


def field(value: dict, name: str, label: str) -> Any:
    require(name in value, f"{label} is missing {name}")
    return value[name]


def binary_word(value: Any, label: str) -> str:
    require(type(value) is str and all(c in "01" for c in value),
            f"{label} must be a binary string")
    return value


def parse_seeds(raw: Any, budget: Budget, label: str = "family") -> tuple:
    raw = obj(raw, label)
    seeds = array(field(raw, "seeds", label), f"{label}.seeds")
    require(bool(seeds), "the declared family must contain at least one seed")
    result = []
    for index, seed in enumerate(seeds):
        where = f"{label}.seeds[{index}]"
        seed = obj(seed, where)
        ports = array(field(seed, "ports", where), f"{where}.ports")
        require(bool(ports), f"{where} must have at least one state")
        rows = []
        for q, row in enumerate(ports):
            budget.charge()
            row = array(row, f"{where}.ports[{q}]")
            require(len(row) == 2, f"{where}.ports[{q}] must have two ports")
            rows.append(tuple(integer(p, f"{where}.ports[{q}]", maximum=len(ports) - 1)
                              for p in row))
        root = integer(field(seed, "root", where), f"{where}.root", maximum=len(rows) - 1)
        if "name" in seed:
            require(type(seed["name"]) is str, f"{where}.name must be a string")
        result.append((root, tuple(rows)))
    return tuple(result)


def parse_observers(raw: Any, seeds: tuple, label: str) -> tuple:
    observers = []
    for index, observer in enumerate(array(raw, label)):
        where = f"{label}[{index}]"
        observer = obj(observer, where)
        seed = integer(field(observer, "seed", where), f"{where}.seed", maximum=len(seeds) - 1)
        mask = integer(field(observer, "mask", where), f"{where}.mask")
        require(mask.bit_length() <= len(seeds[seed][1]), f"{where}.mask is outside its seed closure")
        observers.append((seed, mask))
    require(len(set(observers)) == len(observers), f"{label} contains duplicate observers")
    return tuple(observers)


def transition(seeds: tuple, observer: tuple, state: int, bit: int) -> int:
    seed, mask = observer
    return seeds[seed][1][state][bit ^ ((mask >> state) & 1)]


def trace(seeds: tuple, observer: tuple, word: str, budget: Budget) -> int:
    state = seeds[observer[0]][0]
    for character in word:
        budget.charge()
        state = transition(seeds, observer, state, int(character))
    return state


def root_state(seeds: tuple, observers: tuple, prefix_u: str, prefix_v: str,
               budget: Budget) -> tuple:
    endpoints = tuple((trace(seeds, observer, prefix_u, budget),
                       trace(seeds, observer, prefix_v, budget)) for observer in observers)
    return endpoints, prefix_u != prefix_v


def parse_state(raw: Any, seeds: tuple, observers: tuple, label: str) -> tuple:
    raw = obj(raw, label)
    endpoints = array(field(raw, "endpoints", label), f"{label}.endpoints")
    require(len(endpoints) == len(observers), f"{label}.endpoints has the wrong observer count")
    result = []
    for index, (pair, observer) in enumerate(zip(endpoints, observers)):
        pair = array(pair, f"{label}.endpoints[{index}]")
        require(len(pair) == 2, f"{label}.endpoints[{index}] must be a pair")
        maximum = len(seeds[observer[0]][1]) - 1
        result.append(tuple(integer(q, f"{label}.endpoints[{index}]", maximum=maximum) for q in pair))
    distinct = field(raw, "distinct", label)
    require(type(distinct) is bool, f"{label}.distinct must be boolean")
    return tuple(result), distinct


def successor(state: tuple, a: int, b: int, seeds: tuple, observers: tuple) -> tuple:
    endpoints, distinct = state
    return (tuple((transition(seeds, observer, p, a), transition(seeds, observer, q, b))
                  for (p, q), observer in zip(endpoints, observers)), distinct or a != b)


def is_goal(state: tuple) -> bool:
    endpoints, distinct = state
    return distinct and all(p == q for p, q in endpoints)


def parse_signature(raw: Any, kind: str, depth: int, label: str) -> tuple:
    values = array(raw, label)
    require(len(values) == 4, f"{label} must have four coordinates")
    a = integer(values[0], f"{label}[0]", maximum=depth)
    b = integer(values[1], f"{label}[1]", maximum=depth)
    d = integer(values[2], f"{label}[2]", minimum=-1, maximum=max(-1, depth - 1))
    c = integer(values[3], f"{label}[3]", minimum=-1, maximum=depth)
    if kind == "count":
        require(d == c == -1, f"{label} count signature must end in -1,-1")
    elif d == -1:
        require(c == -1 and a == b, f"{label} has inconsistent no-difference coordinates")
    else:
        require(0 <= c <= d, f"{label} common-prefix count exceeds its first-difference position")
    return a, b, d, c


def signature_successor(signature: tuple, a: int, b: int, kind: str, depth: int) -> tuple:
    count_u, count_v, first, common_ones = signature
    if kind == "first-difference" and first == -1 and a != b:
        first, common_ones = depth, count_u
    return count_u + a, count_v + b, first, common_ones


def checked_layers(raw_layers: Any, horizon: int, seeds: tuple, observers: tuple,
                   budget: Budget, label: str, signature_kind: str | None = None) -> list[set]:
    raw_layers = array(raw_layers, label)
    require(len(raw_layers) == horizon + 1, f"{label} must contain horizon+1 layers")
    layers = []
    for depth, raw_layer in enumerate(raw_layers):
        layer = set()
        for index, raw_state in enumerate(array(raw_layer, f"{label}[{depth}]")):
            budget.charge(states=1)
            where = f"{label}[{depth}][{index}]"
            state = parse_state(raw_state, seeds, observers, where)
            if signature_kind is not None:
                signature = parse_signature(field(raw_state, "signature", where),
                                            signature_kind, depth, f"{where}.signature")
                state = state, signature
            require(state not in layer, f"{label}[{depth}] contains a duplicate state")
            layer.add(state)
        layers.append(layer)
    return layers


def check_paired_proof(proof: dict, seeds: tuple, budget: Budget) -> int:
    horizon = integer(field(proof, "horizon", "proof"), "proof.horizon")
    observers = parse_observers(field(proof, "observers", "proof"), seeds, "proof.observers")
    layers = checked_layers(field(proof, "layers", "proof"), horizon, seeds, observers, budget,
                            "proof.layers")
    require(root_state(seeds, observers, "", "", budget) in layers[0], "proof omits the initial root state")
    for depth in range(horizon):
        for state in layers[depth]:
            for a in (0, 1):
                for b in (0, 1):
                    budget.charge(work=1 + 2 * len(observers))
                    child = successor(state, a, b, seeds, observers)
                    require(child in layers[depth + 1],
                            f"proof.layers[{depth + 1}] omits a required {a}{b} successor")
    require(not any(is_goal(state) for state in layers[-1]), "paired proof contains a terminal distinct collision")
    return horizon


def check_signature_proof(proof: dict, seeds: tuple, budget: Budget) -> tuple[int, bool]:
    horizon = integer(field(proof, "horizon", "proof"), "proof.horizon")
    kind = field(proof, "signature", "proof")
    require(kind in ("count", "first-difference"), "unknown signature definition")
    prefix_u = binary_word(field(proof, "prefix_u", "proof"), "proof.prefix_u")
    prefix_v = binary_word(field(proof, "prefix_v", "proof"), "proof.prefix_v")
    require(len(prefix_u) == len(prefix_v), "signature prefixes must have equal lengths")
    groups = array(field(proof, "groups", "proof"), "proof.groups")
    require(bool(groups), "a signature exclusion requires at least one group")
    intersection = None
    for index, group in enumerate(groups):
        where = f"proof.groups[{index}]"
        group = obj(group, where)
        observers = parse_observers(field(group, "observers", where), seeds, f"{where}.observers")
        layers = checked_layers(field(group, "layers", where), horizon, seeds, observers, budget,
                                f"{where}.layers", signature_kind=kind)
        initial = root_state(seeds, observers, prefix_u, prefix_v, budget), (0, 0, -1, -1)
        require(initial in layers[0], f"{where} omits the correlated initial root/signature state")
        for depth in range(horizon):
            for state, signature in layers[depth]:
                for a in (0, 1):
                    for b in (0, 1):
                        budget.charge(work=1 + 2 * len(observers))
                        child = (successor(state, a, b, seeds, observers),
                                 signature_successor(signature, a, b, kind, depth))
                        require(child in layers[depth + 1],
                                f"{where}.layers[{depth + 1}] omits a required {a}{b} successor")
        accepted = set()
        for j, signature in enumerate(array(field(group, "accepted", where), f"{where}.accepted")):
            budget.charge()
            signature = parse_signature(signature, kind, horizon, f"{where}.accepted[{j}]")
            require(signature not in accepted, f"{where}.accepted contains a duplicate signature")
            accepted.add(signature)
        terminal = {signature for state, signature in layers[-1] if is_goal(state)}
        require(terminal <= accepted, f"{where}.accepted omits attainable terminal signatures")
        intersection = accepted if intersection is None else intersection & accepted
    declared = array(field(proof, "intersection", "proof"), "proof.intersection")
    require(not declared and not intersection, "signature intersection is not empty")
    return horizon, not prefix_u and not prefix_v


def check_upper(document: dict, seeds: tuple, budget: Budget) -> tuple[int | None, int]:
    upper = field(document, "upper_bound", "certificate")
    witness = field(document, "witness", "certificate")
    if upper is None:
        require(witness is None, "an upper witness requires its length as upper_bound")
        return None, 0
    upper = integer(upper, "upper_bound", minimum=1)
    witness = obj(witness, "witness")
    u = binary_word(field(witness, "u", "witness"), "witness.u")
    v = binary_word(field(witness, "v", "witness"), "witness.v")
    require(len(u) == len(v) == upper and u != v,
            "upper witness must be distinct equal-length words matching upper_bound")
    verified = 0
    for seed_index, (_, ports) in enumerate(seeds):
        for mask in range(1 << len(ports)):
            budget.charge()
            observer = seed_index, mask
            require(trace(seeds, observer, u, budget) == trace(seeds, observer, v, budget),
                    f"upper witness is separated by seed {seed_index}, mask {mask}")
            verified += 1
    return upper, verified


def check_certificate(document: Any, expected_family: Any = None,
                      max_work: int = DEFAULT_MAX_WORK,
                      max_states: int = DEFAULT_MAX_STATES) -> dict:
    """Return checked endpoints or raise CertificateError / CheckIncomplete.

    expected_family can be an input {seeds: ...} object or a full certificate
    containing `family`. Ordered roots and exact port tables are pinned; seed
    names are labels only and do not affect the mathematical target.
    """
    budget = Budget(max_work, max_states)
    document = obj(document, "certificate")
    require(field(document, "schema", "certificate") == SCHEMA, "unsupported certificate schema")
    family = obj(field(document, "family", "certificate"), "family")
    require(field(family, "mask_convention", "family") == MASK_CONVENTION,
            "unsupported mask convention")
    seeds = parse_seeds(family, budget)
    observer_count = sum(1 << len(ports) for _, ports in seeds)
    require(integer(field(family, "observer_count", "family"), "family.observer_count") == observer_count,
            "family.observer_count does not match all original indexed masks")
    if expected_family is not None:
        expected_family = obj(expected_family, "expected input")
        if "family" in expected_family:
            expected_family = obj(expected_family["family"], "expected input.family")
        if "mask_convention" in expected_family:
            require(expected_family["mask_convention"] == MASK_CONVENTION,
                    "expected input uses a different mask convention")
        require(parse_seeds(expected_family, budget, "expected input") == seeds,
                "embedded certificate family differs from the expected input")

    lower = integer(field(document, "lower_bound", "certificate"), "lower_bound", minimum=1)
    proof = field(document, "proof", "certificate")
    proved_lower = 1
    remaining_lower = None
    if proof is not None:
        proof = obj(proof, "proof")
        kind = field(proof, "kind", "proof")
        if kind == "paired-layers":
            proved_lower = check_paired_proof(proof, seeds, budget) + 1
        elif kind == "signature-intersection":
            horizon, global_proof = check_signature_proof(proof, seeds, budget)
            if global_proof:
                proved_lower = horizon + 1
            else:
                remaining_lower = horizon + 1
        else:
            raise CertificateError("unsupported proof kind")
    require(lower == proved_lower, "lower_bound does not equal the independently checked global lower endpoint")
    if "remaining_lower_bound" in document:
        declared_remaining = document["remaining_lower_bound"]
        if declared_remaining is not None:
            integer(declared_remaining, "remaining_lower_bound", minimum=1)
        require(declared_remaining == remaining_lower,
                "remaining_lower_bound does not match the checked residual certificate")
    upper, verified = check_upper(document, seeds, budget)
    require(upper is None or lower <= upper, "certified lower endpoint exceeds the verified upper endpoint")
    exact = upper is not None and upper == lower
    if "exact" in document:
        require(type(document["exact"]) is bool and document["exact"] == exact,
                "exact must be boolean and match the independently checked endpoints")
    if "requested_gap" in document and document["requested_gap"] is not None:
        integer(document["requested_gap"], "requested_gap")
    status = document.get("status")
    if status is not None:
        require(type(status) is str, "status must be a string")
    if status == "exact":
        require(exact, "exact status requires matching checked endpoints")
    elif status == "interval-certified":
        requested_gap = integer(field(document, "requested_gap", "certificate"), "requested_gap")
        require(upper is not None and upper - lower <= requested_gap,
                "interval-certified status exceeds the requested checked gap")
    elif status == "excluded":
        require(proof is not None, "excluded status requires a checked exclusion proof")
    elif status == "signature-survives":
        require(proof is None, "signature-survives must not claim an exclusion proof")
    elif status == "witness":
        require(upper is not None, "witness status requires a checked full-family witness")
    return {"status": "check-passed", "schema": SCHEMA, "lower_bound": lower,
            "upper_bound": upper, "exact": exact,
            "remaining_lower_bound": remaining_lower, "observer_count": observer_count,
            "verified_witness_observers": verified, "family_pinned": expected_family is not None,
            "checked_work": budget.work, "checked_states": budget.states}


def unique_object(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def load_json(path: str | Path) -> Any:
    def reject_constant(value: str) -> None:
        raise CertificateError(f"non-finite JSON constant: {value}")
    with Path(path).open(encoding="utf-8-sig") as stream:
        return json.load(stream, object_pairs_hook=unique_object, parse_constant=reject_constant)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("certificate", type=Path)
    parser.add_argument("--input", type=Path, help="pin the certificate to this ordered seed input")
    parser.add_argument("--max-work", type=int, default=DEFAULT_MAX_WORK,
                        help="maximum scalar/check operations (default: %(default)s)")
    parser.add_argument("--max-states", type=int, default=DEFAULT_MAX_STATES,
                        help="maximum proof states read (default: %(default)s)")
    args = parser.parse_args(argv)
    try:
        expected = load_json(args.input) if args.input else None
        result = check_certificate(load_json(args.certificate), expected,
                                   max_work=args.max_work, max_states=args.max_states)
    except (CheckIncomplete, MemoryError) as error:
        print(json.dumps({"status": "check-incomplete", "error": str(error)}))
        return 2
    except (CertificateError, OSError, UnicodeError, json.JSONDecodeError, RecursionError) as error:
        print(json.dumps({"status": "check-failed", "error": str(error)}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
