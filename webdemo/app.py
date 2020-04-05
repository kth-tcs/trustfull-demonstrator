import os

from flask import Flask, render_template, request, send_file
from flask_wtf.csrf import CSRFProtect

app = Flask(__name__)
app.config["SECRET_KEY"] = os.urandom(32)
CSRFProtect(app)

POLL_DATA = {
    "question": "Who do you vote for?",
    "fields": ("Napoleon", "George Bush", "Christina, Queen of Sweden"),
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
    if os.path.exists(FILENAME):
        stat = os.stat(FILENAME)
        os.remove(FILENAME)
        STATS["nvotes"] = 0
        return f"Succesfully deleted {FILENAME}:<br/><pre>   {stat}</pre>"
    return "Nothing to do!"


@app.route("/results")
def results():
    if os.path.exists(FILENAME):
        return send_file(FILENAME)
    return "No results found", 404


if __name__ == "__main__":
    app.run(debug=True)
