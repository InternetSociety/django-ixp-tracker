# Changelog

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
