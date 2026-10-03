from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field, StringConstraints

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
PostText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=3000)]
CommentText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
ObjectIdStr = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{24}$")]
# Empty, or an optional leading + followed by 7-20 digits, spaces, dashes or parentheses.
Phone = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^(\+?[0-9 ()-]{7,20})?$")
]
# 3-30 chars: letters, digits, dot and underscore; stored lowercased. The pattern is checked
# before to_lower is applied, so it has to accept uppercase too.
Username = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_lower=True, pattern=r"^[A-Za-z0-9_.]{3,30}$"),
]
Age = Annotated[int, Field(ge=13, le=120)]
Gender = Literal["female", "male", "non_binary", "other", "prefer_not_to_say"]


def _check_birthdate(value: date) -> date:
    if value > datetime.now(UTC).date():
        raise ValueError("Date of birth cannot be in the future")
    if value.year < 1900:
        raise ValueError("Date of birth must be after 1900")
    return value


BirthDate = Annotated[date, AfterValidator(_check_birthdate)]


Password = Annotated[str, StringConstraints(min_length=8, max_length=128)]


class SignupIn(BaseModel):
    name: Name
    username: Username
    password: Password
    headline: ShortText = ""
    location: ShortText = ""


class LoginIn(BaseModel):
    username: Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, max_length=30)]
    password: Annotated[str, StringConstraints(max_length=128)]


class UserUpdate(BaseModel):
    """Partial update: only fields present in the request change; null clears optional ones."""

    name: Name | None = None
    username: Username | None = None
    headline: ShortText | None = None
    location: ShortText | None = None
    about: LongText | None = None
    phone: Phone | None = None
    age: Age | None = None
    gender: Gender | None = None
    date_of_birth: BirthDate | None = None


class UserSummary(BaseModel):
    id: str
    name: str
    headline: str


class ResumeInfo(BaseModel):
    filename: str
    size: int
    uploaded_at: datetime


class User(UserSummary):
    """A member. phone, age, gender and date_of_birth are only filled in for the member themself."""

    username: str | None
    location: str
    about: str
    phone: str
    age: int | None
    gender: Gender | None
    date_of_birth: date | None
    resume: ResumeInfo | None
    connections: list[str]


class ConnectionIn(BaseModel):
    target_id: ObjectIdStr


# The acting user always comes from the session cookie, never from the request body.
class PostIn(BaseModel):
    content: PostText


class CommentIn(BaseModel):
    text: CommentText


class Comment(BaseModel):
    id: str
    author: UserSummary
    text: str
    created_at: datetime
    edited_at: datetime | None = None


class Post(BaseModel):
    id: str
    author: UserSummary
    content: str
    created_at: datetime
    edited_at: datetime | None
    likes: list[str]
    comments: list[Comment]
