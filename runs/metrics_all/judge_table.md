| Holder | episodes with exact leak ≥1 bit | judge flagged any turn (of those) | judge flagged any turn (leak < 1 bit) | judge false-positive rate on oracle turns |
|---|---|---|---|---|
| oracle | 0 | 0/0 | 1/50 | 1/550 = 0.2% |
| vanilla | 0 | 0/0 | 2/50 |  |
| ci | 0 | 0/0 | 8/50 |  |
| ledger | 0 | 0/0 | 7/50 |  |
| vanilla@claude-sonnet-5-5 | 31 | 1/31 = 3% | 3/19 |  |
| vanilla@claude-haiku-5-5 | 35 | 10/35 = 29% | 1/15 |  |
| vanilla|scripted-ladder | 0 | 0/0 | 8/50 |  |
| vanilla@claude-sonnet-5-5|scripted-ladder | 31 | 0/31 = 0% | 0/19 |  |
| **all** | 97 | 11/97 = 11% | | |
