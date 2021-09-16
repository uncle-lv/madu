__SOFTWARE_VERSION__ = '0.1'
__SERVER_VERSION__ = 'madu/' + __SOFTWARE_VERSION__

BAD_REQUEST = b"""\
HTTP/1.1 400 Bad Request
Content-type: text/plain
Content-length: 11

Bad Request""".replace(b"\n", b"\r\n")