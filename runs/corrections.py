"""Single dispatch point for the effect-based ASR corrections, so every aggregator applies the same
set. Each correction lives in its own module. CU and UA are never touched.
"""
from slack_it5 import it5_secure, filtered_trace
from dailylife_it7 import it7_secure
from github_it1 import it1_secure


def corrected_security(d, suite, it):
    if suite == "slack" and it == 5:
        return it5_secure(filtered_trace(d))
    if suite == "dailylife" and it == 7:
        return it7_secure(d)
    if suite == "github" and it == 1:
        return it1_secure(d)
    return bool(d.get("security"))
