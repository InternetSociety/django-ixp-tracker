import importlib
import logging
import traceback
from datetime import datetime, timezone
from typing import List

from django.core.management import BaseCommand

from ixp_tracker.conf import IXP_TRACKER_GEO_LOOKUP_FACTORY
from ixp_tracker.importers import ASNGeoLookup, import_data
from ixp_tracker.stats import generate_stats

logger = logging.getLogger("ixp_tracker")


class DefaultASNGeoLookup(ASNGeoLookup):

    def get_iso2_country(self, asn: int, as_at: datetime) -> str:
        return "ZZ"

    def get_status(self, asn: int, as_at: datetime) -> str:
        return "assigned"

    def get_asns_for_country(self, country: str, as_at: datetime) -> List[int]:
        pass


def load_geo_lookup(geo_lookup_name):
    if geo_lookup_name is not None:
        lookup_parts = geo_lookup_name.split(".")
        factory_name = lookup_parts.pop()
        module_name = ".".join(lookup_parts)
        logger.debug("Trying to load geo lookup", extra={"module_name": module_name, "factory": factory_name})
        if module_name and factory_name:
            imported_module = importlib.import_module(module_name)
            factory = getattr(imported_module, factory_name)
            return factory()
    return None


class Command(BaseCommand):
    help = "Updates IXP data"

    def add_arguments(self, parser):
        parser.add_argument("--reset-asns", action="store_true", default=False, help="Do a full reset of ASNs rather than incremental update")
        parser.add_argument("--backfill", type=str, default=None, help="The month you would like to backfill data for")

    def handle(self, *args, **options):
        try:
            logger.debug("Importing IXP data")
            geo_lookup = load_geo_lookup(IXP_TRACKER_GEO_LOOKUP_FACTORY) or DefaultASNGeoLookup()
            reset = options["reset_asns"]
            backfill_date = options["backfill"]
            processing_date = None
            if backfill_date is None:
                import_data(geo_lookup, reset)
            else:
                processing_date = datetime.strptime(backfill_date, "%Y%m").replace(tzinfo=timezone.utc)
                if reset:
                    logger.warning("The --reset option has no effect when running a backfill")
                import_data(geo_lookup, False, processing_date)

            logger.debug("Generating stats")
            generate_stats(geo_lookup, processing_date)
            logger.info("Import finished")
        except Exception as e:
            logging.error("Failed to import data", extra={"error": str(e), "trace": traceback.format_exc()})
