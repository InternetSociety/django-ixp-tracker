from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

IXP_TRACKER_DATA_LOOKUP_FACTORY: str | None
try:
    IXP_TRACKER_DATA_LOOKUP_FACTORY = str(settings.IXP_TRACKER_DATA_LOOKUP_FACTORY)
except AttributeError:
    IXP_TRACKER_DATA_LOOKUP_FACTORY = None
except (TypeError, ValueError):
    raise ImproperlyConfigured("IXP_TRACKER_DATA_LOOKUP_FACTORY must be a string value")

IXP_TRACKER_PEERING_DB_URL: str | None
try:
    IXP_TRACKER_PEERING_DB_URL = str(settings.IXP_TRACKER_PEERING_DB_URL)
except AttributeError:
    IXP_TRACKER_PEERING_DB_URL = "https://www.peeringdb.com/api"
except (TypeError, ValueError):
    raise ImproperlyConfigured("IXP_TRACKER_PEERING_DB_URL must be a string value")

IXP_TRACKER_PEERING_DB_KEY: str | None
try:
    IXP_TRACKER_PEERING_DB_KEY = str(settings.IXP_TRACKER_PEERING_DB_KEY)
except AttributeError:
    IXP_TRACKER_PEERING_DB_KEY = None
except (TypeError, ValueError):
    raise ImproperlyConfigured("IXP_TRACKER_PEERING_DB_KEY must be a string value")

try:
    IXP_TRACKER_ENABLE_EVENT_SOURCING = bool(settings.IXP_TRACKER_ENABLE_EVENT_SOURCING)
except AttributeError:
    IXP_TRACKER_ENABLE_EVENT_SOURCING = False
except (TypeError, ValueError):
    raise ImproperlyConfigured("IXP_TRACKER_ENABLE_EVENT_SOURCING must be a boolean")

DATA_ARCHIVE_URL = "https://publicdata.caida.org/datasets/peeringdb/{year}/{month:02d}/peeringdb_2_dump_{year}_{month:02d}_{day:02d}.json"
# Optional local data archive. When backfilling data the lib will look here first, before trying to get the data from CAIDA
IXP_TRACKER_LOCAL_DATA_ARCHIVE_PATH: str | None
try:
    IXP_TRACKER_LOCAL_DATA_ARCHIVE_PATH = str(
        settings.IXP_TRACKER_LOCAL_DATA_ARCHIVE_PATH
    )
except AttributeError:
    IXP_TRACKER_LOCAL_DATA_ARCHIVE_PATH = None
except (TypeError, ValueError):
    raise ImproperlyConfigured(
        "IXP_TRACKER_LOCAL_DATA_ARCHIVE_PATH must be a string value"
    )
