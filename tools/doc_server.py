#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote,urlparse
import argparse,html
ROOT=Path(__file__).resolve().parents[1]
def safe_path(raw):
 p=(ROOT/unquote(raw).lstrip('/')).resolve()
 if not p.is_relative_to(ROOT) or not p.is_file(): raise FileNotFoundError(raw)
 return p
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  try:
   raw=urlparse(self.path).path[len('/doc/'):] if self.path.startswith('/doc/') else ''
   body=('<pre>'+html.escape(safe_path(raw).read_text(encoding='utf-8',errors='replace'))+'</pre>').encode() if raw else b'<h1>Story Brainstorm</h1>'
   self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
  except FileNotFoundError: self.send_error(404)
def main():
 p=argparse.ArgumentParser(); p.add_argument('--host',default='127.0.0.1'); p.add_argument('--port',type=int,default=8775); a=p.parse_args(); ThreadingHTTPServer((a.host,a.port),Handler).serve_forever()
if __name__=='__main__': main()
