import base64
import io
import json
import logging
import mimetypes
import os
import requests
from functools import wraps
from hashlib import sha256
from itertools import islice
from operator import itemgetter
from urllib.parse import urlparse

from flask import Flask, render_template, request, send_file, redirect, flash, url_for, make_response
from flask_wtf.csrf import CSRFProtect

from .bytetree import ByteTree

mimetypes.add_type("application/wasm", ".wasm")

logging.basicConfig(level=logging.INFO, filemode="a", filename="local_demo.log", format="%(asctime)s;%(levelname)s;%(name)s;%(message)s")

logger = logging.getLogger('unverified_backend')

# Items are tuple
# (signature reference/signature, vote, is freja online)
SIGNED_VOTES = []

def get_auth_server_url():
    parsed_url = urlparse(os.getenv('AUTH_SERVER_URL'))

    if parsed_url.port is None:
        return f'{parsed_url.scheme}://{parsed_url.hostname}'
    
    return f'{parsed_url.scheme}://{parsed_url.hostname}:{parsed_url.port}'


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
RESULTS = "results.json"
SIGNATURES = "signatures.txt"


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


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.cookies.get('user') == None or not _is_authenticated(request.cookies.get('user')):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def _check_for_signed_votes():
    it = len(SIGNED_VOTES) - 1
    votes_for_verified_backend = []
    while (it >= 0):
        signed_vote = SIGNED_VOTES[it]
        signature_reference, encrypted_vote, freja_online, user_email = signed_vote
        if freja_online:
            signature, has_signed = _confirm_if_user_has_signed(signature_reference)
            if _has_user_already_voted(signature):
                del SIGNED_VOTES[it]
                return render_template("poll.html", data=POLL_DATA, stats=STATS, vote=None)

            if signature is not None and has_signed:
                modified_response_object = {
                    'vote': encrypted_vote,
                    'signature': signature,
                }
                _append_vote_to_ciphertexts(encrypted_vote)
                _record_signature(signature)
                del SIGNED_VOTES[it]
                print(modified_response_object)
                logger.info(f'Vote signing successful: {user_email},{signature_reference}')
                votes_for_verified_backend.append(modified_response_object)
        else:
            # `signature_reference` is signature in case of offline votes
            if _has_user_already_voted(signature_reference):
                flash('You have already voted')
                del SIGNED_VOTES[it]
                return render_template("poll.html", data=POLL_DATA, stats=STATS, vote=None)

            modified_response_object = {
                'vote': encrypted_vote,
                'signature': signature_reference,
            }
            _append_vote_to_ciphertexts(encrypted_vote)
            _record_signature(signature_reference)
            del SIGNED_VOTES[it]
            print(modified_response_object)
            votes_for_verified_backend.append(modified_response_object)

        it -= 1
    if len(votes_for_verified_backend) == 0:
        return render_template("poll.html", data=POLL_DATA, stats=STATS, vote=None)
    
    return render_template("poll.html", data=POLL_DATA, stats=STATS, show_success=True, vote=json.dumps(votes_for_verified_backend))


def _append_vote_to_ciphertexts(vote):
    with open(FILENAME, "a") as f:
        print(vote, file=f)
        STATS["nvotes"] += 1


def _record_signature(signature):
    with open(SIGNATURES, "a") as f:
        f.write(f"{signature}\n")


def _has_user_already_voted(candidate_signature):
    if candidate_signature is None:
        return False

    if not os.path.exists(SIGNATURES):
        return False
    
    with open(SIGNATURES) as f:
        current_signatures = f.readlines()
    
    for current_signature in current_signatures:
        if _get_userInfo_from_signature(current_signature) \
            == _get_userInfo_from_signature(candidate_signature):
            return True
    return False 


def _get_userInfo_from_signature(signature):
    jws_payload = signature.split('.')[1]
    jws_payload_decoded = base64.urlsafe_b64decode(jws_payload + '=' * (4 - len(jws_payload) % 4))
    payload_json = json.loads(jws_payload_decoded)
    return payload_json["userInfo"]

def _confirm_if_user_has_signed(sign_ref):
    r = requests.post(
        f'{get_auth_server_url()}/confirm_sign',
        json={
            'signRef': sign_ref,
        }
    )

    if r.status_code == 200:
        return (r.json()['signature'], True)
    
    return (None, None)

@app.route("/", methods=("GET", "POST"))
def root():
    if POLL_DATA["publicKey"] is None:
        return "Missing public key!"
    
    session_id = request.cookies.get('session')

    logger.info(f'Client: {session_id}')

    if request.method == "GET":
        return _check_for_signed_votes()

    vote = request.form.get("field")
    vote_dict = json.loads(vote)
    first = vote_dict[0]
    second = vote_dict[1]
    user_email = request.form.get('email-for-signing')
    error = _validate_vote(vote)
    if error:
        return error    

    encrypted_vote = ByteTree([ByteTree(first), ByteTree(second)]).to_byte_array()
    hashed_encryption = sha256()
    hashed_encryption.update(encrypted_vote)
    hex_string = hashed_encryption.digest().hex()
    beautified_hex_string = ' '.join([hex_string[i:i+4] for i in range(0, len(hex_string), 4)])

    logger.info(f'Vote casting: {beautified_hex_string},{user_email},{session_id}')

    sign_request = requests.post(
        f'{get_auth_server_url()}/init_sign',
        json={
            'email': user_email,
            'text': '',
            'vote': beautified_hex_string,
        }
    )

    logger.info(f'Vote signing request: {beautified_hex_string}')

    if sign_request.status_code == 200:
        response_object = sign_request.json()
        signature_reference = response_object['signRef']
        SIGNED_VOTES.append((signature_reference, eval(vote), True, user_email))
        
        return render_template("poll.html", data=POLL_DATA, stats=STATS, show_success=True, hash=beautified_hex_string)
    
    if sign_request.status_code == 418:
        flash(sign_request.json()['message'])
        return redirect(url_for('root'))

    flash('Could not cast your vote.')
    return redirect(url_for('root'))


def _validate_vote(vote):
    try:
        x = json.loads(vote)
        first = x[0]
        second = x[1]
        ByteTree.from_byte_array(first)
        ByteTree.from_byte_array(second)
    except json.JSONDecodeError:
        return "JSON Decode Error"
    except AssertionError:
        return "Vote could not be parsed into a valid ByteTree"

    len_x = len(x)
    if len_x != 2:
        return f"Expected 2 elements, got {len_x}"

    return None


def _delete_file(file):
    if os.path.exists(file):
        stat = os.stat(file)
        os.remove(file)
        return True
    return False


def _reset():
    STATS["nvotes"] = 0
    
    response_text = ""
    if _delete_file(FILENAME):
        response_text += "Successfully deleted {FILENAME}:<br/><pre>{stat}</pre>\n"
    
    if _delete_file(RESULTS):
        response_text += "Successfully deleted {RESULTS}:<br/><pre>{stat}</pre>\n"

    if _delete_file(SIGNATURES):
        response_text += "Successfully deleted {SIGNATURES}:<br/><pre>{stat}</pre>\n"

    if response_text:
        return response_text

    return "Nothing to do!"


@csrf.exempt
@app.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'GET':
        if request.cookies.get('user') != None:
            if _is_authenticated(request.cookies.get('user')):
                return redirect("/")
        return render_template("login.html")
    
    email = request.form.get("email")
    r = requests.post(
        f'{get_auth_server_url()}/init_auth',
        json={'email': email},
    )

    if r.status_code == 200:
        auth_ref = r.json()['authRef']
        res = make_response(redirect('/'))
        res.set_cookie('user', str(auth_ref))
        return res
    
    flash(str(r.text))
    return redirect(url_for("login"))


def _is_authenticated(user_identification):
    r = requests.post(
        f'{get_auth_server_url()}/authentication_validity',
        json={'authRef': user_identification}
    )

    if r.status_code == 200:
        return True
    
    return False

@app.route("/offline_vote")
def offline_vote():
    """
    Endpoint for casting a vote when FrejaEID is offline.
    """

    with open(os.path.join(app.static_folder, 'sample-signed-vote.json')) as f:
        sample_signed_vote = json.loads(f.read())

    encrypted_vote = sample_signed_vote['vote']
    signature = sample_signed_vote['signature']
    user_email = _get_email_from_jws_payload(signature)
    
    SIGNED_VOTES.append((signature, encrypted_vote, False, user_email))
    
    return redirect(url_for('root'))


def _get_email_from_jws_payload(jws_payload):
  _, payload, _ = jws_payload.split('.')
  # Needed to prevent incorrect padding error
  payload += '=='
  payload_decoded = json.loads(base64.b64decode(payload).decode('utf-8'))
  return payload_decoded['userInfo']

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
        if not os.path.isfile(PUBLIC_KEY):
            return "Missing public key!", 404

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
            download_name="ciphertexts",
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
    
    if request.method == "POST":
        with open(RESULTS, 'w+') as result:
            result.write(json.dumps(request.get_json()))
        return "OK"

    if not os.path.exists(RESULTS):
        return "Result file does not exist", 404

    content = None
    with open(RESULTS, 'r+') as result:
        content = json.loads(result.read())

    if content is None:
        return "Result file is empty", 404

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
    import sys

    if len(sys.argv) != 2 and sys.argv[1].lower() != "debug":
        print(
            "This application is not meant to be run directly. To force-run it in debug mode, pass the 'debug' argument:",
            sys.argv[0],
            "debug",
            file=sys.stderr,
        )

    app.run(debug=True)
