import json
import requests
from flask import Flask, request, Response

from frejaeid import urls
from frejaeid.freaeid import FrejaEID
from frejaeid.models import db, User
from frejaeid.utils import UserNotFoundException


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
  freja_auth_ref = r.json()['authRef']
  _save_auth_ref(freja_auth_ref, user_email)

  return f'{r.json()}'


@app.route('/cancel', methods=['POST'])
def cancel_authentication():
  content = request.json
  user_email = content['email']
  try:
    r = requests.post(
      urls.cancel_autentication(),
      data=FrejaEID.get_body_for_cancel_auth(user_email),
      cert=_get_client_ssl_certificate(),
      verify=_get_server_certificate()
    )
  except UserNotFoundException:
    return Response(json.dumps({'message': f'{user_email} does not exist.'}), status=404)

  if r.status_code == 200:
    return Response(json.dumps({'message': f'Authentication cancelled for {user_email}.'}))
  
  if r.json()['code'] == 1100:
    return Response(json.dumps({'message': 'Already cancelled'}), status=400)
  
  if r.json()['code'] == 1004:
    return Response(json.dumps({'message': 'You are not allowed to call this method.'}), status=403)

  return r.json()


def _save_auth_ref(auth_ref: str, user_email: str) -> None:
  user = User.query.filter_by(email=user_email).first()

  if user:
    user.freja_auth_ref = auth_ref
  
  new_user = User(email=user_email, freja_auth_ref=auth_ref)

  # add the new user to the database
  db.session.add(new_user)
  db.session.commit()


# FrejaEid uses it to identify who is making API requests
def _get_client_ssl_certificate():
  return (
    'frejaeid/static/kth_client.crt',
    'frejaeid/static/kth_client.key',
  )  


# Our service uses to trust FrejaEid server
def _get_server_certificate():
  return 'frejaeid/static/freja.crt'
