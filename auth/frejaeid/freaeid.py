import base64
import json


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
  

  @staticmethod
  def _base64encoder(body: dict):
    return base64.urlsafe_b64encode(
      json.dumps(body).encode('utf-8')
    ).decode('ascii')
