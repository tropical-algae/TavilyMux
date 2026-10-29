from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    secret: str = Field(min_length=1, max_length=500)
    remember: bool = False


class LoginResponse(BaseModel):
    authenticated: bool = True
    csrf_token: str


class ChangeAdminSecretRequest(BaseModel):
    current_secret: str = Field(min_length=1, max_length=500)
    new_secret: str = Field(min_length=12, max_length=500)


class AuthStatus(BaseModel):
    authenticated: bool = True
