#!/usr/bin/env python3
"""Clone Exam scorer. usage: compare.py REAL_DIR CLONE_DIR [--json out.json]
Compares, per scenario, what the real Codex and the clone SEND to the model and DO to the workspace.
Checks (each pass/fail): request shape, instructions text, tool definitions, environment context, tool-result text, file effects, final answer."""
import json,glob,os,re,sys
def norm(s):
    if not isinstance(s,str):return s
    s=re.sub(r'/[^\s"<>]*?/workdir','<CWD>',s)
    s=re.sub(r'Chunk ID: [0-9a-f]+','Chunk ID: <CHUNK>',s)
    s=re.sub(r'Wall time: [0-9.]+ seconds','Wall time: <WALL> seconds',s)
    s=re.sub(r'session ID \d+','session ID <SID>',s)
    s=re.sub(r'\b(msg|fc|fco|rs|call)_[0-9a-f-]{8,}','<ID>',s)
    return s
def deep(o):
    if isinstance(o,dict):return {k:deep(v) for k,v in sorted(o.items()) if k not in('id','prompt_cache_key','client_metadata')}
    if isinstance(o,list):return [deep(x) for x in o]
    return norm(o)
def load(d):
    return [json.load(open(f)) for f in sorted(glob.glob(d+'/requests/req_*.json'))]
def files(d):
    r={}
    w=d+'/workdir'
    for root,_,fs in os.walk(w):
        for f in fs:
            p=os.path.join(root,f);r[os.path.relpath(p,w)]=open(p,'rb').read()
    return r
def final(d):
    t=open(d+'/stdout.txt',errors='replace').read()
    m=re.search(r'\ncodex\n(.*?)\ntokens used',t,re.S)
    if not m:return None
    return '\n'.join(l for l in m.group(1).split('\n') if not re.match(r'^\d{4}-\d\d-\d\dT',l)).strip()
def texts(items,role):
    return [deep(i['content']) for i in items if i.get('type')=='message' and i.get('role')==role]
def scenario(real,clone):
    R=load(real);C=load(clone);res={}
    res['requests_count']=len(R)==len(C)
    if not C:
        return {k:False for k in ['requests_count','request_shape','instructions','tools','environment_context','tool_results','file_effects','final_answer']}
    r0,c0=R[0],C[0]
    keys=('model','stream','tool_choice','parallel_tool_calls','reasoning','store','include')
    res['request_shape']=set(r0.keys())-{'prompt_cache_key','client_metadata'}==set(c0.keys())-{'prompt_cache_key','client_metadata'} and all(deep(r0.get(k))==deep(c0.get(k)) for k in keys)
    dev_r=[t for t in texts(r0['input'],'developer')];dev_c=[t for t in texts(c0['input'],'developer')]
    # instructions = the developer messages (system prompt + skills block), compared whole
    res['instructions']=json.dumps(dev_r)==json.dumps(dev_c)
    res['tools']=deep(r0.get('tools'))==deep(c0.get('tools'))
    def env(x):
        out=[]
        for m in texts(x['input'],'user'):
            for part in m:
                t=part.get('text','')
                if '<environment_context>' in t:out.append(t)
        return out
    res['environment_context']=env(r0)==env(c0)
    def outs(rs):return [deep(i.get('output')) for r in rs[-1:] for i in r['input'] if i.get('type')=='function_call_output']
    res['tool_results']=outs(R)==outs(C)
    fr,fc=files(real),files(clone)
    fr.pop('AGENTS.md',None);fc.pop('AGENTS.md',None)
    res['file_effects']=fr==fc
    res['final_answer']=final(real)==final(clone)
    # AGENTS.md handling is part of the user context: compare user texts that mention AGENTS.md
    if os.path.exists(real+'/workdir/AGENTS.md'):
        ag=lambda x:[t for m in texts(x['input'],'user') for p in m for t in [p.get('text','')] if 'AGENTS.md' in t]
        res['agents_md']=ag(r0)==ag(c0)
    return res
if __name__=='__main__':
    RR,CC=sys.argv[1],sys.argv[2];skip=set(os.environ.get('SKIP','s5_readonly,s6_workspace_write').split(','))
    tot=ok=0;rows=[];cat={}
    for n in sorted(os.listdir(RR)):
        if n in skip or not os.path.isdir(f'{CC}/{n}'):continue
        r=scenario(f'{RR}/{n}',f'{CC}/{n}');rows.append((n,r))
        for k,v in r.items():
            tot+=1;ok+=bool(v);a=cat.setdefault(k,[0,0]);a[0]+=bool(v);a[1]+=1
    for n,r in rows:print(f"{n:22s} {sum(map(bool,r.values()))}/{len(r)}  "+' '.join(('.' if v else 'X')+k[:6] for k,v in r.items()))
    print();[print(f"{k:20s} {a[0]}/{a[1]}") for k,a in cat.items()]
    print(f"\nTOTAL {ok}/{tot} = {100*ok/tot:.1f}%")
    if '--json' in sys.argv:json.dump({'rows':rows,'total':[ok,tot]},open(sys.argv[sys.argv.index('--json')+1],'w'),indent=1)
