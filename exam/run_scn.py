#!/usr/bin/env python3
"""usage: run_scn.py NAME...   env: CODEX_CMD (command string, default real codex), OUT_ROOT"""
import json,os,shlex,shutil,subprocess,sys,time,random
HERE=os.path.abspath(os.path.join(os.path.dirname(__file__),'..'))
REAL=HERE+'/target/codex-0.162.1-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex'
CMD=shlex.split(os.environ.get('CODEX_CMD',REAL));ROOT=os.environ.get('OUT_ROOT',HERE+'/exam/real2')
meta=json.load(open(HERE+'/exam/scenarios2/meta.json'))
names=sys.argv[1:] or list(meta)
for n in names:
    m=meta[n];out=f'{ROOT}/{n}';shutil.rmtree(out,ignore_errors=True);os.makedirs(out+'/requests');os.makedirs(out+'/workdir')
    fx=f'{HERE}/exam/fixtures2/{n}'
    if os.path.isdir(fx):shutil.copytree(fx,out+'/workdir',dirs_exist_ok=True)
    port=19000+random.randint(0,899)
    mock=subprocess.Popen(['python3',HERE+'/exam/mock_model.py',str(port),f'{HERE}/exam/scenarios2/{n}.json',out+'/requests'],stdout=open(out+'/mock.log','w'),stderr=subprocess.STDOUT)
    time.sleep(0.7)
    argv=CMD+['exec']+([] if m.get('noskip') else ['--skip-git-repo-check'])+['-c','model_provider="mock"','-c',f'model_providers.mock={{name="mock",base_url="http://127.0.0.1:{port}/v1",wire_api="responses",env_key="MOCK_KEY"}}']+m.get('args',[])
    env=dict(os.environ,HOME=HERE+'/home',CODEX_HOME=HERE+'/home/.codex',MOCK_KEY='x')
    if m.get('stdin'):
        argv+=['-'];inp=m['prompt']+'\n'
    else:
        argv+=[m['prompt']];inp=''
    try:
        p=subprocess.run(['timeout','120']+argv,cwd=out+'/workdir',env=env,input=inp,capture_output=True,text=True,errors='replace')
        open(out+'/stdout.txt','w').write(p.stdout);open(out+'/stderr.txt','w').write(p.stderr);open(out+'/exit_code','w').write(str(p.returncode))
        rc=p.returncode
    except Exception as e:
        open(out+'/stdout.txt','w').write('');open(out+'/stderr.txt','w').write(str(e));open(out+'/exit_code','w').write('-1');rc=-1
    mock.terminate();mock.wait()
    reqs=len([f for f in os.listdir(out+'/requests') if f.startswith('req_')])
    print(f'{n}: {reqs} requests, exit {rc}',flush=True)
