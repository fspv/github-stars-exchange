from __future__ import annotations

import enum
import textwrap
from typing import List

import sqlalchemy
import sqlalchemy.orm
from sqlalchemy.orm.decl_api import DeclarativeMeta

mapper_registry = sqlalchemy.orm.registry()


class Base(metaclass=DeclarativeMeta):
    __abstract__ = True
    registry = mapper_registry
    metadata = mapper_registry.metadata

    __init__ = mapper_registry.constructor


class User(Base):
    """
    User for our service

    Initial idea, that we don't support our own auth and use GitHub auth
    mechanism instead. So this entry represents a GitHub user.

    Potentially we can use it to fit users from other services as well, so
    shouldn't be directly tied to GitHub by any means.
    """

    __tablename__ = "users"

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)

    # FIXME: A human-readable name. Not necessarily unique, not sure if is
    # necessary at all
    name = sqlalchemy.Column(sqlalchemy.String)

    # Auth token to be used to authenticate the user. Should somehow be linked
    # to a github account
    # TODO: Check how Github auth works and look for the best set of fields
    # to authenticate the user
    auth_token = sqlalchemy.Column(sqlalchemy.String)

    jobs: sqlalchemy.orm.Mapped[List[Job]] = (
        sqlalchemy.orm.relationship("Job", back_populates="user")
    )
    campaigns: sqlalchemy.orm.Mapped[List[Campaign]] = (
        sqlalchemy.orm.relationship("Campaign", back_populates="user")
    )
    credits: sqlalchemy.orm.Mapped[List[Credit]] = (
        sqlalchemy.orm.relationship("Credit", back_populates="user")
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, name={self.name})>"


class JobStatus(enum.Enum):
    """
    Status for the job

    The state machine for jobs is the following:

        NEW -> IN_PROGRESS -> COMPLETED
         |        |
         |        |---------> ABORTED
         |_______________________^
    """

    NEW = 1
    IN_PROGRESS = 2
    COMPLETED = 3
    ABORTED = 4


class Job(Base):
    """
    Job to be executed by worker.

    This job is to check, wheather the user fulfilled their promise to endorse
    user's content (star/follow/fork).
    """

    __tablename__ = "jobs"

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)

    # The user who gave a promise to endorce campaign
    user_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey("users.id"))
    user: sqlalchemy.orm.Mapped[User] = (
        sqlalchemy.orm.relationship("User", back_populates="jobs")
    )

    campaign_id = sqlalchemy.Column(
        sqlalchemy.Integer,
        sqlalchemy.ForeignKey("campaigns.id"),
        comment="Campain this job associted with",
    )
    campaign: sqlalchemy.orm.Mapped[Campaign] = (
        sqlalchemy.orm.relationship("Campaign", back_populates="jobs")
    )

    status = sqlalchemy.Column(sqlalchemy.Enum(JobStatus), comment="Status of the job")

    created = sqlalchemy.Column(sqlalchemy.DateTime, comment="Creation time of the job")
    last_updated = sqlalchemy.Column(
        sqlalchemy.DateTime, comment="Latest job update timestamp"
    )

    def __repr__(self) -> str:
        return textwrap.dedent(
            f"""
                <Job(
                    id={self.id},
                    user={self.user_id},
                    campaign={self.campaign_id},
                    status={self.status},
                    created={self.created},
                    last_updated={self.last_updated},
                )>
            """
        )


class CampaignType(enum.Enum):
    GITHUB_STAR = 1
    GITHUB_FORK = 2
    GITHUB_FOLLOW = 3


class CampaignStatus(enum.Enum):
    """
    Status for the campaign

    The state machine for campaigns is the following:

        NEW -> IN_PROGRESS -> COMPLETED
         |        |
         |        |---------> ABORTED
         |_______________________^
    """

    NEW = 1
    IN_PROGRESS = 2
    COMPLETED = 3
    ABORTED = 4


class Campaign(Base):
    __tablename__ = "campaigns"

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)

    user_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey("users.id"))
    user: sqlalchemy.orm.Mapped[User] = (
        sqlalchemy.orm.relationship("User", back_populates="jobs")
    )

    jobs: sqlalchemy.orm.Mapped[List[Job]] = (
        sqlalchemy.orm.relationship("Job", back_populates="campaign")
    )

    type = sqlalchemy.Column(
        sqlalchemy.Enum(CampaignType),
        comment="Type of the campaign (star/fork/follow/etc)",
    )

    reference = sqlalchemy.Column(
        sqlalchemy.String, comment="Link to the repo/user page"
    )

    # count = sqlalchemy.Column(sqlalchemy.Integer)
    initial_count = sqlalchemy.Column(
        sqlalchemy.Integer, comment="How many stars/follows/forks to make"
    )

    status = sqlalchemy.Column(
        sqlalchemy.Enum(CampaignStatus),
        comment="Status of the campaign (completed/in progress/aborted/etc)",
    )

    def __repr__(self) -> str:
        return textwrap.dedent(
            f"""
                <Campaign(
                    id={self.id},
                    user={self.user_id},
                    type={self.type},
                    reference={self.reference},
                    initial_count={self.initial_count},
                    status={self.status},
                )>
            """
        )


class Credit(Base):
    __tablename__ = "credits"

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)

    user_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey("users.id"))
    user: sqlalchemy.orm.Mapped[User] = sqlalchemy.orm.relationship(
        "User", back_populates="jobs"
    )

    # TODO: Remove two fields below (not needed)
    # count = sqlalchemy.Column(
    #     sqlalchemy.Integer, default=1, comment="Count of the credits"
    # )

    # Probably not needed, because credits just get from one user to another
    # used = sqlalchemy.Column(
    #     sqlalchemy.Boolean,
    #     comment="Had this credit been used already (i.e. is it still usable)",
    # )

    type = sqlalchemy.Column(
        sqlalchemy.Enum(CampaignType),
        comment="What this credit can be used for (star/fork/follow/etc)",
    )

    def __repr__(self) -> str:
        return textwrap.dedent(
            f"""
                <Credit(
                    id={self.id},
                    user={self.user_id},
                    type={self.type},
                )>
            """
        )


def create_database() -> None:
    engine = sqlalchemy.create_engine("sqlite:///:memory:", echo=True)
    Base.metadata.create_all(engine)

    Session = sqlalchemy.orm.sessionmaker()
    Session.configure(bind=engine)
    session = Session()
    session.commit()


create_database()
