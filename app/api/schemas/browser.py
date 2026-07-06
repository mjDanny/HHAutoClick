from typing import Literal

from pydantic import BaseModel


class BrowserLoginCheckView(BaseModel):
    status: Literal["logged_in", "logged_out", "captcha", "challenge", "unknown"]
    url: str
    message: str


class BrowserPageCheckView(BaseModel):
    status: Literal[
        "ok",
        "login_required",
        "captcha",
        "challenge",
        "employer_questions",
        "test_task",
        "unknown",
    ]
    url: str
    message: str

