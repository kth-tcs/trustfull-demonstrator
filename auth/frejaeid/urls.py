# Whatever you do in life, do not append a slash at the end of the URL.
# I already wasted 2 hours over this. :(

def _root_url():
  return 'https://services.test.frejaeid.com'


def _auth():
  return f'{_root_url()}/authentication/1.0'


def initiate_authentication():
  return f'{_auth()}/initAuthentication'


def get_one_result():
  return f'{_auth()}/getOneResult'


def cancel_autentication():
  return f'{_auth()}/cancel'


def _sign():
  return f'{_root_url()}/sign/1.0'


def initiate_signing():
  return f'{_sign()}/initSignature'
