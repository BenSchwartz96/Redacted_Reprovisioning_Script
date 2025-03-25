This is a partially redacted version of a script I wrote while at my last workplace, Divitel. This is shared with permission.

The problem this script aimed to solve was a bug in software we weren't allowed to touch (as it was owned/managed by a client). Customers of this client (a TV provider) would have profiles, with a given number of hours provisioned to each account to use for recordings. Due to an unknown reason, customers were regularly being misprovisioned with the wrong number of hours.

This script therefore aimed to regularly scan all customer files for instances where a customer had the wrong number of hours provisioned. If there were only a few of these, the script would reprovision them correctly. If there were too many, it would instead raise a Jira ticket.
