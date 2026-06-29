# Event-sourcing rewrite (v2)

## Status

Agreed

## Context

When we first created the IXP Tracker we decided to create the underlying data processing as a standalone, open-source library so that others in the Internet Measurement community could review our logic and/or run the data themselves.

Initially we statically defined the various stats we wanted to generate around IXPs. Since the first version we have managed to add a few extra stats without having to reprocess all the base IXP data from PeeringDB. However we have had requests over time for stats that we don’t currently generate based on properties that we don’t track over time (e.g. route server peering) and this isn’t possible without reprocessing all the historical PeeringDB data.

## Decision

We have decided to rewrite the library using [event sourcing](https://en.wikipedia.org/wiki/Domain-driven_design#Event_sourcing) so that all changes are tracked across time and allow future analysis without reprocessing the data. A rewrite will also allow us to allow for adding other sources of data about IXPs. We reviewed whether to use an [existing library](https://pypi.org/project/eventsourcing/) or to write our own implementation from scratch and decided to write from scratch:

- the lib seemed over-complicated for what we need
- we spent several days spiking with the lib and we struggled to get even simple examples of a model and projection working
- event sourcing is a pretty simple concept so the code required to do the event sourcing (as opposed to the domain logic) doesn’t need to be every extensive

We also decided to do the development of the new solution in situ in the existing repo, feature-flagged as an experimental feature so we can potentially run it side-by-side in a dev or local environment.

In terms of the specific implementation, we decided to [force events to be dated to match the date on the data we are importing](time-travel.md).

## Consequences

Event sourcing is a long established pattern, popular within domain-driven design, but it is not widely used. Thus there will be an increased complexity for new developers starting to work on the project in understanding the concepts in event sourcing. It is not a complicated pattern but is significantly different to the CRUD pattern that most developers use.

We will need to reprocess all the historical PeeringDB data and work out a plan to validate the new data and then cut over from the existing data to the new lib.

## Bugs

While working on the re-write and validating the newly-generated data against the existing data, we have discovered a number of issues with the existing data that the new code will solve:

- we use country ZZ as a check for defunct ASes and remove them as members of an IX but in the existing code we are checking the registration country against the date the network was last updated in PDB rather than the current registration. This means more often than not we don’t mark an AS as left when the NRO country is changed to ZZ
- AS112 is being marked as left in any IXes where it exists as it is registered to country ZZ in NRO
- we are not correctly detecting ASes that appear to leave and rejoin an IX. There are some instances in the source data where an AS will disappear from the data and re-appear but with the same “created” date. In these instances the existing code does not detect the re-appearance and leaves the AS as having left. We contacted PDB about this issue and this is entirely expected. See [how we infer membership from Peering Db](inferring-membership-from-peeringdb.md) for a description of this. We have decided to follow PDB more closely in how we record membership.
