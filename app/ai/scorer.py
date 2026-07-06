from dataclasses import dataclass, field

from app.core.config import CandidateProfile
from app.hh.models import NormalizedVacancy


@dataclass(frozen=True)
class ScoreResult:
    score: int
    reasons: list[str] = field(default_factory=list)
    matched_skills: list[str] = field(default_factory=list)
    concerns: list[str] = field(default_factory=list)


class RuleBasedVacancyScorer:
    def score(self, vacancy: NormalizedVacancy, profile: CandidateProfile) -> ScoreResult:
        score = 35
        reasons: list[str] = ["base score for Python backend target"]
        concerns: list[str] = []
        matched_skills: list[str] = []
        text = vacancy.search_text
        title = vacancy.title.lower()

        for target_title in profile.preferences.target_titles:
            if all(part.lower() in title for part in target_title.split()[:2]):
                score += 15
                reasons.append(f"title matches target: {target_title}")
                break

        for skill in profile.confirmed_skills:
            if skill.lower() in text:
                score += 3
                matched_skills.append(skill)

        for skill in profile.growth_skills:
            if skill.lower() in text:
                score -= 2
                concerns.append(f"requires growth-only skill: {skill}")

        if profile.preferences.remote_is_positive and "удален" in text:
            score += 5
            reasons.append("remote work is positive")

        if vacancy.has_test:
            score -= 10
            concerns.append("vacancy has employer test")

        if "senior" in text and "middle" not in text:
            score -= 8
            concerns.append("may target senior level")

        bounded_score = max(0, min(100, score))
        unique_matched = list(dict.fromkeys(matched_skills))
        return ScoreResult(
            score=bounded_score,
            reasons=reasons,
            matched_skills=unique_matched,
            concerns=concerns,
        )

