from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)


class RegisterRequest(BaseModel):

    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    daily_available_hours: float = Field(gt=0, le=24)
    learning_preference: str | None = Field(
        default=None,
        max_length=50,
    )

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value):
        if isinstance(value, str):
            value = value.strip()

            if not value:
                raise ValueError("Name cannot contain only whitespace.")

        return value

    @field_validator("email")
    @classmethod
    def validate_email_length(cls, value):
        if len(str(value)) > 150:
            raise ValueError("Email must not exceed 150 characters.")

        return value

    @field_validator("daily_available_hours", mode="before")
    @classmethod
    def reject_boolean_hours(cls, value):
        if isinstance(value, bool):
            raise ValueError(
                "Daily available hours must be a numeric value."
            )

        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email_length(cls, value):
        if len(str(value)) > 150:
            raise ValueError("Email must not exceed 150 characters.")

        return value


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