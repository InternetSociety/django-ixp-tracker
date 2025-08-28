import logging
import traceback
from datetime import datetime, timezone

from django.core.management import BaseCommand

from ixp_tracker.conf import IXP_TRACKER_DATA_LOOKUP_FACTORY
from ixp_tracker.data_lookup import AdditionalDataSources, DefaultAdditionalDataSources, load_lookup
from ixp_tracker.importers import import_data
from ixp_tracker.stats import generate_stats

logger = logging.getLogger("ixp_tracker")


class Command(BaseCommand):
    help = "Updates IXP data"

    def add_arguments(self, parser):
        parser.add_argument("--reset-asns", action="store_true", default=False, help="Do a full reset of ASNs rather than incremental update")
        parser.add_argument("--backfill", type=str, default=None, help="The month you would like to backfill data for")

    def handle(self, *args, **options):
        try:
            logger.debug("Importing IXP data")
            data_lookup: AdditionalDataSources = load_lookup(IXP_TRACKER_DATA_LOOKUP_FACTORY) or DefaultAdditionalDataSources()
            reset = options["reset_asns"]
            backfill_date = options["backfill"]
            processing_date = None
            if backfill_date is None:
                import_data(data_lookup, reset)
            else:
                processing_date = datetime.strptime(backfill_date, "%Y%m").replace(tzinfo=timezone.utc)
                if reset:
                    logger.warning("The --reset option has no effect when running a backfill")
                import_data(data_lookup, False, processing_date)

            logger.debug("Generating stats")
            generate_stats(data_lookup, processing_date)
            logger.info("Import finished")
        except Exception as e:
            logging.error("Failed to import data", extra={"error": str(e), "trace": traceback.format_exc()})
