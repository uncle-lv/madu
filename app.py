from flask import Flask, Response

app = Flask("app")

@app.route("/hello")
def hello():
    return Response("Hello Flask!\n", mimetype="text/plain")