from flask import Flask, jsonify
import os

app = Flask(__name__)

@app.route('/') # Question page
def landing():
    env_vars = list(os.environ)
    return jsonify(env_vars)

def run(port):
    app.run(port=port, debug=False)
