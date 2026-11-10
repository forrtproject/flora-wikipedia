import json, sys, time
from http.server import HTTPServer, BaseHTTPRequestHandler
class Handler(BaseHTTPRequestHandler):
    count = 0
    def log_message(self, *args): pass
    def do_GET(self):
        Handler.count += 1
        n = Handler.count
        self.send_response(429 if n == 1 else 200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Retry-After', '0')
        self.end_headers()
        body = {'error': {'code': 'maxlag'}} if n == 2 else {'query': {'requests': n}}
        self.wfile.write(json.dumps(body).encode())
        if n >= 3: self.server.completed = True
server = HTTPServer(('127.0.0.1', 0), Handler)
with open(sys.argv[1], 'w') as f: f.write(str(server.server_port) + '\n')
server.timeout = 15
server.completed = False
deadline = time.monotonic() + 60
while not server.completed and time.monotonic() < deadline:
    server.handle_request()
server.server_close()
