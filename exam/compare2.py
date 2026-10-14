#!/usr/bin/env python3
"""Exam v2 scorer: compare2.py REAL_DIR OTHER_DIR  -> per-scenario checks. Normalises ids, paths, timestamps, session numbers."""
import json,glob,os,re,sys
def norm(s):
    if not isinstance(s,str):return s
    s=re.sub(r'/[^\s"<>\']*?/workdir','<CWD>',s)
    s=re.sub(r'Chunk ID: [0-9a-f]+','Chunk ID: <CHUNK>',s)
    s=re.sub(r'Wall time: [0-9.]+ seconds','Wall time: <WALL> seconds',s)
    s=re.sub(r'session ID \d+','session ID <SID>',s)
    s=re.sub(r'\b(msg|fc|fco|rs|call|item|resp)_[0-9a-zA-Z_-]{1,}\b','<ID>',s)
    s=re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}','<UUID>',s)
    s=re.sub(r'\d{4}-\d\d-\d\dT[0-9:.]+Z','<TS>',s)
    s=re.sub(r'\b\d{13}\b','<MS>',s)
    s=re.sub(r'\b1[0-9]{9}\b','<EPOCH>',s)
    s=re.sub(r'codex-arg0[A-Za-z0-9]{6}','codex-arg0<RND>',s)
    return s
SKIPK=('id','prompt_cache_key','client_metadata')
def deep(o):
    if isinstance(o,dict):return {k:deep(v) for k,v in sorted(o.items()) if k not in SKIPK}
    if isinstance(o,list):return [deep(x) for x in o]
    return norm(o)
def load(d,pat='req_*.json'):return [json.load(open(f)) for f in sorted(glob.glob(d+'/requests/'+pat))]
def read(p):
    try:return open(p,errors='replace').read()
    except:return ''
def files(d):
    r={};w=d+'/workdir'
    for root,_,fs in os.walk(w):
        for f in fs:
            p=os.path.join(root,f);r[os.path.relpath(p,w)]=open(p,'rb').read()
    return r
def final(t):
    m=re.search(r'\ncodex\n(.*?)\ntokens used',t,re.S)
    if not m:return t.strip().split('\n')[-1] if t.strip() else ''
    return '\n'.join(l for l in m.group(1).split('\n') if not re.match(r'^\d{4}-\d\d-\d\dT',l)).strip()
def errlines(t):
    out=[]
    for l in t.split('\n'):
        l=re.sub(r'^\d{4}-\d\d-\d\dT[0-9:.]+Z\s+','',l)
        if re.search(r'ERROR|error|Error|warning|Reconnecting|retry',l):out.append(norm(l))
    return [x for x in out if 'rollout' not in x and 'thread' not in x]
def hdrs(d):
    h=[json.load(open(f)) for f in sorted(glob.glob(d+'/requests/hdr_*.json'))]
    keep=('user-agent','originator','content-type','accept','openai-beta','version','x-codex-beta-features','x-client-request-id','x-codex-installation-id')
    return [{k:norm(v) for k,v in x.items() if k in keep and k not in('x-client-request-id','x-codex-installation-id')} for x in h[:1]]
def jsonevents(t):
    ev=[]
    for l in t.split('\n'):
        l=l.strip()
        if l.startswith('{'):
            try:ev.append(deep(json.loads(l)))
            except:pass
    return ev
CHECKS=['request_count','request_shape','instructions','tools','environment_context','user_messages','tool_results','file_effects','final_answer','json_events','exit_code','stderr_errors','headers']
def scen(real,other):
    R=load(real);C=load(other);res={}
    res['request_count']=len(R)==len(C)
    if not C and R:
        for k in CHECKS:res[k]=False
        res['exit_code']=read(real+'/exit_code')==read(other+'/exit_code');res['stderr_errors']=errlines(read(real+'/stderr.txt')+read(real+'/stdout.txt'))==errlines(read(other+'/stderr.txt')+read(other+'/stdout.txt'))
        return res
    if not R:
        for k in ('request_shape','instructions','tools','environment_context','user_messages','tool_results'):res[k]=(not C)
        res['file_effects']=files(real)==files(other);res['final_answer']=final(read(real+'/stdout.txt'))==final(read(other+'/stdout.txt'));res['json_events']=True;res['exit_code']=read(real+'/exit_code')==read(other+'/exit_code');res['stderr_errors']=errlines(read(real+'/stderr.txt')+read(real+'/stdout.txt'))==errlines(read(other+'/stderr.txt')+read(other+'/stdout.txt'));res['headers']=True
        return res
    r0,c0=R[0],C[0]
    top=lambda x:set(x.keys())-set(SKIPK)
    keys=('model','stream','tool_choice','parallel_tool_calls','reasoning','store','include','text','instructions_len')
    res['request_shape']=top(r0)==top(c0) and all(deep(r0.get(k))==deep(c0.get(k)) for k in keys if k!='instructions_len')
    dev=lambda x:json.dumps([deep(i['content']) for i in x['input'] if i.get('type')=='message' and i.get('role')=='developer'])+json.dumps(deep(x.get('instructions')))
    res['instructions']=dev(r0)==dev(c0)
    res['tools']=deep(r0.get('tools'))==deep(c0.get('tools'))
    env=lambda x:[p.get('text') for i in x['input'] if i.get('role')=='user' for p in i.get('content',[]) if isinstance(p,dict) and '<environment_context>' in str(p.get('text',''))]
    res['environment_context']=deep(env(r0))==deep(env(c0))
    um=lambda x:deep([i['content'] for i in x['input'] if i.get('type')=='message' and i.get('role')=='user'])
    res['user_messages']=um(r0)==um(c0)
    outs=lambda rs:[deep(i.get('output')) for r in rs for i in r['input'] if i.get('type')=='function_call_output']
    # tool results across all requests: only the new ones (last request has all)
    res['tool_results']=outs(R[-1:])==outs(C[-1:])
    fr,fc=files(real),files(other);res['file_effects']=fr==fc
    so=read(real+'/stdout.txt');co=read(other+'/stdout.txt')
    res['final_answer']=final(so)==final(co)
    res['json_events']=jsonevents(so)==jsonevents(co) if '--json' in (json.load(open('scenarios2/meta.json')).get(os.path.basename(real),{}).get('args',[])) else True
    res['exit_code']=read(real+'/exit_code')==read(other+'/exit_code')
    res['stderr_errors']=errlines(read(real+'/stderr.txt')+so)==errlines(read(other+'/stderr.txt')+co)
    res['headers']=hdrs(real)==hdrs(other)
    return res
if __name__=='__main__':
    RR,CC=sys.argv[1],sys.argv[2];tot=ok=0;rows=[];cat={}
    for n in sorted(os.listdir(RR)):
        if not os.path.isdir(f'{CC}/{n}'):continue
        r=scen(f'{RR}/{n}',f'{CC}/{n}');rows.append((n,r))
        for k,v in r.items():tot+=1;ok+=bool(v);a=cat.setdefault(k,[0,0]);a[0]+=bool(v);a[1]+=1
    for n,r in rows:print(f"{n:28s} {sum(map(bool,r.values()))}/{len(r)}  "+''.join(('.' if r.get(k) else 'X') for k in CHECKS))
    print('\ncolumns:',' '.join(c[:7] for c in CHECKS));print()
    for k in CHECKS:
        a=cat.get(k);print(f"{k:20s} {a[0]}/{a[1]}") if a else None
    print(f"\nTOTAL {ok}/{tot} = {100*ok/tot:.1f}%")
    if '--json' in sys.argv:json.dump({'rows':rows,'total':[ok,tot]},open(sys.argv[sys.argv.index('--json')+1],'w'),indent=1)
