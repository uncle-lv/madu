import socket
import sys
import io
import datetime
import traceback
from threading import Thread
from queue import Empty, Queue
from typing import Callable,  Tuple

__version__ = '0.1'
__server_version__ = 'madu/' + __version__

Bad_Request = b"""\
HTTP/1.1 400 Bad Request
Content-type: text/plain
Content-length: 11

Bad Request""".replace(b"\n", b"\r\n")


class WSGIServer:
    
    addr_family = socket.AF_INET
    socket_type = socket.SOCK_STREAM
    request_queue_size = 5
    
    def __init__(self, server_addr: Tuple[str, int], RequestHandlerClass, worker_count: int = 16) -> None:
        self.server_addr = server_addr
        self.RequsetHandlerClass = RequestHandlerClass
        self.worker_count = worker_count
        self.worker_backlog = worker_count * 8
        self.connection_queue = Queue(self.worker_backlog)
        
    def set_app(self, application: Callable) -> None:
        self.application = application
        
    @property
    def get_app(self) -> Callable:
        return self.application
        
    def serve_forever(self) -> None:
        workers = []
        for _ in range(self.worker_count):
            worker = WSGIServerWorker(self.connection_queue, self.RequsetHandlerClass, self)
            worker.start()
            workers.append(worker)
        
        with socket.socket() as server_socket:
            server_socket.setsockopt(
                socket.SOL_SOCKET, 
                socket.SO_REUSEADDR, 
                1
            )
            server_socket.bind(self.server_addr)
            server_socket.listen(self.worker_backlog)
            self.host, self.port = server_socket.getsockname()[:2]
            self.server_name = socket.getfqdn(self.host)
            print(f'WSGIServer: Serving HTTP on port {PORT} ...\n')
            
            while True:
                try:
                    self.connection_queue.put(server_socket.accept())
                except KeyboardInterrupt:
                    break
                
        for worker in workers:
            worker.stop()
            
        for worker in workers:
            worker.join(timeout=30)
            
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
        env['wsgi.multithread']  = True
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
        try:
            self.parse_request("")
        except IndexError:
            self.client_connection.sendall(Bad_Request)
            return
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
        try:
            request_line = text.splitlines()[0]
        except IndexError:
            raise IndexError
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
            response_bytes = response.encode()
            self.client_connection.sendall(response_bytes)
        finally:
            self.client_connection.close()


class WSGIServerWorker(Thread):
    def __init__(self, connection_queue: Queue, RequestHandlerClass, server: WSGIServer) -> None:
        super().__init__(daemon=True)
        
        self.connection_queue = connection_queue
        self.RequestHandlerClass = RequestHandlerClass
        self.server = server
        self.running = True
        
    def stop(self) -> None:
        self.running = False
        
    def run(self) -> None:
        self.running = True
        while self.running:
            try:
                client_connection, _ = self.connection_queue.get(timeout=1)
            except Empty:
                continue
            
            try:
                self.handle_request(client_connection, application)
            except Exception as e:
                traceback.print_exc()
            finally:
                self.connection_queue.task_done()
                
    def handle_request(self, client_connection: socket.socket, application: Callable) -> None:
        self.RequestHandlerClass(client_connection, self.server).handle(application)
        

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
    httpd.serve_forever()