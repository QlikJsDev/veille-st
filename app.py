from flask import Flask, jsonify, send_from_directory
from core import fetch_all

app = Flask(__name__)


@app.route("/")
def index():
    return send_from_directory("docs", "index.html")


@app.route("/articles.json")
def articles_json():
    data = fetch_all()
    return jsonify(data)


if __name__ == "__main__":
    app.run(debug=True, port=5000, threaded=True)
