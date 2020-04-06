import mimetypes
import os

from flask import Flask, render_template, request, send_file
from flask_wtf.csrf import CSRFProtect

mimetypes.add_type("application/wasm", ".wasm")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.urandom(32)
CSRFProtect(app)

with open("publicKey", "rb") as _f:  # TODO: more properly
    POLL_DATA = {
        "question": "Who do you vote for?",
        "fields": ("Napoleon", "George Bush", "Christina, Queen of Sweden"),
        "publicKey": list(map(int, _f.read())),
    }
FILENAME = "data.txt"
STATS = {}
if os.path.exists(FILENAME):
    with open(FILENAME) as _f:
        STATS["nvotes"] = sum(1 for _ in _f)
else:
    STATS["nvotes"] = 0


@app.route("/", methods=("GET", "POST"))
def root():
    if request.method == "GET":
        return render_template("poll.html", data=POLL_DATA, stats=STATS)

    vote = request.form.get("field")
    with open(FILENAME, "a") as f:
        print(vote, file=f)

    STATS["nvotes"] = STATS.get("nvotes", 0) + 1

    return render_template("thankyou.html", data=POLL_DATA)


@app.route("/reset")
def reset():
    STATS["nvotes"] = 0

    if os.path.exists(FILENAME):
        stat = os.stat(FILENAME)
        os.remove(FILENAME)
        return f"Succesfully deleted {FILENAME}:<br/><pre>   {stat}</pre>"

    return "Nothing to do!"


# XXX: Someone needs to post-process these. Options are:
# 1. This app can implement a rough ByteTree, enough to do the translation
# 2. (receiver side) A Java-based program that uses verificatum
# 3. (receiver side) A VJSC-based node program
@app.route("/results")
def results():
    if os.path.exists(FILENAME):
        return send_file(FILENAME)
    return "No results found", 404


if __name__ == "__main__":
    app.run(debug=True)
