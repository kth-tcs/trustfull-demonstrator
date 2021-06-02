import io
import json
import mimetypes
import os
from itertools import islice
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


def init_stats():
    if os.path.exists(FILENAME):
        STATS["nvotes"] = _count_lines(FILENAME)
    else:
        STATS["nvotes"] = 0


def _count_lines(filename):
    with open(filename) as f:
        return sum(1 for _ in f)


def init_pk():
    if os.path.exists(PUBLIC_KEY):
        with open(PUBLIC_KEY, "rb") as f:
            # Public key as int array, to be directly pasted in Javascript code
            POLL_DATA["publicKey"] = [int(x) for x in f.read()]


@app.route("/", methods=("GET", "POST"))
def root():
    if POLL_DATA["publicKey"] is None:
        return "Missing public key!"

    if request.method == "GET":
        return render_template(
            "poll.html", data=POLL_DATA, stats=STATS, show_success=False
        )

    vote = request.form.get("field")
    error = _validate_vote(vote)
    if error:
        return error

    with open(FILENAME, "a") as f:
        print(vote, file=f)
    STATS["nvotes"] += 1

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
        return f"Successfully deleted {FILENAME}:<br/><pre>   {stat}</pre>"

    return "Nothing to do!"


@csrf.exempt
@app.route("/publicKey", methods=("GET", "POST"))
def publickey():
    """
    Endpoint for the public key.

    POST: Receive the public key from the admin after the mix network generates it. Currently, no authentication is
        done. The key should be provided as an attachment in the POST request, the file name should be `publicKey`.
        Example curl call: `curl -i -X POST -F publicKey=@./publicKey <root URL>/publicKey`.
    GET: Return the current public key as an octet stream.

    This function is exempt from CSRF since it is not meant to be accessed from the web interface.
    """
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
    """
    Endpoint for the encrypted cipher votes.

    Returns the current votes as a byte tree encoded as an octet stream.
    """
    if not os.path.exists(FILENAME):
        return "No ciphertexts found", 404

    with open(FILENAME) as f:
        # Read votes as received by encrypt(s) from poll.html
        vote_list = [
            (
                ByteTree.from_byte_array(x[0]),  # encrypted0
                ByteTree.from_byte_array(x[1]),  # encrypted1
            )
            for x in map(json.loads, f)
        ]
        # Convert N x 2 -> 2 x N
        left, right = tuple(zip(*vote_list))
        # Single ByteTree to hold all encrypted votes
        byte_tree = ByteTree([ByteTree(left), ByteTree(right)])

        return send_file(
            io.BytesIO(byte_tree.to_byte_array()),
            mimetype="application/octet-stream",
            attachment_filename="ciphertexts",
            as_attachment=True,
        )


@csrf.exempt
@app.route("/results", methods=("GET", "POST"))
def results():
    """
    Endpoint for the results page.

    POST: Receive the tally from the admin after the mix net has finished executing. Currently, no authentication is
        done. Format should be a JSON dictionary candidate -> values.
    GET: Return a page with a visualization of the received results.

    This function is exempt from CSRF since it is not meant to be accessed from the web interface.
    """
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


init_stats()
init_pk()
if __name__ == "__main__":
    app.run(debug=True)
