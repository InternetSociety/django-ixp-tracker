# Changelog

## 1.3.2
- another performance improvement to pull only the data needed for the stats generation

## 1.3.1
- retrieve previous months members directly rather than relying on previous month's stats

## 1.3
- add number of IXP physical locations to IXP objects

## 1.2
- performance improvement to generating monthly stats

## 1.1
- always store the date stats are generated

## 1.0
- implemented a single additional lookup, config values has changed from `IXP_TRACKER_GEO_LOOKUP_FACTORY` to `IXP_TRACKER_DATA_LOOKUP_FACTORY`
- extra lookups have been added which will need to be implemented (even if as noops)
- params for `import_data()` have changed, use `import_data(data_lookup_instance)` rather than `import_data(geo_lookup_instance)`
- breaking change to `StatsPerIXP` where no fields are now nullable. Some fields are temporarily populated with zero so all stats should be regenerated.
- remove support for Django < 5.2 and Python < 3.10

## 0.15
- change definition of active status for an IXP from at least 1 member to at least 3 members

## 0.14
- add local_routed_asns_members_rate to per-IXP stats
- add routed_asns_ixp_member_rate and routed_asn_count to per-country stats

## 0.13
- make rs_peer_rate field nullable to allow for pre-existing data

## 0.12
- add rs_peer_rate to the per-IXP stats (existing stats will need to be re-generated)

## 0.11
- ensured inactive IXPs are not counted in per-country stats

## 0.10
- fixed IXP count in per-country stats

## 0.9
- add IXP count to per-country stats (will default to zero for any existing stats so those will need to be re-generated)

## 0.8
- update `last_updated` rather than `last_active` when active status toggled

## 0.7
- fix bug where rejoined members were being counted twice

## 0.6
- extend a membership if created date for imported record is before end date of previous record
- toggle IXP active status based on whether there are active memberships

## 0.5
- fix membership starting after it ended
- fix import for AS being a member of an IX for multiple prefixes
- ensure we don't re-add a membership where not appropriate

## 0.4
- move membership details to separate model so we can track changes over time

## 0.3
- add per-ixp and per-country stats over time

## 0.2
- add ability to backfill data from CAIDA archive

## 0.1
- import ASNs, IXPs and members
