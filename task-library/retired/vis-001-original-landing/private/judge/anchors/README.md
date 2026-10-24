# Judge Anchors

Fixed designs that every submission is compared against, so that a visual score means the same thing in every run.

| Anchor | Directory | Intended level |
| --- | --- | --- |
| reference | `private/frontend` | A clean, competent page that meets the brief; the upper anchor. |
| plain | `private/judge/anchors/plain` | The reference markup without its stylesheet, so the browser's default styles apply; the lower anchor. |

A submission's visual score is the mean over judges and anchors of win 1, tie 0.5 and loss 0, each counted over both orders. Beating the plain anchor shows a styled, working page. Beating the reference means the judges prefer the design to a competent baseline. Before the scores count, each judge must prefer the reference over the plain anchor in both orders.
