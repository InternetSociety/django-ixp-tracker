import logging
import traceback

from django.core.management import BaseCommand

from ixp_tracker.data_lookup import load_lookup
from ixp_tracker.event_store import Projection, EventStore, DjangoEventStore
from ixp_tracker.ixp_tracker_aggregates import (
    IXP_TRACKER_EVENT_MAP,
    IXP_TRACKER_AGGREGATE_MAP,
)

logger = logging.getLogger("ixp_tracker")


class Command(BaseCommand):
    help = "Rebuilds a projection"

    def add_arguments(self, parser):
        parser.add_argument(
            "projection",
            metavar="projection",
            type=str,
            nargs="+",
            help="The name of the projection to rebuild",
        )

    def handle(self, *args, **options):
        try:
            logger.debug("Rebuilding projection")
            projection_names = [
                str(p).strip() for p in options["projection"] if str(p).strip() != ""
            ]
            if len(projection_names) == 0:
                logging.error("Projection names are empty")
                return
            projections = [
                load_lookup(f"ixp_tracker.ixp_tracker_projections.{p}")
                for p in projection_names
            ]
            projections = [
                p for p in projections if issubclass(p.__class__, Projection)
            ]
            if len(projections) == 0:
                logging.error(
                    "Cannot load projections", extra={"projection": projection_names}
                )
                return
            logger.debug(
                "Rebuilding projection", extra={"projection": projection_names}
            )
            es = EventStore(IXP_TRACKER_EVENT_MAP, DjangoEventStore())
            for p in projections:
                es.add_listener(p)
            es.rebuild_projections(IXP_TRACKER_AGGREGATE_MAP)
            logger.info("Rebuild finished")
        except Exception as e:
            logging.error(
                "Failed to rebuild projection",
                extra={"error": str(e), "trace": traceback.format_exc()},
            )
