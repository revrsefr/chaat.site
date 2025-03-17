import jwt
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

def decode_jwt(token, secret, issuer):
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            issuer=issuer,
            options={"verify_exp": True}
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token has expired.")
        return None
    except jwt.InvalidIssuerError:
        logger.warning("JWT issuer mismatch.")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid JWT token: {e}")
        return None

def is_jwt_token(token):
    return token and token.startswith('ey') and len(token.split('.')) == 3