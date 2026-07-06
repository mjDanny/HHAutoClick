from pathlib import Path

import pytest

from app.core.config import CandidateProfile, load_profile


@pytest.fixture
def profile() -> CandidateProfile:
    return load_profile(Path("configs/profile.example.yaml")).candidate

