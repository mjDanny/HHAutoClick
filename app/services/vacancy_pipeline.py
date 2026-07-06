from dataclasses import dataclass

from app.ai.scorer import RuleBasedVacancyScorer, ScoreResult
from app.core.config import CandidateProfile
from app.hh.filters import BlacklistFilter, DuplicateGuard
from app.hh.models import NormalizedVacancy


@dataclass(frozen=True)
class VacancyPipelineResult:
    accepted: bool
    reason: str
    score: ScoreResult | None = None


class VacancyPipeline:
    def __init__(
        self,
        profile: CandidateProfile,
        scorer: RuleBasedVacancyScorer,
        blacklist: BlacklistFilter,
        duplicate_guard: DuplicateGuard,
        min_score_for_review: int,
    ) -> None:
        self.profile = profile
        self.scorer = scorer
        self.blacklist = blacklist
        self.duplicate_guard = duplicate_guard
        self.min_score_for_review = min_score_for_review

    def process(self, vacancy: NormalizedVacancy) -> VacancyPipelineResult:
        blacklist_decision = self.blacklist.check(vacancy)
        if not blacklist_decision.allowed:
            return VacancyPipelineResult(False, blacklist_decision.reason or "blacklisted")

        if self.duplicate_guard.is_duplicate(vacancy):
            return VacancyPipelineResult(False, "duplicate vacancy")

        self.duplicate_guard.remember(vacancy)
        score = self.scorer.score(vacancy, self.profile)
        if score.score < self.min_score_for_review:
            return VacancyPipelineResult(False, "score below review threshold", score)

        return VacancyPipelineResult(True, "ready for review", score)

