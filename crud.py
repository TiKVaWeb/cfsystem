import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import and_, or_
from sqlalchemy.sql import func
import models
from typing import List, Optional


async def get_cf_contests(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        name: Optional[str] = None,
        contest_type: Optional[str] = None,
        phase: Optional[str] = None,
        min_duration: Optional[int] = None,
        max_duration: Optional[int] = None,
        start_time_from: Optional[datetime] = None,
        start_time_to: Optional[datetime] = None,
        min_problems: Optional[int] = None,
        max_problems: Optional[int] = None
) -> List[models.CFContest]:
    # Подзапрос для подсчета задач в каждом контесте
    problem_count = (
        select(
            models.cf_problem_contest_association.c.contest_id,
            func.count().label('problems_count')
        )
        .group_by(models.cf_problem_contest_association.c.contest_id)
        .subquery()
    )

    query = (
        select(models.CFContest)
        .outerjoin(
            problem_count,
            models.CFContest.id == problem_count.c.contest_id
        )
    )

    # Базовые фильтры
    if name:
        query = query.where(models.CFContest.name.ilike(f"%{name}%"))
    if contest_type:
        query = query.where(models.CFContest.type == contest_type)
    if phase:
        query = query.where(models.CFContest.phase == phase)
    if min_duration:
        query = query.where(models.CFContest.duration >= min_duration)
    if max_duration:
        query = query.where(models.CFContest.duration <= max_duration)
    if start_time_from:
        query = query.where(models.CFContest.start_time >= start_time_from)
    if start_time_to:
        query = query.where(models.CFContest.start_time <= start_time_to)

    # Фильтры по количеству задач
    if min_problems is not None:
        query = query.where(
            or_(
                problem_count.c.problems_count >= min_problems,
                and_(
                    problem_count.c.problems_count == None,
                    min_problems == 0
                )
            )
        )
    if max_problems is not None:
        query = query.where(
            or_(
                problem_count.c.problems_count <= max_problems,
                problem_count.c.problems_count == None
            )
        )

    result = await db.execute(
        query.order_by(models.CFContest.start_time.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def get_cf_contest(db: AsyncSession, contest_id: int) -> Optional[models.CFContest]:
    result = await db.execute(
        select(models.CFContest)
        .where(models.CFContest.id == contest_id)
        .options(selectinload(models.CFContest.problems)))
    return result.scalars().first()


async def get_cf_problems(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        name: Optional[str] = None,
        min_rating: Optional[int] = None,
        max_rating: Optional[int] = None,
        include_null_rating: bool = False,
        tags: Optional[List[str]] = None,
        contest_id: Optional[int] = None,
        min_solved_count: Optional[int] = None
) -> List[models.CFProblem]:
    query = select(models.CFProblem)

    # Фильтры по рейтингу с учетом NULL значений
    rating_conditions = []
    if min_rating is not None:
        rating_conditions.append(models.CFProblem.rating >= min_rating)
    if max_rating is not None:
        rating_conditions.append(models.CFProblem.rating <= max_rating)

    if rating_conditions:
        if include_null_rating:
            query = query.where(
                or_(
                    and_(*rating_conditions),
                    models.CFProblem.rating == None
                )
            )
        else:
            query = query.where(and_(*rating_conditions))
    elif not include_null_rating:
        query = query.where(models.CFProblem.rating != None)

    # Остальные фильтры
    if name:
        query = query.where(models.CFProblem.name.ilike(f"%{name}%"))
    if tags:
        query = query.join(models.cf_problem_tag_association).join(models.CFTag)
        query = query.where(models.CFTag.name.in_(tags))
        query = query.group_by(models.CFProblem.id)
        query = query.having(func.count(models.CFTag.id) == len(tags))
    if contest_id:
        query = query.join(models.cf_problem_contest_association)
        query = query.where(models.cf_problem_contest_association.c.contest_id == contest_id)
    if min_solved_count:
        query = query.join(models.CFProblemStatistics)
        query = query.where(models.CFProblemStatistics.solved_count >= min_solved_count)

    result = await db.execute(
        query.order_by(models.CFProblem.rating.desc())
        .offset(skip)
        .limit(limit)
        .options(
            selectinload(models.CFProblem.tags),
            selectinload(models.CFProblem.statistics)
        )
    )
    return result.scalars().all()

async def get_cf_problem(db: AsyncSession, problem_id: int) -> Optional[models.CFProblem]:
    result = await db.execute(
        select(models.CFProblem)
        .where(models.CFProblem.id == problem_id)
        .options(
            selectinload(models.CFProblem.contests),
            selectinload(models.CFProblem.tags),
            selectinload(models.CFProblem.statistics)
        ))
    return result.scalars().first()


async def get_cf_contest_problems(
        db: AsyncSession,
        contest_id: int,
        skip: int = 0,
        limit: int = 100,
        name: Optional[str] = None,
        min_rating: Optional[int] = None,
        max_rating: Optional[int] = None,
        tags: Optional[List[str]] = None,
        min_solved_count: Optional[int] = None
) -> List[models.CFProblem]:
    query = (
        select(models.CFProblem)
        .join(models.cf_problem_contest_association)
        .where(models.cf_problem_contest_association.c.contest_id == contest_id)
    )

    # Применяем дополнительные фильтры
    if name:
        query = query.where(models.CFProblem.name.ilike(f"%{name}%"))
    if min_rating:
        query = query.where(models.CFProblem.rating >= min_rating)
    if max_rating:
        query = query.where(models.CFProblem.rating <= max_rating)
    if tags:
        query = query.join(models.cf_problem_tag_association).join(models.CFTag)
        query = query.where(models.CFTag.name.in_(tags))
        query = query.group_by(models.CFProblem.id)
        query = query.having(func.count(models.CFTag.id) == len(tags))
    if min_solved_count:
        query = query.join(models.CFProblemStatistics)
        query = query.where(models.CFProblemStatistics.solved_count >= min_solved_count)

    result = await db.execute(
        query.order_by(models.CFProblem.rating)
        .offset(skip)
        .limit(limit)
        .options(
            selectinload(models.CFProblem.tags),
            selectinload(models.CFProblem.statistics)
        )
    )
    return result.scalars().all()