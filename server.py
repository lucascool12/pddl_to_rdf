import _socket
import http.server
import socketserver
from functools import partial
import traceback
import pddl_to_rdf

PORT = 8400


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        path = self.translate_path(self.path)
        if path == "./public/translate_pddl":
            length = int(self.headers.get('Content-Length', 0))
            print(length)
            if length > 0:
                pddl = self.rfile.read(length)
                print(pddl.decode())
                try:
                    rdf = pddl_to_rdf.translate_pddl(pddl)
                    self.send_response(http.HTTPStatus.OK)
                    self.send_header("Content-type", "text/plain")
                    self.send_header("Content-Length", str(len(rdf)))
                    self.end_headers()
                    self.wfile.write(rdf.encode())
                except:
                    self.send_error(http.HTTPStatus.UNPROCESSABLE_ENTITY, traceback.format_exc())
            else:
                self.send_error(http.HTTPStatus.UNPROCESSABLE_ENTITY, "Bad pddl")
        else:
            self.send_error(http.HTTPStatus.NOT_FOUND, "Page not found")

handler = partial(Handler, directory="./public")

with socketserver.TCPServer(("", PORT), handler) as httpd:
    print("Server started at localhost:" + str(PORT))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()

