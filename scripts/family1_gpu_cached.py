"""Run the unchanged GPU witness proposer with a retained private memory pool.

Pass the same arguments as family1_gpu_witnesses.py. This changes allocation
policy only; GPU misses remain unresolved and every hit is CPU verified.
"""
import hashlib
import json
from pathlib import Path
import runpy
import sys
import cupy as cp


if __name__ == '__main__':
    generator = Path(__file__).with_name('family1_gpu_witnesses.py')
    if '--out' not in sys.argv:
        raise SystemExit('The GPU proposer requires --out DIRECTORY')
    out = Path(sys.argv[sys.argv.index('--out') + 1])
    # A private allocator keeps buffers across graphs. The unchanged proposer
    # can still clear the original default pool without discarding these buffers.
    pool = cp.cuda.MemoryPool()
    cp.cuda.set_allocator(pool.malloc)
    policy = {'allocator': 'retained-private-cupy-memory-pool',
              'launcher_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'generator_sha256': hashlib.sha256(generator.read_bytes()).hexdigest(),
              'cupy': cp.__version__}
    # The generator owns the destination guard and run/resume validation.
    # Write policy only after the generator accepts and executes the run.
    completed = False
    try:
        runpy.run_path(str(generator), run_name='__main__')
        completed = True
    finally:
        if completed and (out / 'run.json').is_file():
            policy_path = out / 'allocator-policy.json'
            if not policy_path.exists():
                policy_path.write_text(json.dumps(policy, indent=2) + '\n')
        pool.free_all_blocks()
