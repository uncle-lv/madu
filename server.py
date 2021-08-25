import socket
import sys
import io
import datetime
from typing import Callable,  Tuple

__version__ = '0.1'
__server_version__ = 'madu/' + __version__

class WSGIServer:
    
    addr_family = socket.AF_INET
    socket_type = socket.SOCK_STREAM
    request_queue_size = 5
    
    def __init__(self, server_addr: Tuple[str, int], RequestHandlerClass) -> None:
        self.server_addr = server_addr
        self.RequsetHandlerClass = RequestHandlerClass
        self.socket = socket.socket(
            self.addr_family,
            self.socket_type
        )
        
        self.socket.setsockopt(
            socket.SOL_SOCKET, 
            socket.SO_REUSEADDR, 
            1
        )
        
        self.socket.bind(self.server_addr)
        self.socket.listen(self.request_queue_size)
        self.host, self.port = self.socket.getsockname()[:2]
        self.server_name = socket.getfqdn(self.host)
        
    def set_app(self, application: Callable) -> None:
        self.application = application
        
    @property
    def get_app(self) -> Callable:
        return self.application
        
    def serve_forever(self) -> None:
        listen_socket = self.socket
        while True:
            client_connection, _ = listen_socket.accept()
            self.handle_request(client_connection)
            
    def handle_request(self, client_connection) -> None:
        self.RequsetHandlerClass(client_connection, self).handle(self.get_app)
            
            
class WSGIRequestHandler:
    
    server_version = __server_version__
    
    def __init__(self, client_connection: socket.socket, server: WSGIServer) -> None:
        self.client_connection = client_connection
        self.server = server
        self.headers = []
    
    def get_environ(self) -> dict:
        env = {}
        env['wsgi.version']      = (1, 0)
        env['wsgi.url_scheme']   = 'http'
        env['wsgi.input']        = io.StringIO(self.request_data)
        env['wsgi.errors']       = sys.stderr
        env['wsgi.multithread']  = False
        env['wsgi.multiprocess'] = False
        env['wsgi.run_once']     = False
        env['REQUEST_METHOD']    = self.request_method
        env['PATH_INFO']         = self.path
        env['SERVER_NAME']       = self.server.server_name
        env['SERVER_PORT']       = str(self.server.port)
        return env
    
    def handle(self, application: Callable) -> None:
        request_data = self.client_connection.recv(1024)
        self.request_data = request_data = request_data.decode('utf-8')
        print(''.join(
            f'< {line}\n' for line in request_data.splitlines()
        ))
        self.parse_request(request_data)
        env = self.get_environ()
        result = application(env, self.start_response)
        self.finish_response(result)
        
    def start_response(self, status, response_headers, exc_info=None) -> None:
        server_headers = [
            ('DATE', datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %Z")),
            ('SERVER_SOFTWARE', __server_version__),
        ]
        self.headers = [status, response_headers + server_headers]
        
    def parse_request(self, text: str) -> None:
        request_line = text.splitlines()[0]
        request_line = request_line.rstrip('\r\n')
        (self.request_method, 
         self.path,
         self.request_version
         ) = request_line.split()
        
    def finish_response(self, result) -> None:
        try:
            status, response_headers = self.headers
            response = f'HTTP/1.1 {status}\r\n'
            for header in response_headers:
                response += '{0}: {1}\r\n'.format(*header)
            response += '\r\n'
            for data in result:
                response += data.decode('utf-8')
            print(''.join(
                f'> {line}\n' for line in response.splitlines()
            ))
            response_bytes = response.encode()
            self.client_connection.sendall(response_bytes)
        finally:
            self.client_connection.close()


SERVER_ADDR = (HOST, PORT) = '', 8000


def make_server(server_addr: Tuple[str, int], application: Callable) -> WSGIServer:
    server = WSGIServer(server_addr, WSGIRequestHandler)
    server.set_app(application)
    return server


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit('Provide a WSGI application object as module:callable')
    app_path = sys.argv[1]
    module, application = app_path.split(':')
    module = __import__(module)
    application = getattr(module, application)
    httpd = make_server(SERVER_ADDR, application)
    print(f'WSGIServer: Serving HTTP on port {PORT} ...\n')
    httpd.serve_forever()