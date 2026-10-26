"""Optional GPU proposals of upper witnesses, verified by CPU on all128 masks.

GPU misses, errors and complete collision-free GPU layers remain UNRESOLVED.
No lower bound or global certificate is derived from GPU computations.
Install the optional pinned runtime in an isolated environment; see --help.
"""
import argparse, hashlib, json, time, sys
from pathlib import Path
from types import SimpleNamespace
try:
    import cupy as cp
    import numpy as np
except ImportError:
    raise SystemExit('Optional GPU runtime missing: install cupy-cuda13x[ctk]==14.2.0 in an isolated environment')

MASK=(1<<64)-1
PAT=[0xaaaaaaaaaaaaaaaa,0xcccccccccccccccc,0xf0f0f0f0f0f0f0f0,
     0xff00ff00ff00ff00,0xffff0000ffff0000,0xffffffff00000000]

def scalar(table, words):
    if len(words)!=2 or words[0]==words[1] or not words[0] or len(words[0])!=len(words[1]):
        return False
    if any(set(w)-{'0','1'} for w in words):return False
    for mask in range(128):
        a=b=0
        for x,y in zip(*words):
            a=table[a][int(x)^((mask>>a)&1)]
            b=table[b][int(y)^((mask>>b)&1)]
        if a!=b:return False
    return True

base=SimpleNamespace(MASK=MASK,PAT=PAT,scalar=scalar)
adjacent_equal=cp.ElementwiseKernel('uint64 a, uint64 b, int32 shift','bool same',
                                  'same=(a>>shift)==(b>>shift);','family1_adjacent_equal')

def table_from_key(key):
    if len(key)!=28 or not key.isdigit():raise ValueError('Expected seven-state two-digit key')
    table=[[int(key[4*s:4*s+2]),int(key[4*s+2:4*s+4])] for s in range(7)]
    if any(v>6 for row in table for v in row):raise ValueError('Target outside0..6')
    return table

def source(chunk=3):
    lines=['typedef unsigned long long U; struct P { U v[6]; }; __constant__ U graphcode;',
           '__device__ __forceinline__ P step(P p,int x){ P r={}; U g=graphcode;']
    for state in range(7):
        lines += [f'{{U a0=(g>>{6*state})&7,a1=(g>>{6*state+3})&7;']
        for block in range(2):
            sig=base.PAT[state] if state<6 else base.MASK if block else 0
            terms=[('' if (state>>bit)&1 else '~')+f'p.v[{2*bit+block}]' for bit in range(3)]
            lines += [f'{{ U e={"&".join(terms)},sig=x?~{sig}ULL:{sig}ULL;']
            for bit in range(3):
                lines += [f'{{U b0=(a0>>{bit})&1,b1=(a1>>{bit})&1;U m=(0ULL-b0)^(sig&(0ULL-(b0^b1)));r.v[{2*bit+block}]|=e&m;}}']
            lines+=['}']
        lines+=['}']
    lines+=['return r;}',
      '__device__ __forceinline__ U rev(U a){return __brevll(a);}',
      '__device__ __forceinline__ U mix(U a){a^=a>>30;a*=0xbf58476d1ce4e5b9ULL;a^=a>>27;a*=0x94d049bb133111ebULL;return a^(a>>31);}',
      '__device__ __forceinline__ U fp(P p){U a=0x9e3779b97f4a7c15ULL,b=a;']
    for bit in range(3):
        lines += [f'a^=mix(p.v[{2*bit}])+(a<<6)+(a>>2); b^=mix(rev(p.v[{2*bit+1}]))+(b<<6)+(b>>2);']
    lines+=['U lo=a<b?a:b,hi=a<b?b:a;return mix(lo^((hi<<29)|(hi>>35))^0xd6e8feb86659fd93ULL);}',
      '__device__ __forceinline__ bool eq(P a,P b){bool same=true,other=true;for(int s=0;s<3;++s){same&=a.v[2*s]==b.v[2*s]&&a.v[2*s+1]==b.v[2*s+1];other&=a.v[2*s]==rev(b.v[2*s+1])&&a.v[2*s+1]==rev(b.v[2*s]);}return same||other;}',
      '__device__ __forceinline__ P eval(U w,int d){P p={};for(int j=d-1;j>=0;--j)p=step(p,(w>>j)&1);return p;}',
      'template<int K> __device__ __forceinline__ void walk(P p,U id,int bits,U* out,U* self){if constexpr(K==0){bool own=true;for(int s=0;s<3;++s)own&=p.v[2*s]==rev(p.v[2*s+1]);if(own)atomicMin(self,id);out[id]=(fp(p)<<bits)|id;}else{walk<K-1>(step(p,0),id*2,bits,out,self);walk<K-1>(step(p,1),id*2+1,bits,out,self);}}',
      f'extern "C" __global__ void generate(int depth,int bits,U offset,U* out,U* self){{U id=(U)blockIdx.x*blockDim.x+threadIdx.x;U n=1ULL<<(bits-{chunk});if(id>=n)return;P p=eval((offset>>{chunk})+id,depth-{chunk});walk<{chunk}>(p,id,bits,out,self);}}',
      'extern "C" __global__ void check(int depth,int bits,U offset,const U* sorted,const long long* positions,U n,U* hit){U j=(U)blockIdx.x*blockDim.x+threadIdx.x;if(j>=n)return;U at=positions[j],count=1ULL<<bits,mask=count-1,hash=sorted[at]>>bits;P a=eval((sorted[at]&mask)+offset,depth);for(U other=at+1;other<count&&(sorted[other]>>bits)==hash;++other){if(eq(a,eval((sorted[other]&mask)+offset,depth)))atomicMin(hit,(at<<32)|(other-at));}}',
      'extern "C" __global__ void profiles(const U* words,int n,int depth,U* out){int i=blockIdx.x*blockDim.x+threadIdx.x;if(i>=n)return;P p=eval(words[i],depth);for(int j=0;j<6;++j)out[i*6+j]=p.v[j];}'
    ]
    return '\n'.join(lines)

class Engine:
    def __init__(self,chunk=3):
        self.chunk=chunk
        self.module=cp.RawModule(code=source(chunk),options=('-std=c++17',))
        self.generate=self.module.get_function('generate');self.check=self.module.get_function('check')
        self.profiles_kernel=self.module.get_function('profiles')
        self.codeptr=self.module.get_global('graphcode')
    def graph(self,key):
        table=table_from_key(key)
        encoded=np.array([sum(t<<(6*s+3*p) for s,row in enumerate(table) for p,t in enumerate(row))],dtype=np.uint64)
        cp.cuda.runtime.memcpy(self.codeptr.ptr,encoded.ctypes.data,8,cp.cuda.runtime.memcpyHostToDevice)
        return table
    def profiles(self,key,words,depth):
        self.graph(key);w=cp.asarray(words,dtype=cp.uint64);r=cp.empty((len(words),6),dtype=cp.uint64)
        self.profiles_kernel(((len(words)+127)//128,),(128,),(w,np.int32(len(words)),np.int32(depth),r))
        return r.get()
    def probe_window(self,key,depth,bits,offset=0):
        if not self.chunk<=bits<=min(depth-1,30) or depth>40 or offset<0 or offset%(1<<bits) or offset+(1<<bits)>1<<(depth-1):
            raise ValueError('Unsupported depth or word window')
        table=self.graph(key);start=time.perf_counter();n=1<<bits
        out=cp.empty(n,dtype=cp.uint64);selfhit=cp.full(1,base.MASK,dtype=cp.uint64)
        self.generate((((n>>self.chunk)+127)//128,),(128,),(np.int32(depth),np.int32(bits),np.uint64(offset),out,selfhit))
        cp.cuda.Stream.null.synchronize();generated=time.perf_counter()-start
        witness=None;selfindex=int(selfhit.item());candidates=0
        if selfindex!=base.MASK:
            a=f'{selfindex+offset:0{depth}b}';b=''.join('1' if c=='0' else '0' for c in a)
            if base.scalar(table,[a,b]):witness=[a,b]
            else:raise RuntimeError('GPU own-complement hit failed CPU scalar')
        if witness is None:
            out.sort();positions=cp.flatnonzero(adjacent_equal(out[:-1],out[1:],np.int32(bits)))
            candidates=int(positions.size)
            if candidates:
                hit=cp.full(1,base.MASK,dtype=cp.uint64)
                self.check(((candidates+127)//128,),(128,),(np.int32(depth),np.int32(bits),np.uint64(offset),out,positions,np.uint64(candidates),hit))
                cp.cuda.Stream.null.synchronize();index=int(hit.item())
                if index!=base.MASK:
                    at=index>>32;distance=index&((1<<32)-1)
                    a=(int(out[at].item())&(n-1))+offset;b=(int(out[at+distance].item())&(n-1))+offset
                    wa,wb=f'{a:0{depth}b}',f'{b:0{depth}b}'
                    for other in (wb,''.join('1' if c=='0' else '0' for c in wb)):
                        if wa!=other and base.scalar(table,[wa,other]):witness=[wa,other];break
                    if witness is None:raise RuntimeError('GPU hit failed CPU scalar')
        cp.cuda.Stream.null.synchronize()
        result=dict(key=key,depth=depth,chunk=self.chunk,window_bits=bits,window_offset=offset,
                    generate_s=generated,seconds=time.perf_counter()-start,
                    candidate_groups=candidates,witness=witness,upper_bound=depth if witness else None,
                    status='verified-upper' if witness else 'unresolved',lower_bound=None,absence_is_not_lower_proof=True)
        del out,selfhit
        cp.get_default_memory_pool().free_all_blocks()
        return result

    def probe(self,key,depth,window_bits=29,max_blocks=0):
        if not self.chunk+1<=depth<=40 or not self.chunk<=window_bits<=30 or max_blocks<0:
            raise ValueError('Unsupported search limits')
        bits=depth-1 if depth<=31 else min(depth-1,window_bits)
        count=1<<(depth-1-bits)
        blocks=min(count,max_blocks) if max_blocks else count
        start=time.perf_counter();windows=[]
        for block in range(blocks):
            report=self.probe_window(key,depth,bits,block<<bits);windows.append(report)
            if report['witness']:break
        final=dict(windows[-1])
        final.update(seconds=time.perf_counter()-start,windows_tested=len(windows),
                     total_windows=count,window_reports=windows,
                     cross_window_pairs_checked=count==1,
                     absence_is_not_lower_proof=True)
        return final

def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--journal',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--depths',default='28,30')
    p.add_argument('--threshold',type=int,default=31)
    p.add_argument('--follow',action='store_true',help='Wait for the producer summary at EOF')
    p.add_argument('--resume',action='store_true')
    p.add_argument('--limit-graphs',type=int,default=0)
    p.add_argument('--window-bits',type=int,default=29,help='Bounded-memory blocks above depth31; misses are inconclusive')
    p.add_argument('--max-window-blocks',type=int,default=0,help='0 checks all blocks, without cross-block pairs')
    a=p.parse_args();journal=a.journal.resolve();directory=a.out.resolve()
    depths=[int(s) for s in a.depths.split(',')]
    if not journal.is_file() or not depths or depths!=sorted(set(depths)) or any(not 4<=d<=40 for d in depths):
        raise ValueError('Need a journal and increasing distinct depths in4..40')
    if a.threshold<max(depths) or a.limit_graphs<0 or not 3<=a.window_bits<=30 or a.max_window_blocks<0:
        raise ValueError('Invalid threshold or limit')
    config=dict(method='gpu-positive-proposals-cpu128-static-mask-witness-verification-v3',
                journal=str(journal),depths=depths,threshold=a.threshold,
                window_bits=a.window_bits,max_window_blocks=a.max_window_blocks,
                source_sha256=digest(Path(__file__)),cupy=cp.__version__,
                gpu=cp.cuda.runtime.getDeviceProperties(0)['name'].decode(),
                no_hit_is_inconclusive=True,maximum_value_certified=False,
                maximizing_collection_complete=False)
    if a.resume:
        if json.loads((directory/'run.json').read_text())!=config:raise ValueError('Resume configuration differs')
    else:
        if directory.exists() and any(directory.iterdir()):raise ValueError('Output must be new or empty')
        directory.mkdir(parents=True,exist_ok=True)
        (directory/'run.json').write_text(json.dumps(config,indent=2)+'\n')
    done={};positive_keys=set()
    for name in ('attempts.jsonl','upper-witnesses.jsonl'):
        path=directory/name
        if path.exists():
            with path.open() as stream:
                for line in stream:
                    record=json.loads(line)
                    if name=='attempts.jsonl':
                        if record['key'] in done:raise ValueError('Duplicate attempt in resume')
                        done[record['key']]=record['ordinal']
                    else:
                        if record['key'] in positive_keys:raise ValueError('Duplicate witness in resume')
                        table=table_from_key(record['key'])
                        if (type(record.get('m')) is not int or record['m']!=7
                            or type(record.get('ordinal')) is not int or record['ordinal']<0
                            or record.get('canonical_table')!=table
                            or type(record.get('upper_bound')) is not int
                            or record['upper_bound'] not in depths
                            or not isinstance(record.get('witness'),list)
                            or len(record['witness'])!=2
                            or any(not isinstance(w,str) or len(w)!=record['upper_bound'] for w in record['witness'])
                            or not scalar(table,record['witness'])):raise ValueError('Invalid prior upper witness metadata or trajectory')
                        positive_keys.add(record['key'])
    engine=Engine(3);started=time.perf_counter();scored=hits=errors=read_count=0
    complete=False;limit=False
    with journal.open('rb') as stream, (directory/'attempts.jsonl').open('a',buffering=1) as attempts, \
            (directory/'upper-witnesses.jsonl').open('a',buffering=1) as positives:
        while True:
            offset=stream.tell();line=stream.readline()
            if not line or not line.endswith(b'\n'):
                stream.seek(offset)
                producer=journal.parent/'summary.json'
                if producer.exists():
                    report=json.loads(producer.read_text())
                    if report.get('enumeration_complete') is True:
                        if line:raise ValueError('Completed producer has a torn final record')
                        complete=True;break
                if not a.follow:break
                time.sleep(1);continue
            record=json.loads(line);read_count+=1
            if record.get('m')!=7 or record.get('ordinal')!=read_count-1:raise ValueError('Input order or size mismatch')
            key=record['key'];table=table_from_key(key)
            if table!=record['canonical_table']:raise ValueError('Input table/key mismatch')
            if record['upper_bound'] is not None and record['upper_bound']<a.threshold:continue
            if record.get('status')=='exact':continue
            if key in done:
                if done[key]!=record['ordinal']:raise ValueError('Input identity changed on resume')
                continue
            results=[]
            try:
                for depth in depths:
                    if depth<record['lower_bound']:continue
                    r=engine.probe(key,depth,a.window_bits,a.max_window_blocks);results.append(r)
                    if r['witness']:
                        if depth<record['lower_bound']:raise ValueError('Witness contradicts certified lower bound')
                        if key not in positive_keys:
                            upper=dict(m=7,ordinal=record['ordinal'],key=key,canonical_table=table,
                                       upper_bound=depth,witness=r['witness'],cpu_scalar_masks_verified=128,
                                       method=config['method'])
                            positives.write(json.dumps(upper,separators=(',',':'))+'\n');positive_keys.add(key)
                        hits+=1;break
            except (cp.cuda.memory.OutOfMemoryError, cp.cuda.runtime.CUDARuntimeError) as error:
                results.append(dict(status='incomplete',error=str(error)));errors+=1
            attempts.write(json.dumps(dict(m=7,ordinal=record['ordinal'],key=key,results=results,
                                           absence_is_not_lower_proof=True),separators=(',',':'))+'\n')
            done[key]=record['ordinal'];scored+=1
            if scored%100==0:
                progress=dict(read_records=read_count,graphs_attempted=scored,verified_uppers=hits,
                              unresolved=scored-hits,errors=errors,seconds=time.perf_counter()-started)
                print(json.dumps(progress),flush=True)
                (directory/'progress.json').write_text(json.dumps(progress)+'\n')
            if errors>=10:break
            if a.limit_graphs and scored>=a.limit_graphs:limit=True;break
    summary=dict(config,source_enumeration_complete=complete,records_read=read_count,
                 graphs_attempted_this_execution=scored,verified_uppers_this_execution=hits,
                 unresolved_this_execution=scored-hits,errors=errors,limit_reached=limit,
                 total_attempted=len(done),total_verified_uppers=len(positive_keys),
                 seconds=time.perf_counter()-started)
    if complete:summary['journal_sha256']=digest(journal)
    (directory/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary),flush=True)

if __name__=='__main__':main()
