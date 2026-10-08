from __future__ import annotations

from datetime import datetime, timezone
from importlib.metadata import version
from fsrs import Card, Scheduler, Rating

VERSION = f'fsrs-{version("fsrs")}/selflore-1'


def fresh(now=None):
    now = now or datetime.now(timezone.utc)
    return {'scheduler': Scheduler(enable_fuzzing=False).to_dict(), 'card': Card(due=now, card_id=0).to_dict()}


def schedule(payload, rating, now, duration=0):
    scheduler = Scheduler.from_dict(payload['scheduler'])
    card = Card.from_dict(payload['card'])
    updated, _ = scheduler.review_card(card, Rating(rating), review_datetime=now, review_duration=duration)
    state = {1:'learning',2:'review',3:'relearning'}[updated.state.value]
    return {'scheduler': payload['scheduler'], 'card':updated.to_dict()}, state, updated.due
