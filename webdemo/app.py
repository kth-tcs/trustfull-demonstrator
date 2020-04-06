import io
import json
import mimetypes
import os

from flask import Flask, render_template, request, send_file
from flask_wtf.csrf import CSRFProtect

from .bytetree import ByteTree

mimetypes.add_type("application/wasm", ".wasm")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.urandom(32)
app.debug = True
CSRFProtect(app)

with open(
    os.path.join(os.path.abspath(os.path.dirname(__file__)), "publicKey"), "rb"
) as _f:  # TODO: more properly
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


@app.route("/results")
def results():
    if not os.path.exists(FILENAME):
        return "No results found", 404

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


if __name__ == "__main__":
    app.run(debug=True)
