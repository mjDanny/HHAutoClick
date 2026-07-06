from dataclasses import dataclass

from app.core.config import Settings
from app.core.exceptions import EmployerQuestionsDetected, ManualReviewRequired
from app.hh.models import NormalizedVacancy


@dataclass(frozen=True)
class ApplicationResult:
    sent: bool
    status: str
    reason: str


class ApplicationPipeline:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def preflight(self, vacancy: NormalizedVacancy, score: int, manual_approved: bool) -> None:
        if vacancy.has_test:
            raise EmployerQuestionsDetected("vacancy has employer test")

        if not manual_approved and not self.settings.auto_apply_enabled:
            raise ManualReviewRequired("manual approval is required")

        if not manual_approved and score < self.settings.min_score_for_auto_apply:
            raise ManualReviewRequired("score is below auto-apply threshold")

    def apply(
        self,
        vacancy: NormalizedVacancy,
        score: int,
        manual_approved: bool,
    ) -> ApplicationResult:
        self.preflight(vacancy, score, manual_approved)
        if self.settings.dry_run:
            return ApplicationResult(False, "dry_run", "application sending is disabled by DRY_RUN")
        return ApplicationResult(
            False,
            "not_implemented",
            "real application sending is not implemented",
        )
