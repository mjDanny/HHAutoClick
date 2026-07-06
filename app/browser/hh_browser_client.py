from typing import Protocol

from app.core.exceptions import (
    CaptchaDetected,
    ChallengeDetected,
    EmployerQuestionsDetected,
    LoginRequired,
)


class PageLike(Protocol):
    url: str

    async def title(self) -> str:
        raise NotImplementedError

    async def content(self) -> str:
        raise NotImplementedError


class HHBrowserClient:
    async def assert_safe_page(self, page: PageLike) -> None:
        title = (await page.title()).lower()
        url = page.url.lower()
        content = (await page.content()).lower()

        captcha_markers = ["captcha", "капча", "подтвердите, что вы не робот"]
        if any(marker in url or marker in title or marker in content for marker in captcha_markers):
            raise CaptchaDetected("hh.ru challenge detected; manual review required")

        challenge_markers = ["challenge", "проверка безопасности", "security check"]
        has_challenge = any(
            marker in url or marker in title or marker in content
            for marker in challenge_markers
        )
        if has_challenge:
            raise ChallengeDetected("hh.ru safety challenge detected; manual review required")

        login_markers = ["account/login", "login", "войти в личный кабинет"]
        if any(marker in url or marker in title for marker in login_markers):
            raise LoginRequired("hh.ru login page detected; manual login required")

        employer_question_markers = [
            "вопросы работодателя",
            "ответьте на вопросы",
            "тестовое задание",
        ]
        if any(marker in content for marker in employer_question_markers):
            raise EmployerQuestionsDetected(
                "employer questions or test detected; manual review required"
            )
