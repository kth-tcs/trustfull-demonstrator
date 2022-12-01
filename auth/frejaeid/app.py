import base64
import json
import requests
from flask import Flask, request, Response

# from auth.frejaeid.sign_confirmation import BackgroundThreadFactory, TASKS_QUEUE
from auth.frejaeid import urls
from auth.frejaeid.payload import FrejaEID
from auth.frejaeid.models import db, User


app = Flask(__name__, static_url_path='/static')
# vote_signing_thread = BackgroundThreadFactory.create()

# if not (app.debug or os.environ.get('FLASK_ENV') == 'development') or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
#   vote_signing_thread.start()

#   original_handler = signal.getsignal(signal.SIGINT)

#   def sigint_handler(signum, frame):
#     vote_signing_thread.stop()

#     # wait until thread is finished
#     if vote_signing_thread.is_alive():
#         vote_signing_thread.join()

#     original_handler(signum, frame)

#   try:
#     signal.signal(signal.SIGINT, sigint_handler)
#   except ValueError as e:
#     print(f'{e}. Continuing execution...')

# Create an in-memory database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
db.create_all(app=app)


def _validate_auth_body(content):
  if content is None:
    return Response(json.dumps({'message': '`Content-Type` header must be `application/json`.'}), status=400)
  
  user_email = content.get('email')
  if user_email is None:
    return Response(json.dumps({'message': '\"email\" atttribute missing in payload'}), status=400)
  
  return Response(json.dumps({'message': 'All okay!'}))


def _validate_body_with_auth_ref(content):
  if content is None:
    return Response(json.dumps({'message': '`Content-Type` header must be `application/json`.'}), status=400)
  
  auth_ref = content.get('authRef')
  if auth_ref is None:
    return Response(json.dumps({'message': '\"authRef\" atttribute missing in payload'}), status=400)
  
  return Response(json.dumps({'message': 'All okay!'}))


@app.route('/init_auth', methods=['POST'])
def initiate_authentication():
  request_payload = _validate_auth_body(request.get_json())

  if request_payload.status_code == 400:
    return request_payload
  
  user_email = request.get_json().get('email')

  r = requests.post(
    urls.initiate_authentication(),
    data=FrejaEID.get_body_for_init_auth(user_email),
    cert=_get_client_ssl_certificate(),
    verify=_get_server_certificate()
  )
  if r.status_code == 422 and r.json()['code'] == 2000:
    return Response(json.dumps({'message': 'Why are you doing it again? See your phone!'}), status=400)

  if r.status_code == 200:
    freja_auth_ref = r.json()['authRef']
    user, created = _save_auth_ref(freja_auth_ref)
    if created:
      return Response(json.dumps(
        {
          'message': 'You have been logged in. Check your phone :)',
          'authRef': freja_auth_ref,
        }
      ), status=200)
    else:
      return Response(json.dumps(
        {
          'message': 'You have already been authenticated with Freja. Please proceed to vote.',
          'authRef': freja_auth_ref,
        }
      ), status=403)
  
  ## Adding this for the sake of defensive programming and debugging in future.
  return Response(json.dumps({'message': f'Could not process {r.json()}'}), status=500)


@app.route('/authentication_validity', methods=['POST'])
def authentication_validity():
  request_payload = _validate_body_with_auth_ref(request.get_json())

  if request_payload.status_code == 400:
    return request_payload
  
  auth_ref = request.get_json().get('authRef')
  
  return _check_validity(auth_ref)


def _register_vote(auth_ref):
  validity = _check_validity(auth_ref)

  if validity.status_code == 200:
    return Response(json.dumps({'message': 'You are allowed to vote.'}), status=200)
  
  return validity


def _check_validity(auth_ref) -> Response:
  user = User.query.filter_by(freja_auth_ref=auth_ref).first()

  if user is None:
    return Response(json.dumps({'message': f'You are not authenticated.'}), status=401)
  
  request_to_check_validity = requests.post(
    urls.get_one_result(),
    data=FrejaEID.get_body_for_checking_validity_of_user_session(user.freja_auth_ref),
    cert=_get_client_ssl_certificate(),
    verify=_get_server_certificate(),
  )

  response_body = request_to_check_validity.json()

  if request_to_check_validity.status_code == 200:
    if response_body['status'] == 'CANCELED':
      return Response(json.dumps({'message': 'You denied the authentication on the mobile and hence cannot vote. चित भी मेरी पट भी मेरी'}), status=403)

    if response_body['status'] == 'RP_CANCELED':
      return Response(json.dumps({'message': 'You cancelled authentication via an API call \'/cancel\''}), status=403)

    if response_body['status'] != 'APPROVED':
      return Response(json.dumps({'message': 'You have not approved the authentication.'}), status=403)
    
    return Response(json.dumps({'message': 'Your authentication is valid.'}), status=200)

  if response_body['code'] == 1100:
    return Response(json.dumps({'message': 'Reauthenicate with Freja e-ID'}), status=403)
  
  return Response(json.dumps({'message': f'Could not process {response_body}'}), status=500)


@app.route('/cancel', methods=['POST'])
def cancel_authentication():
  request_payload = _validate_body_with_auth_ref(request.get_json())

  if request_payload.status_code == 400:
    return request_payload
  
  auth_ref = request.get_json().get('authRef')

  user = User.query.filter_by(freja_auth_ref=auth_ref).first()

  if user is None:
    return Response(json.dumps({'message': 'User does not exist.'}), status=401)
  
  r = requests.post(
    urls.cancel_autentication(),
    data=FrejaEID.get_body_for_cancel_auth(user.freja_auth_ref),
    cert=_get_client_ssl_certificate(),
    verify=_get_server_certificate()
  )

  if r.status_code == 200:
    return Response(json.dumps({'message': f'Authentication cancelled for the given authentication reference.'}))
  
  if r.json()['code'] == 1100:
    return Response(json.dumps({'message': 'You are not in the middle of authentication process.'}), status=400)
  
  if r.json()['code'] == 1004:
    return Response(json.dumps({'message': 'You are not allowed to call this method.'}), status=403)

  return Response(json.dumps({'message': f'Could not process {r.json()}'}), status=500)


def _save_auth_ref(auth_ref: str) -> None:
  user = User.query.filter_by(freja_auth_ref=auth_ref).first()

  if user:
    return (user, False)
  
  else:
    new_user = User(freja_auth_ref=auth_ref)

    # add the new user to the database
    db.session.add(new_user)
    db.session.commit()

    return (new_user, True)


def _validate_sign_body(content):
  if content is None:
    return Response(json.dumps({'message': '`Content-Type` header must be `application/json`.'}), status=400)
  
  user_email = content.get('email')
  if user_email is None:
    return Response(json.dumps({'message': '\'email\' atttribute missing in payload'}), status=400)
  
  vote = content.get('vote')
  if vote is None:
    return Response(json.dumps({'message': '\'vote\' atttribute missing in payload'}), status=400)
  
  return Response(json.dumps({'message': 'All okay!'}))

@app.route('/init_sign', methods=['POST'])
def initiate_signing():
  request_payload = _validate_sign_body(request.get_json())

  if request_payload.status_code == 400:
    return request_payload
  
  auth_ref = request.get_json().get('authRef')
  user_email = request.get_json().get('email')
  vote = request.get_json().get('vote')

  hash_bytes = bytes(vote, 'utf-8')
  b64encode_bytes_vote = base64.b64encode(hash_bytes)
  b64encode_bytes_string = b64encode_bytes_vote.decode('utf-8')

  can_vote = _register_vote(auth_ref)
  if can_vote.status_code == 200:
    r = requests.post(
      urls.initiate_signing(),
      data=FrejaEID.get_body_for_init_sign(user_email, b64encode_bytes_string),
      cert=_get_client_ssl_certificate(),
      verify=_get_server_certificate()
    )

    if r.status_code == 200:
      freja_sign_ref = r.json()['signRef']
      return Response(json.dumps({
        'message': 'Here is the signature reference',
        'signRef': freja_sign_ref
      }))
    
    ## Adding this for the sake of defensive programming and debugging in future.
    return Response(json.dumps({'message': f'Could not process {r.json()}'}), status=500)
  
  return can_vote

@app.route('/confirm_sign', methods=['POST'])
def confirm_if_user_has_signed():
  # Todo: add malformed request verifier
  sign_ref = request.get_json().get('signRef')
  r = requests.post(
    urls.confirm_signing(),
    data=FrejaEID.get_body_for_confirming_signature(sign_ref),
    cert=_get_client_ssl_certificate(),
    verify=_get_server_certificate()
  )

  if r.status_code == 200:
    status = r.json()['status']
    if status == 'APPROVED':
      return Response(json.dumps({
        'message': 'Signing successful',
        'signature': r.json()['details']
      }))
    else:
      return Response(json.dumps({
        'message': 'Signing unsuccessful'
      }), status=400)
  
  return Response(json.dumps({'message': 'Connection with Freja failed'}), status=500)

# FrejaEid uses it to identify who is making API requests
def _get_client_ssl_certificate():
  return (
    'auth/frejaeid/static/kth_client.crt',
    'auth/frejaeid/static/kth_client.key',
  )  


# Our service uses to trust FrejaEid server
def _get_server_certificate():
  return 'auth/frejaeid/static/freja.crt'
