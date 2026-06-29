# The Event Sourcing "time travel" issue

Event Sourcing usually represents the changes in a system; an action happens which generates "events" and these are persisted as the source of truth as they happen. Thus normally an event is stored along with a timestamp to denote when it happened (though important to note it is usually also stored with a sequence number for ordering rather than rely on the timestamps for ordering). In our system we import historical data so currently the events are generated during the import and timestamped with the time of the import rather than the date to which the data archive relates. This presents possible issues when trying to look back at the state of an aggregate at a point in time (e.g. for stats).

It’s not entirely clear if this is going to cause a problem but if it does here are some possible solutions:

- "time travel" and set the event dates in ES to be the date of the import itself (i.e. events triggered by the January 2024 import are dated January 2024 rather than whenever that import was run). This does make me slightly uneasy as it may be playing with a core ES concept. Though I don’t really know how this would play out. We would then be able to query the events to recreate an IXP on a particular date.
- a projection. We could build a projection of the state of each IXP over time (e.g. one row per IXP/month and update accordingly). In theory this would work though it would be complicated to think through every type of event and work out how to update the projection.
- snapshots. We currently take snapshots after each import to improve performance. We could perhaps use these snapshots. We would have to ensure the snapshot was taken at the right logical point in the process. Perhaps this mixes implementation/performance with application logic though.
- add an "import date" to every event to register the date associated with that import. This feels like we are adding meta-data to each event which shouldn’t be there.
- use the current state of each IXP. We currently store all members (active and those that have left) in an IXP aggregate. We could retrieve all these members are query for those matching the date we want the stats for. This should work well and mirrors the current approach. There is at least one flaw with this currently though - if a member leaves and rejoins, we don’t keep any record of the previous membership. Thus if we were querying stats for dates before the rejoin date, we would be missing any data about that member under their initial membership. This should be fixable though so this is probably the best option.

## Decision

We are going to implement "time travel". In the end we narrowed down the trade-off to

- without it we are unable to query for the state of an aggregate at a particular point in time (without adding a specific projection to handle what we need) but we don’t have any concrete use cases for this feature yet
- with it we are losing some information about when the import events actually happened (i.e. when the import script was run) but we’re not clear if there are any other side effects as a result of this change.

There are unknowns in both directions but we felt that the unknown of "we don’t know why we might need to query for an aggregate at a point in time" was more likely to resolve in our favour that "we don’t know what (bad) side effects there might be from implementing it".
