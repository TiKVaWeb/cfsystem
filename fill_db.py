import aiohttp
import asyncio
import ssl
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, insert, update, and_
from datetime import datetime
from models import (
    Base, CFContest, CFProblem, CFTag, Language,
    CFProblemStatistics, cf_problem_tag_association,
    cf_problem_language_association, cf_problem_contest_association
)
import logging
import os

# Настройка логгирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Константы
API_BASE_URL = "https://codeforces.com/api/"
DEFAULT_LANGUAGES = ['ru', 'en']
MAX_CONTESTS = 10
TEST_DB_PATH = "test_youit.db"

# SSL контекст
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE


async def create_test_db():
    """Создание тестовой базы данных"""
    test_engine = create_async_engine(f"sqlite+aiosqlite:///{TEST_DB_PATH}", echo=True)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        async with sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)() as session:
            for lang_code in DEFAULT_LANGUAGES:
                if not (await session.execute(select(Language).where(Language.code == lang_code))).scalars().first():
                    session.add(Language(code=lang_code, name=lang_code))
            await session.commit()

    await test_engine.dispose()
    return test_engine


async def fetch_data(session, url, params=None):
    """Получение данных с API Codeforces"""
    try:
        async with session.get(url, params=params, ssl=ssl_context) as response:
            if response.status == 200:
                data = await response.json()
                if data['status'] == 'OK':
                    return data['result']
                logger.error(f"API error: {data.get('comment', 'Unknown error')}")
            else:
                logger.error(f"HTTP error: {response.status}")
    except Exception as e:
        logger.error(f"Error fetching data from {url}: {str(e)}")
    return None


async def get_or_create_tag(session, tag_name):
    """Получение или создание тега"""
    result = await session.execute(select(CFTag).where(CFTag.name == tag_name))
    tag = result.scalars().first()

    if not tag:
        tag = CFTag(name=tag_name)
        session.add(tag)
        await session.commit()
        await session.refresh(tag)

    return tag


async def get_problem_solved_count(http_session, contest_id, problem_index):
    """Получение количества решений задачи с несколькими попытками"""
    urls_to_try = [
        (f"{API_BASE_URL}problemset.problems", None),
        (f"{API_BASE_URL}contest.standings", {'contestId': contest_id, 'from': 1, 'count': 1}),
        (f"{API_BASE_URL}contest.status", {'contestId': contest_id, 'from': 1, 'count': 1000})
    ]

    for url, params in urls_to_try:
        try:
            data = await fetch_data(http_session, url, params)
            if not data:
                continue

            if 'problemStatistics' in data:
                for stat in data['problemStatistics']:
                    if stat.get('contestId') == contest_id and stat.get('index') == problem_index:
                        return stat.get('solvedCount', 0)

            if 'problems' in data:
                for problem in data['problems']:
                    if problem.get('index') == problem_index and 'solvedCount' in problem:
                        return problem['solvedCount']

            if 'rows' in data:
                for row in data['rows']:
                    for problem_result in row['problemResults']:
                        if problem_result.get('index') == problem_index and 'solvedCount' in problem_result:
                            return problem_result['solvedCount']

            if isinstance(data, list):
                solved_count = len([sub for sub in data
                                    if sub.get('verdict') == 'OK'
                                    and sub.get('problem', {}).get('index') == problem_index])
                if solved_count > 0:
                    return solved_count

        except Exception as e:
            logger.warning(f"Failed to get solved count from {url}: {str(e)}")
            continue

    return 0


def get_problem_url(contest_id, problem_index):
    """Генерация правильного URL для задачи"""
    if 1 <= contest_id <= 10000:
        return f"https://codeforces.com/contest/{contest_id}/problem/{problem_index}"
    elif 10000 < contest_id < 100000:
        return f"https://codeforces.com/problemset/problem/{contest_id}/{problem_index}"
    return f"https://codeforces.com/gym/{contest_id}/problem/{problem_index}"


def get_contest_url(contest_id):
    """Генерация правильного URL для контеста"""
    if 1 <= contest_id <= 10000:
        return f"https://codeforces.com/contest/{contest_id}"
    elif 10000 < contest_id < 100000:
        return f"https://codeforces.com/problemset"
    return f"https://codeforces.com/gym/{contest_id}"


async def get_problem_translation(http_session, contest_id, problem_index, lang):
    """Получение перевода задачи"""
    url = f"{API_BASE_URL}contest.standings"
    params = {
        'contestId': contest_id,
        'showUnofficial': 'false',
        'from': 1,
        'count': 1,
        'lang': lang
    }

    data = await fetch_data(http_session, url, params)
    if data and 'problems' in data:
        for problem in data['problems']:
            if problem.get('index') == problem_index:
                return problem
    return None


async def add_problem_language(session, problem_id, lang_code):
    """Добавление связи задачи с языком"""
    result = await session.execute(
        select(cf_problem_language_association).where(
            (cf_problem_language_association.c.problem_id == problem_id) &
            (cf_problem_language_association.c.language_code == lang_code)
        )
    )
    if not result.first():
        await session.execute(
            insert(cf_problem_language_association).values(
                problem_id=problem_id,
                language_code=lang_code
            )
        )


async def process_problem(session, http_session, contest_id, problem_data):
    """Обработка и сохранение информации о задаче"""
    problem_uid = f"{contest_id}_{problem_data['index']}"

    # Проверяем существование задачи
    result = await session.execute(
        select(CFProblem).where(CFProblem.problem_uid == problem_uid)
    )
    problem = result.scalars().first()

    # Получаем переводы
    ru_data = await get_problem_translation(http_session, contest_id, problem_data['index'], 'ru')
    en_data = await get_problem_translation(http_session, contest_id, problem_data['index'], 'en')
    localized_data = ru_data if ru_data else en_data if en_data else problem_data

    # Подготовка данных задачи
    problem_dict = {
        'problem_uid': problem_uid,
        'cf_problem_index': problem_data['index'],
        'name': localized_data.get('name', problem_data.get('name', '')),
        'rating': problem_data.get('rating'),
        'time_limit': problem_data.get('timeLimitSeconds'),
        'memory_limit': problem_data.get('memoryLimitBytes', 0) / 1024 / 1024,
        'problem_url': get_problem_url(contest_id, problem_data['index'])
    }

    if problem:
        await session.execute(
            update(CFProblem).where(CFProblem.id == problem.id).values(**problem_dict)
        )
    else:
        problem = CFProblem(**problem_dict)
        session.add(problem)

    await session.flush()

    # Получаем или создаем контест
    contest_result = await session.execute(
        select(CFContest).where(CFContest.cf_contest_id == contest_id)
    )
    contest = contest_result.scalars().first()

    if contest:
        # Добавляем статистику
        solved_count = await get_problem_solved_count(http_session, contest_id, problem_data['index'])

        stat_result = await session.execute(
            select(CFProblemStatistics).where(
                CFProblemStatistics.problem_id == problem.id,
                CFProblemStatistics.contest_id == contest.id
            )
        )
        stat = stat_result.scalars().first()

        if stat:
            stat.solved_count = solved_count
        else:
            stat = CFProblemStatistics(
                problem_id=problem.id,
                contest_id=contest.id,
                solved_count=solved_count
            )
            session.add(stat)

        # Добавляем связь с контестом если ее нет
        assoc_result = await session.execute(
            select(cf_problem_contest_association).where(
                cf_problem_contest_association.c.problem_id == problem.id,
                cf_problem_contest_association.c.contest_id == contest.id
            )
        )
        if not assoc_result.first():
            await session.execute(
                insert(cf_problem_contest_association).values(
                    problem_id=problem.id,
                    contest_id=contest.id
                )
            )

    # Обработка тегов
    if 'tags' in problem_data:
        for tag_name in problem_data['tags']:
            tag = await get_or_create_tag(session, tag_name)
            result = await session.execute(
                select(cf_problem_tag_association).where(
                    (cf_problem_tag_association.c.problem_id == problem.id) &
                    (cf_problem_tag_association.c.tag_id == tag.id)
                )
            )
            if not result.first():
                await session.execute(
                    insert(cf_problem_tag_association).values(
                        problem_id=problem.id,
                        tag_id=tag.id
                    )
                )

    # Обработка языков
    if ru_data:
        await add_problem_language(session, problem.id, 'ru')
    if en_data or not ru_data:
        await add_problem_language(session, problem.id, 'en')

    return problem


async def process_contest(session, contest_data):
    """Обработка и сохранение информации о контесте"""
    result = await session.execute(
        select(CFContest).where(CFContest.cf_contest_id == contest_data['id'])
    )
    contest = result.scalars().first()

    contest_dict = {
        'cf_contest_id': contest_data['id'],
        'name': contest_data.get('name', ''),
        'type': contest_data.get('type', ''),
        'phase': contest_data.get('phase', ''),
        'start_time': datetime.fromtimestamp(contest_data['startTimeSeconds'])
        if 'startTimeSeconds' in contest_data else None,
        'duration': contest_data['durationSeconds'] // 60
        if 'durationSeconds' in contest_data else None,
        'contest_url': get_contest_url(contest_data['id'])
    }

    if contest:
        await session.execute(
            update(CFContest).where(CFContest.id == contest.id).values(**contest_dict)
        )
    else:
        contest = CFContest(**contest_dict)
        session.add(contest)

    await session.flush()
    return contest


async def get_contest_problems(http_session, contest_id):
    """Получение списка задач для контеста"""
    url = f"{API_BASE_URL}contest.standings"
    params = {
        'contestId': contest_id,
        'showUnofficial': 'false',
        'from': 1,
        'count': 1
    }

    data = await fetch_data(http_session, url, params)
    return data['problems'] if data and 'problems' in data else None


async def get_contest_list(http_session):
    """Получение списка контестов"""
    url = f"{API_BASE_URL}contest.list"
    data = await fetch_data(http_session, url)

    if data:
        finished_contests = [c for c in data if c['phase'] == 'FINISHED']
        finished_contests.sort(key=lambda x: x['startTimeSeconds'], reverse=True)
        return finished_contests[:MAX_CONTESTS]
    return None


async def main():
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

    test_engine = await create_test_db()
    test_session = sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

    conn = aiohttp.TCPConnector(ssl=ssl_context)
    async with aiohttp.ClientSession(connector=conn) as http_session:
        try:
            contests = await get_contest_list(http_session)
            if not contests:
                logger.error("No contests found")
                return

            async with test_session() as session:
                for contest_data in contests:
                    try:
                        contest = await process_contest(session, contest_data)
                        await session.commit()

                        logger.info(f"Processing contest: {contest.name} (ID: {contest.cf_contest_id})")

                        problems = await get_contest_problems(http_session, contest.cf_contest_id)
                        if not problems:
                            logger.warning(f"No problems found for contest {contest.cf_contest_id}")
                            continue

                        for problem_data in problems:
                            try:
                                problem = await process_problem(session, http_session,
                                                                contest.cf_contest_id, problem_data)
                                await session.commit()
                                logger.info(f"  - Processed problem: {problem.name}")
                            except Exception as e:
                                await session.rollback()
                                logger.error(f"Error processing problem {problem_data.get('index')}: {str(e)}")

                    except Exception as e:
                        await session.rollback()
                        logger.error(f"Error processing contest {contest_data.get('id')}: {str(e)}")

                logger.info(f"Parsing completed. Database created at {TEST_DB_PATH}")

        except Exception as e:
            logger.error(f"Fatal error: {str(e)}")
        finally:
            await test_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())