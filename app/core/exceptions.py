class AppError(Exception):
    """Base application error."""


class ManualReviewRequired(AppError):
    """Raised when an action must stop and be shown to the user."""


class CaptchaDetected(ManualReviewRequired):
    """Raised when hh.ru shows a CAPTCHA or challenge page."""


class ChallengeDetected(ManualReviewRequired):
    """Raised when hh.ru shows an unexpected safety challenge."""


class LoginRequired(ManualReviewRequired):
    """Raised when the user session is not authenticated."""


class EmployerQuestionsDetected(ManualReviewRequired):
    """Raised when a vacancy has employer questions or tests."""
