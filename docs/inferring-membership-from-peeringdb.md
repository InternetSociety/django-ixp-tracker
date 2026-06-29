# How we infer membership from PeeringDB data

One of the complications with the existing implementation was our assumption that Peering DB data rewrites history. An import of data for a particular month can contain entries that have a “created” date in the past and did not appear in other imports between that date in the past and the current import date. As an example AS 212655 (YouFibre) is listed in PDB as having joined IXP 53 (LONAP) in April 2021. From December 2022 onwards that ASN no longer appears as a member of that IX in the PDB archive. However in Feb 2024 it re-appears in the data with the same “created” date in April 2021. From this we infer that the AS never left the IX and was always a member.

After discussing this with PeeringDB, it appears that we made a wrong assumption. All data records (“objects”) in PDB can be “soft deleted” and then “resurrected” at some point after that. This explains what we are seeing in the data, e.g. the user soft deleted AS212655 some time in November 2022 and then resurrected the same database record some time in January 2024. The “created” date never changes as the original database record was created in April 2021. PeeringDB does not capture the intention of the user (e.g. the reason for the soft delete or the resurrection) so it’s impossible to know why this happened.

After consideration, we have decided to remove our logic on whether to combine or extends previous membership periods based on what we think we can infer from the data (i.e. “rewriting history”). We will instead follow the PeeringDB data much more closely; when a member appears in the data we will mark it as having joined, and when a member disappears from the data we will mark it as having left.

The benefits of this approach are:

- the code will be simpler and hence there will be less scope for bugs.
- the data will follow PeeringDB more closely.
- we will be able to look at historical data much more easily. Previously members could be back-dated so when data for a specific month could change based on imports of subsequent months data. It meant when comparing/validating data we’d have to import all data before being able to compare against the existing system.
- we will no longer have to regenerate all monthly stats every time we ingest a new month’s data.
- we avoid any potential issues with combining two memberships for the same ASN referring to different actual ASes. (e.g. AS4866 originally operated by MAROSNET Telecommunication Company but was unassigned by NRO in Jan 2021 and re-assigned later in the year to Centre for Strategic Planning of FMBA of Russia)

Obviously the big downside is that the current numbers in the IXP Tracker will change when we make this live. It’s difficult to estimate how much they will change. There are other issues we have found in the original implementation (see [rewrite ADR](event-sourcing-rewrite.md)) which will net off some of the changes. We will be able to run the data before we go to production to check the scale of the changes.

Other examples of challenges with the existing approach:

- AS20940 is listed with a “created” date of 2011-10-08T00:00:00Z. It is not listed as a member of IX 513 in the archive data until August 2024 (bear in mind our import starts in January 2019). Under the current logic, in August 2024 we would mark it as having been a member since October 2011 and thus we would have to regenerate all stats from Jan 2019 onwards to account for this.
