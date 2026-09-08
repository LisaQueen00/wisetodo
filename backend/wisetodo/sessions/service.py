from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from wisetodo.sessions.models import SessionHistory, SessionStatus, SessionSummary
from wisetodo.sessions.tables import SessionRecord


class SessionService:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def create(self, label: str = "") -> SessionHistory:
        if not isinstance(label, str):
            raise ValueError("Session label must be a string")
        with self._sessions.begin() as session:
            record = SessionRecord(label=label.strip())
            session.add(record)
            session.flush()
            session.refresh(record)
            return SessionHistory.model_validate(record)

    def list(self) -> list[SessionSummary]:
        # History bodies are fetched only after the user selects a Session.
        with self._sessions() as session:
            records = session.scalars(
                select(SessionRecord).order_by(
                    SessionRecord.updated_at.desc(),
                    SessionRecord.created_at.desc(),
                    SessionRecord.id,
                )
            )
            return [SessionSummary.model_validate(record) for record in records]

    def get(self, session_id: str) -> SessionHistory | None:
        with self._sessions() as session:
            record = session.scalar(
                select(SessionRecord)
                .where(SessionRecord.id == session_id)
                .options(
                    selectinload(SessionRecord.messages), selectinload(SessionRecord.tool_events)
                )
            )
            return SessionHistory.model_validate(record) if record is not None else None

    def delete(self, session_id: str) -> bool:
        with self._sessions.begin() as session:
            record = session.get(SessionRecord, session_id)
            if record is None:
                return False
            # Never remove a live run's history beneath the future runtime.
            if record.status == SessionStatus.RUNNING:
                raise ValueError("Stop the running Session before deleting it")
            session.delete(record)
            return True
