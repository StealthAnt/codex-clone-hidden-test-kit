#!/usr/bin/env python3
"""Scripted fake model for the Clone Exam. Speaks the OpenAI Responses API (SSE). Logs every request body.
usage: mock_model.py PORT SCRIPT.json LOGDIR   (script = list of steps: {"text":..} or {"tool":name,"args":{...}})"""
import json,sys,time,threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
PORT=int(sys.argv[1]);SCRIPT=json.load(open(sys.argv[2]));LOG=sys.argv[3]
state={'n':0};lock=threading.Lock()
def ev(name,data):return f"event: {name}\ndata: {json.dumps(data)}\n\n".encode()
class H(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def do_GET(self):
        self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b'{"data":[],"models":[]}')
    def do_POST(self):
        n=int(self.headers.get('Content-Length') or 0);body=self.rfile.read(n)
        with lock:
            i=state['n'];state['n']+=1
        open(f"{LOG}/req_{i:03d}_{self.path.strip('/').replace('/','_')}.json",'wb').write(body)
        open(f"{LOG}/hdr_{i:03d}.json",'w').write(json.dumps({k.lower():v for k,v in self.headers.items()}))
        if not self.path.endswith('/responses'):
            self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b'{}');return
        step=SCRIPT[min(i,len(SCRIPT)-1)] if i<len(SCRIPT) else {"text":"done"}
        if 'status' in step:
            self.send_response(step['status']);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps({'error':{'message':step.get('message','server error'),'type':'x','code':'x'}}).encode());return
        self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
        rid=f"resp_{i}"
        w=self.wfile.write
        w(ev("response.created",{"type":"response.created","response":{"id":rid}}))
        items=[]
        for k,t in enumerate(step.get("tools",[step] if "tool" in step else [])):
            args=t["raw_args"] if "raw_args" in t else json.dumps(t["args"])
            items.append({"type":"function_call","call_id":f"call_{i}_{k}","name":t["tool"],"arguments":args})
        if not items:
            items.append({"type":"message","role":"assistant","content":[{"type":"output_text","text":step["text"]}]})
        for item in items:
            w(ev("response.output_item.done",{"type":"response.output_item.done","item":item}))
        w(ev("response.completed",{"type":"response.completed","response":{"id":rid,"usage":{"input_tokens":10,"input_tokens_details":None,"output_tokens":5,"output_tokens_details":None,"total_tokens":15}}}))
        self.wfile.flush()
ThreadingHTTPServer(('127.0.0.1',PORT),H).serve_forever()
