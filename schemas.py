from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class Language(BaseModel):
    code: str
    name: str

    class Config:
        from_attributes = True

class CFTag(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

class CFProblemStatistics(BaseModel):
    id: int
    solved_count: int
    last_updated: datetime

    class Config:
        from_attributes = True

class CFContest(BaseModel):
    id: int
    cf_contest_id: int
    name: str
    type: Optional[str] = None
    phase: Optional[str] = None
    start_time: Optional[datetime] = None
    duration: Optional[int] = None
    contest_url: Optional[str] = None

    class Config:
        from_attributes = True

class CFContestWithProblems(CFContest):
    problems: List['CFProblem']

class CFProblem(BaseModel):
    id: int
    problem_uid: str
    cf_problem_index: str
    name: str
    rating: Optional[int] = None
    problem_url: Optional[str] = None

    class Config:
        from_attributes = True

class CFProblemWithDetails(CFProblem):
    contests: List[CFContest]
    tags: List[CFTag]
    statistics: Optional[List['CFProblemStatistics']] = None