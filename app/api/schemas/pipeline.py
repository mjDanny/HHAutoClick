from pydantic import BaseModel


class ReadOnlyPipelineSummaryView(BaseModel):
    found: int
    new: int
    duplicates: int
    blacklisted: int
    saved: int
    errors: int
    searches: int
    error_messages: list[str]


class StatsView(BaseModel):
    total: int
    new: int
    skipped: int

