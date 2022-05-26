import base64
import json

from frejaeid.models import db, User
from frejaeid.utils import UserNotFoundException


class FrejaEID:

  @classmethod
  def get_body_for_init_auth(cls, email: str) -> str:
    human_readable_body = {
      "userInfoType": "EMAIL",
      "userInfo": email,
      "minRegistrationLevel": "EXTENDED",
    }
    b64_encoded = cls._base64encoder(human_readable_body)
    frejaedi_body = f'initAuthRequest={b64_encoded}'
    return frejaedi_body
  

  @classmethod
  def get_body_for_cancel_auth(cls, email: str) -> str:
    user = User.query.filter_by(email=email).first()

    if user:
      human_readable_body = {
        "authRef": user.freja_auth_ref,
      }
      b64_encoded = cls._base64encoder(human_readable_body)
      frejaeid_body = f'cancelAuthRequest={b64_encoded}'
      return frejaeid_body
    
    raise UserNotFoundException(f'No user corresponding to {email}.')
    

  @staticmethod
  def _base64encoder(body: dict):
    return base64.urlsafe_b64encode(
      json.dumps(body).encode('utf-8')
    ).decode('ascii')
