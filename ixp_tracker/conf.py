from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

try:
    IXP_TRACKER_GEO_LOOKUP_FACTORY = str(settings.IXP_TRACKER_GEO_LOOKUP_FACTORY)
except AttributeError:
    IXP_TRACKER_GEO_LOOKUP_FACTORY = None
except(TypeError, ValueError):
    raise ImproperlyConfigured("IXP_TRACKER_GEO_LOOKUP_FACTORY must be a string value")

try:
    IXP_TRACKER_PEERING_DB_URL = str(settings.IXP_TRACKER_PEERING_DB_URL)
except AttributeError:
    IXP_TRACKER_PEERING_DB_URL = "https://www.peeringdb.com/api"
except(TypeError, ValueError):
    raise ImproperlyConfigured("IXP_TRACKER_PEERING_DB_URL must be a string value")

try:
    IXP_TRACKER_PEERING_DB_KEY = str(settings.IXP_TRACKER_PEERING_DB_KEY)
except AttributeError:
    IXP_TRACKER_PEERING_DB_KEY = None
except(TypeError, ValueError):
    raise ImproperlyConfigured("IXP_TRACKER_PEERING_DB_KEY must be a string value")

DATA_ARCHIVE_URL = "https://publicdata.caida.org/datasets/peeringdb/{year}/{month:02d}/peeringdb_2_dump_{year}_{month:02d}_{day:02d}.json"
