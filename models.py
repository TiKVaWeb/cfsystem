from sqlalchemy import (
    Column, Integer, String, Boolean, ForeignKey,
    DateTime, Float, Table, Text, Enum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum as PyEnum
from database import Base


# --- Перечисления ---
class LanguageCode(PyEnum):
    RU = "ru"
    EN = "en"
    KK = "kk"


# --- Вспомогательные таблицы ---
youit_problem_contest_association = Table(
    "youit_problem_contest_association",
    Base.metadata,
    Column("problem_id", ForeignKey("youit_problems.id"), primary_key=True),
    Column("contest_id", ForeignKey("youit_contests.id"), primary_key=True),
)

youit_problem_language_association = Table(
    "youit_problem_language_association",
    Base.metadata,
    Column("problem_id", ForeignKey("youit_problems.id"), primary_key=True),
    Column("language_code", ForeignKey("languages.code"), primary_key=True),
)

cf_problem_tag_association = Table(
    "cf_problem_tag_association",
    Base.metadata,
    Column("problem_id", ForeignKey("cf_problems.id"), primary_key=True),
    Column("tag_id", ForeignKey("cf_tags.id"), primary_key=True),
)

cf_problem_language_association = Table(
    "cf_problem_language_association",
    Base.metadata,
    Column("problem_id", ForeignKey("cf_problems.id"), primary_key=True),
    Column("language_code", ForeignKey("languages.code"), primary_key=True),
)

cf_problem_contest_association = Table(
    "cf_problem_contest_association",
    Base.metadata,
    Column("problem_id", ForeignKey("cf_problems.id"), primary_key=True),
    Column("contest_id", ForeignKey("cf_contests.id"), primary_key=True),
)


# --- Основные таблицы ---
class Language(Base):
    """Поддерживаемые языки"""
    __tablename__ = 'languages'
    code = Column(String(2), primary_key=True)
    name = Column(String(50), unique=True)


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())


class YouITContest(Base):
    __tablename__ = 'youit_contests'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    start_time = Column(DateTime)
    duration = Column(Integer)
    is_archived = Column(Boolean, default=False)
    creator_id = Column(Integer, ForeignKey('users.id'))
    cf_contest_id = Column(Integer, nullable=True)

    creator = relationship("User")
    problems = relationship(
        "YouITProblem",
        secondary=youit_problem_contest_association,
        back_populates="contests"
    )


class YouITProblem(Base):
    __tablename__ = 'youit_problems'
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    difficulty = Column(Integer)
    time_limit = Column(Float)
    memory_limit = Column(Integer)
    creator_id = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime, server_default=func.now())
    problem_url = Column(String(200))

    creator = relationship("User")
    contests = relationship(
        "YouITContest",
        secondary=youit_problem_contest_association,
        back_populates="problems"
    )
    languages = relationship(
        "Language",
        secondary=youit_problem_language_association,
        back_populates="youit_problems"
    )
    cf_reference = relationship("CFProblemReference", uselist=False, back_populates="youit_problem")


class CFProblemReference(Base):
    __tablename__ = 'cf_problem_references'
    id = Column(Integer, primary_key=True)
    youit_problem_id = Column(Integer, ForeignKey('youit_problems.id'), unique=True)
    cf_problem_id = Column(Integer, ForeignKey('cf_problems.id'))

    youit_problem = relationship("YouITProblem", back_populates="cf_reference")
    cf_problem = relationship("CFProblem", back_populates="youit_references")


class CFContest(Base):
    __tablename__ = 'cf_contests'
    id = Column(Integer, primary_key=True)
    cf_contest_id = Column(Integer, unique=True)
    name = Column(String(100))
    type = Column(String(20))
    phase = Column(String(20))
    start_time = Column(DateTime)
    duration = Column(Integer)
    contest_url = Column(String(200))

    problems = relationship(
        "CFProblem",
        secondary=cf_problem_contest_association,
        back_populates="contests"
    )


class CFTag(Base):
    __tablename__ = 'cf_tags'
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True)


class CFProblemStatistics(Base):
    __tablename__ = 'cf_problem_statistics'
    id = Column(Integer, primary_key=True)
    problem_id = Column(Integer, ForeignKey('cf_problems.id'))
    contest_id = Column(Integer, ForeignKey('cf_contests.id'))
    solved_count = Column(Integer)
    last_updated = Column(DateTime, server_default=func.now(), onupdate=func.now())

    problem = relationship("CFProblem", back_populates="statistics")
    contest = relationship("CFContest")


class CFProblem(Base):
    __tablename__ = 'cf_problems'
    id = Column(Integer, primary_key=True)
    problem_uid = Column(String(50), unique=True)  # contestId_index
    cf_problem_index = Column(String(20))
    name = Column(String(200))
    rating = Column(Integer, nullable=True)
    # time_limit = Column(Float)
    # memory_limit = Column(Integer)
    problem_url = Column(String(200))

    contests = relationship(
        "CFContest",
        secondary=cf_problem_contest_association,
        back_populates="problems"
    )
    statistics = relationship("CFProblemStatistics", back_populates="problem")
    tags = relationship(
        "CFTag",
        secondary=cf_problem_tag_association,
        back_populates="problems"
    )
    languages = relationship(
        "Language",
        secondary=cf_problem_language_association,
        back_populates="cf_problems"
    )
    youit_references = relationship("CFProblemReference", back_populates="cf_problem")


# Обратные связи
Language.youit_problems = relationship(
    "YouITProblem",
    secondary=youit_problem_language_association,
    back_populates="languages"
)

Language.cf_problems = relationship(
    "CFProblem",
    secondary=cf_problem_language_association,
    back_populates="languages"
)

CFTag.problems = relationship(
    "CFProblem",
    secondary=cf_problem_tag_association,
    back_populates="tags"
)