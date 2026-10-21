from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    daily_available_hours: float = Field(gt=0, le=24)
    learning_preference: str | None = Field(
        default=None,
        max_length=50,
    )


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class AuthenticatedStudent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    student_id: int
    name: str
    email: EmailStr
    daily_available_hours: float
    learning_preference: str | None = None
