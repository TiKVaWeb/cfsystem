from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
import schemas, crud
from database import get_db
from typing import Optional, List
from datetime import datetime

app = FastAPI()

templates = Jinja2Templates(directory="frontend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
# CF Контесты
@app.get("/cf/contests/", response_model=List[schemas.CFContest])
async def read_cf_contests(
    skip: int = 0,
    limit: int = 100,
    name: Optional[str] = Query(None, description="Фильтр по названию контеста"),
    contest_type: Optional[str] = Query(None, description="Тип контеста (CF, IOI, ICPC)"),
    phase: Optional[str] = Query(None, description="Фаза контеста"),
    min_duration: Optional[int] = Query(None, description="Минимальная длительность в секундах"),
    max_duration: Optional[int] = Query(None, description="Максимальная длительность в секундах"),
    start_time_from: Optional[datetime] = Query(None, description="Начало периода времени проведения"),
    start_time_to: Optional[datetime] = Query(None, description="Конец периода времени проведения"),
    min_problems: Optional[int] = Query(None, description="Минимальное количество задач в контесте"),
    max_problems: Optional[int] = Query(None, description="Максимальное количество задач в контесте"),
    db: AsyncSession = Depends(get_db)
):
    contests = await crud.get_cf_contests(
        db,
        skip=skip,
        limit=limit,
        name=name,
        contest_type=contest_type,
        phase=phase,
        min_duration=min_duration,
        max_duration=max_duration,
        start_time_from=start_time_from,
        start_time_to=start_time_to,
        min_problems=min_problems,
        max_problems=max_problems
    )
    return contests

@app.get("/cf/contests/{contest_id}", response_model=schemas.CFContestWithProblems)
async def read_cf_contest(contest_id: int, db: AsyncSession = Depends(get_db)):
    contest = await crud.get_cf_contest(db, contest_id=contest_id)
    if contest is None:
        raise HTTPException(status_code=404, detail="CF Contest not found")
    return contest

# CF Задачи
@app.get("/cf/problems/", response_model=List[schemas.CFProblem])
async def read_cf_problems(
    skip: int = 0,
    limit: int = 100,
    name: Optional[str] = Query(None, description="Фильтр по названию задачи"),
    min_rating: Optional[int] = Query(None, description="Минимальный рейтинг задачи"),
    max_rating: Optional[int] = Query(None, description="Максимальный рейтинг задачи"),
    include_null_rating: Optional[bool] = Query(False, description="Включать задачи без рейтинга"),
    tags: Optional[List[str]] = Query(None, description="Список тегов через запятую"),
    contest_id: Optional[int] = Query(None, description="ID контеста для фильтрации задач"),
    min_solved_count: Optional[int] = Query(None, description="Минимальное количество решений"),
    db: AsyncSession = Depends(get_db)
):
    problems = await crud.get_cf_problems(
        db,
        skip=skip,
        limit=limit,
        name=name,
        min_rating=min_rating,
        max_rating=max_rating,
        include_null_rating=include_null_rating,
        tags=tags,
        contest_id=contest_id,
        min_solved_count=min_solved_count
    )
    return problems

@app.get("/cf/problems/{problem_id}", response_model=schemas.CFProblemWithDetails)
async def read_cf_problem(problem_id: int, db: AsyncSession = Depends(get_db)):
    problem = await crud.get_cf_problem(db, problem_id=problem_id)
    if problem is None:
        raise HTTPException(status_code=404, detail="CF Problem not found")
    return problem

# Задачи CF контеста
@app.get("/cf/contests/{contest_id}/problems/", response_model=List[schemas.CFProblem])
async def read_cf_contest_problems(
    contest_id: int,
    skip: int = 0,
    limit: int = 100,
    name: Optional[str] = Query(None, description="Фильтр по названию задачи"),
    min_rating: Optional[int] = Query(None, description="Минимальный рейтинг задачи"),
    max_rating: Optional[int] = Query(None, description="Максимальный рейтинг задачи"),
    tags: Optional[List[str]] = Query(None, description="Список тегов через запятую"),
    min_solved_count: Optional[int] = Query(None, description="Минимальное количество решений"),
    db: AsyncSession = Depends(get_db)
):
    problems = await crud.get_cf_contest_problems(
        db,
        contest_id=contest_id,
        skip=skip,
        limit=limit,
        name=name,
        min_rating=min_rating,
        max_rating=max_rating,
        tags=tags,
        min_solved_count=min_solved_count
    )
    if not problems:
        raise HTTPException(status_code=404, detail="No problems found for this contest with specified filters")
    return problems