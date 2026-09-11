# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class TeamCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class TeamUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class TeamSummary(BaseModel):
    """One of the caller's teams, with their own role and the team's total
    member count. Returned by POST /api/teams, each item of GET /api/teams,
    and PATCH /api/teams/{id} - one shape for create/list/rename so the
    frontend can keep a single Team type for all three."""

    id: uuid.UUID
    name: str
    role: str
    member_count: int
    created_at: datetime


class TeamMemberOut(BaseModel):
    user_id: uuid.UUID
    email: str | None
    role: str
    joined_at: datetime


class TeamDetail(BaseModel):
    id: uuid.UUID
    name: str
    members: list[TeamMemberOut]


class InvitationCreate(BaseModel):
    email: EmailStr


class InvitationOut(BaseModel):
    """Never includes the raw token: invitations are accepted via the
    emailed link only, not a shareable code (CLAUDE.md's locked-in decision
    #2) - exposing the token here would let any member hand it out directly."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    team_id: uuid.UUID
    email: str
    status: str
    created_at: datetime
    expires_at: datetime
