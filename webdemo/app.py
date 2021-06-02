import io
import json
import mimetypes
import os
from itertools import cycle, islice
from operator import itemgetter

from flask import Flask, render_template, request, send_file
from flask_wtf.csrf import CSRFProtect

from .bytetree import ByteTree

mimetypes.add_type("application/wasm", ".wasm")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.urandom(32)
app.debug = True
csrf = CSRFProtect(app)

FILENAME = "data.txt"
PUBLIC_KEY = os.path.join(os.path.abspath(os.path.dirname(__file__)), "publicKey")
POLL_DATA = {
    "question": "Who do you vote for?",
    "fields": ("Blue Candidate", "Green Candidate", "Yellow Candidate"),
    "publicKey": None,
}
STATS = {}
if os.path.exists(FILENAME):
    with open(FILENAME) as _f:
        STATS["nvotes"] = sum(1 for _ in _f)
else:
    STATS["nvotes"] = 0


def init_pk():
    if os.path.exists(PUBLIC_KEY):
        with open(PUBLIC_KEY, "rb") as _f:  # TODO: more properly
            POLL_DATA["publicKey"] = list(map(int, _f.read()))


@app.route("/", methods=("GET", "POST"))
def root():
    if POLL_DATA["publicKey"] is None:
        return "Missing public key!"

    if request.method == "GET":
        return render_template(
            "poll.html", data=POLL_DATA, stats=STATS, show_success=False
        )
    assert request.method == "POST"

    vote = request.form.get("field")
    error = _validate_vote(vote)
    if error:
        return error

    with open(FILENAME, "a") as f:
        print(vote, file=f)

    STATS["nvotes"] = STATS.get("nvotes", 0) + 1

    return render_template("poll.html", data=POLL_DATA, stats=STATS, show_success=True)


def _validate_vote(vote):
    try:
        x = json.loads(vote)
    except json.JSONDecodeError:
        return "JSON Decode Error"

    len_x = len(x)
    if len_x != 2:
        return f"Expected 2 elements, got {len_x}"

    return None


@app.route("/reset")
def reset():
    return _reset()


def _reset():
    STATS["nvotes"] = 0

    if os.path.exists(FILENAME):
        stat = os.stat(FILENAME)
        os.remove(FILENAME)
        return f"Succesfully deleted {FILENAME}:<br/><pre>   {stat}</pre>"

    return "Nothing to do!"


@csrf.exempt
@app.route("/publicKey", methods=("GET", "POST"))
def get_set_public_key():
    if request.method == "GET":
        return send_file(
            PUBLIC_KEY,
            mimetype="application/octet-stream",
            as_attachment=True,
            attachment_filename="publicKey",
        )

    new_pk = request.files.get("publicKey")
    if new_pk is None:
        return "publicKey missing", 400

    new_pk.save(PUBLIC_KEY)
    init_pk()
    _reset()

    return "OK"


@app.route("/ciphertexts")
def ciphertexts():
    if not os.path.exists(FILENAME):
        return "No ciphertexts found", 404

    with open(FILENAME) as f:
        return send_file(
            io.BytesIO(
                ByteTree(  # Single ByteTree to hold all encrypted votes
                    list(
                        map(
                            ByteTree,  # Create left & right ByteTree
                            zip(  # Convert N x 2 -> 2 x N
                                *list(
                                    map(
                                        lambda x: (
                                            ByteTree.from_byte_array(
                                                x[0]  # encrypted0
                                            ),
                                            ByteTree.from_byte_array(
                                                x[1]  # encrypted1
                                            ),
                                        ),
                                        map(json.loads, f),
                                    )
                                )
                            ),
                        )
                    )
                ).to_byte_array()
            ),
            mimetype="application/octet-stream",
            attachment_filename="ciphertexts",
            as_attachment=True,
        )


@csrf.exempt
@app.route("/results", methods=("GET", "POST"))
def results():
    d = results.__dict__
    d.setdefault("content", None)

    if request.method == "POST":
        d["content"] = request.get_json()
        return "OK"

    content = d.get("content")
    if content is None:
        return "No results found", 404

    largest = max(content.values())
    palette = [
        "#332288",
        "#88CCEE",
        "#44AA99",
        "#117733",
        "#999933",
        "#DDCC77",
        "#CC6677",
        "#882255",
        "#AA4499",
    ]
    palette = islice(palette, len(content))
    meta = dict(
        question=POLL_DATA["question"], nvotes=sum(content.values()), largest=largest
    )
    bars = sorted(content.items(), key=itemgetter(1))
    bars = [(k, 100 * v / largest, v, color) for (k, v), color in zip(bars, palette)]
    return render_template("results.html", meta=meta, bars=bars)


init_pk()
if __name__ == "__main__":
    app.run(debug=True)
