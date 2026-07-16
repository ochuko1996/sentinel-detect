"""SQLAlchemy ORM models: one table per persisted entity.

Every model must be imported here (or from wherever `Base` is used before
`create_all`/Alembic autogenerate runs) so it registers on `Base.metadata`.
"""

from sentinel_detect.database.models.alert import AlertRecord
from sentinel_detect.database.models.camera import CameraRecord
from sentinel_detect.database.models.configuration import ConfigurationRecord
from sentinel_detect.database.models.detection import DetectionRecord
from sentinel_detect.database.models.event import EventRecord
from sentinel_detect.database.models.user import UserRecord

__all__ = [
    "AlertRecord",
    "CameraRecord",
    "ConfigurationRecord",
    "DetectionRecord",
    "EventRecord",
    "UserRecord",
]
