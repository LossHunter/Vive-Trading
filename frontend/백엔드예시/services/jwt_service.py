import jwt
from datetime import datetime, timedelta, timezone
import httpx
from google.oauth2 import id_token
from google.auth.transport import requests
import os
from dotenv import load_dotenv

class TokenJwt():
    def __init__(self, authorize_code):
        load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

        self.code = authorize_code
        self.SECRET_KEY = "dev_secret_key_12345"
        self.ALGORITHM = "HS256"
        self.GOOGLE_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
        self.GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
        self.REDIRECT_URI = os.getenv("REDIRECT_URI") # 배포시 env 파일 변경할 것

    async def authorize_token(self):
        async with httpx.AsyncClient() as client:
            res = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": self.GOOGLE_CLIENT_ID,
                    "client_secret": self.GOOGLE_CLIENT_SECRET,
                    "code": self.code,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.REDIRECT_URI,
                    "scope": "openid email profile"
                }
            )
            token_json = res.json()
            
            return token_json.get("id_token")

    def verify_google(self, id_token_str):
        try:
            idinfo = id_token.verify_oauth2_token(
                id_token_str,
                requests.Request(),
                self.GOOGLE_CLIENT_ID,
                clock_skew_in_seconds=10 # 서버 시간과 구글 서버시간 차이때문에 생기는 버그가 있어서 해당 구문 반드시 포함
            )
            return idinfo 
        except ValueError as e:
            print("Google ID Token 검증 실패")
            print("reason : ", e)
            return None
        
    async def generation(self):
        id_token_str = await self.authorize_token()
        google_info = self.verify_google(id_token_str)
        if google_info is None:
            raise ValueError("Invalid Google Access Token")
        
        payload = {
            "sub": google_info["sub"],        
            "email": google_info.get("email"), 
            "name": google_info.get("name"), 
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=24)).timestamp())
        }

        return payload, jwt.encode(payload, self.SECRET_KEY, algorithm=self.ALGORITHM)


# token = TokenJwt("4/0Ab32j91ieDlbL5sC2BKBxiE80YpIsygeJxA1JveP3KwGpNQYo9vwzfspnmosSRR9Vj1YvQ")
# jwt_token = asyncio.run(token.generation())
# print(jwt_token)