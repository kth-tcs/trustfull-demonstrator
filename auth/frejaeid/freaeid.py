import base64
import json

from auth.frejaeid.models import db


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
  def get_body_for_checking_validity_of_user_session(cls, auth_ref: str) -> str:
    human_readable_body = {
      "authRef": auth_ref,
    }
    b64_encoded = cls._base64encoder(human_readable_body)
    frejaeid_body = f'getOneAuthResultRequest={b64_encoded}'
    return frejaeid_body

  @classmethod
  def get_body_for_cancel_auth(cls, auth_ref: str) -> str:
    human_readable_body = {
      "authRef": auth_ref,
    }
    b64_encoded = cls._base64encoder(human_readable_body)
    frejaeid_body = f'cancelAuthRequest={b64_encoded}'
    return frejaeid_body

  @classmethod
  def get_body_for_init_sign(cls, email: str, text: str, vote: str) -> str:
    human_readable_body = {
      "userInfoType": "EMAIL",
      "userInfo": email,
      "minRegistrationLevel": "EXTENDED",
      "title": "Verificatum election",
      "pushNotification": {
        "title": "Hi from VCS :)",
        "text": "Please sign your vote"
      },
      "dataToSignType": "EXTENDED_UTF8_TEXT",
      "dataToSign": {
        "text": f"{text}",
        "binaryData": f"{vote}"
      },
      "signatureType": "EXTENDED",
    }
    b64_encoded = cls._base64encoder(human_readable_body)
    frejaedi_body = f'initSignRequest={b64_encoded}'
    return frejaedi_body

  @staticmethod
  def _base64encoder(body: dict):
    return base64.urlsafe_b64encode(
      json.dumps(body).encode('utf-8')
    ).decode('ascii')
