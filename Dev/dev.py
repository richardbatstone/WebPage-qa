from flask import Flask, jsonify
import os
import requests

app = Flask(__name__)

@app.route('/') # Question page
def landing():
    env_vars = list(os.environ)
    return jsonify(env_vars)

if __name__=="__main__":
    app.run(port=8080, debug=False)
