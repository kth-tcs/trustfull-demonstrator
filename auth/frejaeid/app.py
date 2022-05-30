import json
import requests
from flask import Flask, request, Response

from auth.frejaeid import urls
from auth.frejaeid.freaeid import FrejaEID
from auth.frejaeid.models import db, User


app = Flask(__name__, static_url_path='/static')

# Create an in-memory database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
db.init_app(app)
db.create_all(app=app)


@app.route('/init_auth', methods=['POST'])
def initiate_authentication():
  content = request.json
  user_email = content['email']
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
    _save_auth_ref(freja_auth_ref, user_email)
    return Response(json.dumps({'message': 'You have been logged in. Check your phone :)'}), status=200)
  
  ## Adding this for the sake of defensive programming and debugging in future.
  return Response(json.dumps({'message': f'Could not process {r.json()}'}), status=500)


@app.route('/authentication_validity', methods=['POST'])
def authentication_validity():
  content = request.json
  user_email = content['email']
  return _check_validity(user_email)


@app.route('/register_vote', methods=['POST'])
def register_vote():
  content = request.json
  user_email = content['email']
  validity = _check_validity(user_email)

  if validity.status_code == 200:
    user = User.query.filter_by(email=user_email).first()

    if user.has_voted:
      return Response(json.dumps({'message': 'You have already voted!'}), status=418)
    
    user.has_voted = True
    db.session.commit()
    return Response(json.dumps({'message': 'You are allowed to vote.'}), status=200)
  
  return validity


def _check_validity(user_email) -> Response:
  user = User.query.filter_by(email=user_email).first()

  if user is None:
    return Response(json.dumps({'message': f'Authenticate yourself, {user_email}'}), status=401)
  
  request_to_check_validity = requests.post(
    urls.get_one_result(),
    data=FrejaEID.get_body_for_checking_validity_of_user_session(user.freja_auth_ref),
    cert=_get_client_ssl_certificate(),
    verify=_get_server_certificate(),
  )

  response_body = request_to_check_validity.json()

  if request_to_check_validity.status_code == 200:
    response_body = request_to_check_validity.json()
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
  content = request.json
  user_email = content['email']

  user = User.query.filter_by(email=user_email).first()

  if user is None:
    return Response(json.dumps({'message': f'{user_email} does not exist.'}), status=401)
  
  r = requests.post(
    urls.cancel_autentication(),
    data=FrejaEID.get_body_for_cancel_auth(user.freja_auth_ref),
    cert=_get_client_ssl_certificate(),
    verify=_get_server_certificate()
  )

  if r.status_code == 200:
    return Response(json.dumps({'message': f'Authentication cancelled for {user_email}.'}))
  
  if r.json()['code'] == 1100:
    return Response(json.dumps({'message': 'You are not in the middle of authentication process.'}), status=400)
  
  if r.json()['code'] == 1004:
    return Response(json.dumps({'message': 'You are not allowed to call this method.'}), status=403)

  return Response(json.dumps({'message': f'Could not process {r.json()}'}), status=500)


def _save_auth_ref(auth_ref: str, user_email: str) -> None:
  user = User.query.filter_by(email=user_email).first()

  if user:
    user.freja_auth_ref = auth_ref
    db.session.commit()
  
  else:
    new_user = User(email=user_email, freja_auth_ref=auth_ref)

    # add the new user to the database
    db.session.add(new_user)
    db.session.commit()


# FrejaEid uses it to identify who is making API requests
def _get_client_ssl_certificate():
  return (
    'auth/frejaeid/static/kth_client.crt',
    'auth/frejaeid/static/kth_client.key',
  )  


# Our service uses to trust FrejaEid server
def _get_server_certificate():
  return 'auth/frejaeid/static/freja.crt'
