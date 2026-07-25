"""Per-user profiles with background, and background folded into recommendations."""

from __future__ import annotations

from app.models import Issue, UserProfile
from app.services.indexer import refresh_embeddings
from app.services.recommendations import get_or_create_profile, recommend_issues
from app.text import content_hash


def test_profiles_are_keyed_by_external_id(session):
    a = get_or_create_profile(session, "alice")
    b = get_or_create_profile(session, "bob")
    a.skill_prompt = "rbd mirroring"
    b.skill_prompt = "cephfs internals"
    session.commit()

    assert a.id != b.id
    assert get_or_create_profile(session, "alice").skill_prompt == "rbd mirroring"
    assert session.query(UserProfile).count() == 2


def test_background_field_persists(session):
    p = get_or_create_profile(session, "me")
    p.skill_prompt = "C++"
    p.background = "Worked on rbd-mirror snapshot sync last year"
    session.commit()
    assert get_or_create_profile(session, "me").background.startswith("Worked on")


def test_background_influences_ranking(session):
    # Two issues; the skill line is generic, but the background clearly matches #1.
    session.add(Issue(id=1, subject="rbd mirror snapshot replayer",
                      description="snapshot sync replayer work", is_open=True,
                      content_hash=content_hash("1"), url="u1"))
    session.add(Issue(id=2, subject="cephfs quota metrics", description="quota",
                      is_open=True, content_hash=content_hash("2"), url="u2"))
    session.commit()
    refresh_embeddings(session)

    combined = "I am a developer\n\nExperience with rbd mirror snapshot replayer"
    recs = recommend_issues(session, skill_prompt=combined, stretch=0)
    assert recs[0].issue_id == 1
