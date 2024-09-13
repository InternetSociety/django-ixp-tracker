# django-ixp-tracker

[![PyPI](https://img.shields.io/pypi/v/django-ixp-tracker.svg)](https://pypi.org/project/django-ixp-tracker/)
[![Tests](https://github.com/InternetSociety/django-ixp-tracker/actions/workflows/test.yml/badge.svg)](https://github.com/InternetSociety/django-ixp-tracker/actions/workflows/test.yml)
[![Changelog](https://img.shields.io/github/v/release/InternetSociety/django-ixp-tracker?include_prereleases&label=changelog)](https://github.com/InternetSociety/django-ixp-tracker/releases)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/InternetSociety/django-ixp-tracker/blob/main/LICENSE)

Library to retrieve and manipulate data about IXPs

## Installation

Install this library using `pip`:
```bash
pip install django-ixp-tracker
```
## Usage

1. Add to your INSTALLED_APPS setting like this:
```
   INSTALLED_APPS = [
   ...,
   "ixp_tracker",
   ]
```

 Note: this app has no web-facing components so you don't need to add anything to `urls.py` etc

2. Run `python manage.py migrate` to create the models.
3. Add the relevant settings to your config. `IXP_TRACKER_PEERING_DB_URL` will use a default if you don't provide a value so you probably don't need that. But you will need to set `IXP_TRACKER_PEERING_DB_KEY` to authenticate against the API.
4. Add `IXP_TRACKER_GEO_LOOKUP_FACTORY` to config with the path to your factory (see below).
5. Run the management command to import the data: `python manage.py ixp_tracker_import` (This will sync the current data, if you want historical data you need to backfill first)

## ASN country and status data

The lib uses an external component to look up the country of registration (why?) and the status of an ASN. This status is used for the logic to identify when members have left an IXP.

If you don't provide this service yourself, it will default to a noop version. This will mean you will get no country of registration data and the marking of members having left an IXP will not be as efficient.

In order to implement such a component yourself, you should implement the Protocol `ixp_tracker.importers.ASNGeoLookup` and provide a factory function for your class.

## Backfilling data

You have the option of backfilling data from archived PeeringDb data. This can be done by running the import command with the `--backfill` option for each month you want to backfill:
```shell
python manage.py ixp_tracker_import --backfill <YYYMM>
```
The backfill currently process a single month at a time and will look for the earliest file for the relevant month at https://publicdata.caida.org/datasets/peeringdb/

IMPORTANT NOTE: due to the way the code tries to figure out when a member left an IXP, you should run the backfill strictly in date order and *before* syncing the current data.

## IXP stats

The import process also generates monthly stats per IXP and per country. These are generated as of the 1st of the month used to import the data.

## Running programmatically

If you'd like to run the import from code, rather than from the management command, you can call `importers.import_data()` directly.

It's not recommended to call any other functions yourself.

## Development

To contribute to this library, first checkout the code. Then create a new virtual environment:
```bash
cd django-ixp-tracker
python -m venv venv
source venv/bin/activate
```
Now install the dependencies and test dependencies:
```bash
pip install -e '.[test]'
```
To run the tests:
```bash
pytest
```
We use [pre-commit](https://pre-commit.com/) for linting etc on push. Run:
```bash
pre-commit install
```
from the repo top-level dir to set it up.

## Peering Db libraries

PeeringDb provide their own [vanilla Python](https://github.com/peeringdb/peeringdb-py) and [Django](https://github.com/peeringdb/django-peeringdb) libs, but we have decided not to use these.

Both libs are designed to keep a local copy of the current data and to keep that copy in sync with the central copy via the API.

As we need to keep a historical record (e.g. for IXP growth stats over time), we would have to provide some sort of wrapper over those libs anyway.

In addition to that, the [historical archives of PeeringDb data](https://publicdata.caida.org/datasets/peeringdb/) use flat lists of the different object types in json. We can retrieve the data from the API directly in the same way, so it makes it simpler to implement.
