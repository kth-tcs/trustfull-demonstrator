# Whatever you do in life, do not append a slash at the end of the URL.
# I already wasted 2 hours over this. :(

def _root_url():
  return 'https://services.test.frejaeid.com/authentication/1.0'


def initiate_authentication():
  return f'{_root_url()}/initAuthentication'
