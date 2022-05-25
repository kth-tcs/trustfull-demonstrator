import requests
from flask import Flask, request, url_for

from frejaeid import urls
from frejaeid.freaeid import FrejaEID

app = Flask(__name__, static_url_path='/static')


@app.route('/init_auth', methods=['POST'])
def initiate_authentication():
  content = request.json
  user_email = content['email']
  certificate = (
    'frejaeid/static/kth_client.crt',
    'frejaeid/static/kth_client.key',
  )
  r = requests.post(
    urls.initiate_authentication(),
    data=FrejaEID.get_body_for_init_auth(user_email),
    cert=certificate,
    verify='frejaeid/static/freja.crt'
  )
  return f'{r.json()}'

