"""Rebuild the standalone Task 3 report from the checked SQL results."""
from pathlib import Path
from datetime import date, timedelta
from collections import Counter, defaultdict
import base64
import html
import io
import json
import re
import zipfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

ROOT = Path(__file__).resolve().parent
PLOTS = ROOT / "plots"
PLOTS.mkdir(exist_ok=True)
payload = json.loads((ROOT / "analysis-results.json").read_text())
queries = payload["queries"]
daily = queries["daily_active_users"]
cards = queries["status_changes_by_card"]
matched = queries["matched_28_day_comparison"]
summary = queries["card_activity_summary"][0]
release = date.fromisoformat(payload["release_date_utc"])
pre = [row for row in daily if row["day"] < release.isoformat()]
post = [row for row in daily if row["day"] >= release.isoformat()]
pre_mean = sum(row["dau"] for row in pre) / len(pre)
post_mean = sum(row["dau"] for row in post) / len(post)
matched_before = matched[0]["active_user_days"] / matched[0]["calendar_days"]
matched_after = matched[1]["active_user_days"] / matched[1]["calendar_days"]
relative_change = (matched_after / matched_before - 1) * 100
zero_days = sum(row["dau"] == 0 for row in daily)
BLUE, TEAL, ORANGE, INK = "#3b6daa", "#087c83", "#dc741f", "#182b3a"
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.spines.left": False,
    "axes.spines.bottom": False,
    "axes.labelcolor": INK,
    "xtick.color": "#536574",
    "ytick.color": "#536574",
    "svg.fonttype": "none",
    "savefig.facecolor": "white",
})


def save_plot(fig, name):
    fig.savefig(PLOTS / (name + ".png"), dpi=130, bbox_inches="tight")
    buffer = io.StringIO()
    fig.savefig(buffer, format="svg", bbox_inches="tight")
    plt.close(fig)
    svg = buffer.getvalue()
    svg = svg[svg.index("<svg"):]
    for item in sorted(set(re.findall(r'id="([^"]+)"', svg)), key=len, reverse=True):
        prefixed = name + "_" + item
        svg = svg.replace('id="' + item + '"', 'id="' + prefixed + '"')
        svg = svg.replace('href="#' + item + '"', 'href="#' + prefixed + '"')
        svg = svg.replace("url(#" + item + ")", "url(#" + prefixed + ")")
    (PLOTS / (name + ".svg")).write_text(svg)
    return svg


dates = [date.fromisoformat(row["day"]) for row in daily]
fig, ax = plt.subplots(figsize=(11.4, 4.2), layout="constrained")
ax.plot(dates, [row["dau"] for row in daily], color="#bdcbd9",
        linewidth=1, label="Daily active users")
ax.plot(dates, [row["trailing_7_day_average"] for row in daily],
        color=TEAL, linewidth=2, label="Trailing 7-day mean")
ax.axvline(release, color=ORANGE, linewidth=1.4, linestyle="--")
ax.hlines(pre_mean, dates[0], release - timedelta(days=1),
          color=BLUE, linestyles=":", linewidth=1.5)
ax.hlines(post_mean, release, dates[-1],
          color=BLUE, linestyles=":", linewidth=1.5)
ax.text(dates[4], 8.0, "Full-period mean: " + f"{pre_mean:.2f}",
        color=BLUE, fontsize=9)
ax.text(dates[-100], 21.2, "Full-period mean: " + f"{post_mean:.2f}",
        color=BLUE, fontsize=9)
ax.text(release + timedelta(days=5), 25.5, "Kanban launch\n2 Jun 2018",
        color=ORANGE, fontsize=9, va="top")
ax.set_ylim(0, 27)
ax.set_ylabel("Unique users with a recorded login")
ax.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=6))
locator = mdates.AutoDateLocator(minticks=7, maxticks=11)
ax.xaxis.set_major_locator(locator)
ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
ax.grid(axis="y", color="#e5ebf0", linewidth=0.7)
ax.set_axisbelow(True)
ax.legend(loc="upper right", frameon=False, fontsize=9)
dau_svg = save_plot(fig, "daily_active_users")

fig, ax = plt.subplots(figsize=(12.3, 48))
labels = [f"{row['card_id']:03d} · {row['card_name']}" for row in cards]
values = [row["status_changes"] for row in cards]
positions = list(range(len(cards)))
ax.barh(positions, values, color=BLUE, height=0.72)
ax.set_yticks(positions, labels=labels, fontsize=8.5)
ax.invert_yaxis()
ax.set_ylim(len(cards) - 0.5, -0.5)
ax.set_xlim(0, max(values) + 0.7)
ax.set_xticks(range(max(values) + 1))
ax.xaxis.tick_top()
ax.xaxis.set_label_position("top")
ax.set_xlabel("Status transitions per card — creation events excluded", labelpad=13)
ax.tick_params(axis="both", length=0, pad=6)
ax.grid(axis="x", color="#e5ebf0", linewidth=0.7)
ax.set_axisbelow(True)
for y, value in enumerate(values):
    ax.text(value + 0.06, y, str(value), va="center", fontsize=8.5, color=INK)
fig.subplots_adjust(left=0.42, right=0.97, top=0.988, bottom=0.008)
cards_svg = save_plot(fig, "status_changes_by_card")

changes = defaultdict(int)
for row in queries["daily_status_changes_by_card"]:
    changes[row["day"]] += row["status_changes"]
last_card_day = max(row["day"] for row in queries["daily_status_changes_by_card"])
change_dates = []
day = release
while day <= date.fromisoformat(last_card_day):
    change_dates.append(day)
    day += timedelta(days=1)
change_values = [changes[day.isoformat()] for day in change_dates]
fig, ax = plt.subplots(figsize=(11.4, 3.2), layout="constrained")
ax.plot(change_dates, change_values, color=BLUE, linewidth=1.3)
ax.set_ylim(bottom=0)
ax.set_ylabel("Status changes / day")
ax.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=5))
locator = mdates.AutoDateLocator(minticks=6, maxticks=10)
ax.xaxis.set_major_locator(locator)
ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
ax.grid(axis="y", color="#e5ebf0", linewidth=0.7)
ax.set_axisbelow(True)
changes_svg = save_plot(fig, "daily_status_changes")

sql = (ROOT / "answer.sql").read_text()
sql_data = base64.b64encode(sql.encode()).decode()
json_data = base64.b64encode(json.dumps(payload, indent=2).encode()).decode()
distribution = Counter(values)
distribution_text = "; ".join(
    f"{count} changes: {number} cards" for count, number in sorted(distribution.items())
)
matched_rows = "".join(
    "<tr><td>" + html.escape(row["period"]) + "</td><td>" +
    row["start_day"] + " → " + row["end_day"] + "</td><td>28</td><td>" +
    f"{row['active_user_days'] / row['calendar_days']:.2f}" +
    "</td><td>" + str(row["unique_users_in_window"]) + "</td></tr>"
    for row in matched
)
transition_rows = "".join(
    "<tr><td>" + html.escape(row["from_status"]) + " → " +
    html.escape(row["to_status"]) + "</td><td>" + str(row["status_changes"]) +
    "</td><td>" + str(row["distinct_cards"]) + "</td></tr>"
    for row in queries["transition_counts"]
)
raw_cards = "".join(
    "<tr><td>" + str(row["card_id"]) + "</td><td>" + html.escape(row["card_name"]) +
    "</td><td>" + html.escape(row["current_status"]) + "</td><td>" +
    str(row["status_changes"]) + "</td></tr>" for row in cards
)

document = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Shiptivitas · Task 3 analytics</title>
<style>
:root{color-scheme:light;--ink:#182b3a;--muted:#536574;--line:#dfe6ec;--teal:#087c83}
*{box-sizing:border-box}body{margin:0;background:#f3f6f9;color:var(--ink);font:16px/1.6 "Segoe UI",Arial,sans-serif}
main{max-width:1160px;margin:0 auto;padding:48px 32px 64px}header{padding:0 2px 26px}
.eyebrow{color:var(--teal);font-size:13px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase}
h1{font-size:42px;line-height:1.12;letter-spacing:-1.1px;margin:12px 0 18px;max-width:830px}
h2{font-size:25px;line-height:1.25;letter-spacing:-.3px;margin:0 0 16px}
h3{font-size:19px;line-height:1.3;margin:0 0 12px}p{margin:10px 0 16px}.muted,.caption{color:var(--muted)}
.caption{font-size:13px}.section{margin:20px 0;background:white;padding:28px;border:1px solid var(--line);border-radius:16px}
.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:4px 0 26px}
.metric{background:white;padding:19px;border:1px solid var(--line);border-radius:12px}
.metric .label{font-size:12px;color:var(--muted);font-weight:600}.metric strong{display:block;font-size:32px;line-height:1.3;margin:6px 0}
.metric .note{font-size:12px;color:var(--muted)}.callout{border-left:4px solid var(--teal);background:#eef7f7;padding:14px 18px;border-radius:0 10px 10px 0;margin:16px 0}
.chart svg{display:block;width:100%;height:auto}.scroll-plot{height:580px;overflow:auto;border:1px solid var(--line);border-radius:10px;margin:14px 0;padding:12px;background:white}
.scroll-plot svg{display:block;width:100%;min-width:920px;height:auto}
.table-wrap{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px;margin:14px 0}
th,td{text-align:left;padding:10px 12px;border-bottom:1px solid var(--line)}th{background:#f3f6f9;font-weight:600}
.ideas{display:grid;gap:18px}.idea{border:1px solid var(--line);border-radius:12px;padding:22px}.idea .evidence{color:var(--teal);font-size:13px;font-weight:600}
dl{margin:14px 0 0}dt{font-weight:700;font-size:13px;margin-top:12px}dd{margin:4px 0 0;font-size:14px}
.buttons{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0 6px}
.button{display:inline-block;background:var(--ink);color:white;text-decoration:none;padding:9px 14px;border-radius:8px;font-size:13px;font-weight:600}
a{color:#215c96}details{margin-top:18px}summary{cursor:pointer;font-weight:600}pre{white-space:pre;overflow:auto;max-height:500px;background:#f4f7fa;padding:20px;font:12px/1.6 Consolas,monospace;border-radius:10px}
code{font-family:Consolas,monospace}.hash{font-size:11px;word-break:break-all}li{margin:7px 0}footer{font-size:12px;color:var(--muted);padding:14px 2px}
@media(max-width:740px){main{padding:24px 14px}h1{font-size:32px}.metrics{grid-template-columns:repeat(2,1fr)}.section{padding:20px}.metric strong{font-size:27px}}
@media print{body{background:white}main{max-width:none;padding:12px}.section,.metric{break-inside:avoid}.scroll-plot{height:auto;overflow:visible}.scroll-plot svg{min-width:0}.buttons{display:none}pre{max-height:none}}
</style></head><body><main>
<header><div class="eyebrow">Shiptivitas · Analytics · Task 3</div>
<h1>What changed after the Kanban launch?</h1>
<p class="muted">An analysis of recorded logins and card history, with three product hypotheses to test next.</p>
<p class="caption">Launch: 2 June 2018 · Observed login dates: 3 February 2018–1 February 2019 · UTC</p>
</header>
<div class="metrics">
<div class="metric"><span class="label">DAU · 28 days before</span><strong>@@BEFORE@@</strong><span class="note">5 May–1 June 2018</span></div>
<div class="metric"><span class="label">DAU · 28 days after</span><strong>@@AFTER@@</strong><span class="note">2–29 June 2018</span></div>
<div class="metric"><span class="label">Actual status changes</span><strong>286</strong><span class="note">Across 200 cards</span></div>
<div class="metric"><span class="label">Cards with no status changes</span><strong>38 / 200</strong><span class="note">19% of all cards</span></div>
</div>
<section class="section"><h2>1. Daily active users before and after release</h2>
<p>A user is active on a day if they have at least one recorded login that day. Repeat logins by the same user count once. The series includes every calendar day in the observed range.</p>
<div class="chart" role="img" aria-label="Daily active users across all 364 observed calendar days, with a seven-day mean and a marker on 2 June 2018.">@@DAU@@</div>
<p class="caption">Dotted horizontal segments show full-period means: @@FULLBEFORE@@ over 119 days before launch and @@FULLAFTER@@ over 245 days after launch. The first six rolling-average points use the available days.</p>
<div class="callout"><strong>Equal 28-day windows: observed average DAU increased by @@LIFT@@%.</strong><br>
The average rose from @@BEFORE@@ to @@AFTER@@, an increase of @@ABSOLUTE@@ active users per day. Each window contains four complete weeks.</div>
<div class="table-wrap"><table><thead><tr><th>Period</th><th>Dates, inclusive</th><th>Days</th><th>Average DAU</th><th>Unique users in window</th></tr></thead><tbody>@@MATCHED@@</tbody></table></div>
<p class="caption">This is an observed before/after difference, not an estimated causal effect. The population of users who logged in also changed from 24 to 71, and there is no control group or feature-exposure log. User growth, existing trends and other changes could contribute.</p>
</section>
<section class="section"><h2>2. Status changes by card</h2>
<p>The database contains 486 card-history records: 200 initial creations and <strong>286 actual status transitions</strong>. Creation records have no previous status and are excluded. Changes that only affect priority would also be excluded; this dataset contains none.</p>
<p><strong>162 cards changed status at least once.</strong> The remaining 38 did not. All 200 cards appear below, including the zero-change cards. Scroll to see the full ranked chart.</p>
<div class="scroll-plot" role="img" aria-label="Status-transition counts for all 200 cards, ranked by count. Counts range from zero to five.">@@CARDS@@</div>
<p class="caption">@@DISTRIBUTION@@.</p>
<div class="table-wrap"><table><thead><tr><th>Transition</th><th>Events</th><th>Distinct cards</th></tr></thead><tbody>@@TRANSITIONS@@</tbody></table></div>
<details><summary>View all 200 card counts as a table</summary><div class="table-wrap"><table><thead><tr><th>Card ID</th><th>Name</th><th>Current status</th><th>Status changes</th></tr></thead><tbody>@@RAW_CARDS@@</tbody></table></div></details>
<h3 style="margin-top:26px">Daily status activity</h3>
<p class="caption">The SQL also provides counts for each day/card pair. This supplemental chart sums those counts across cards by day, with zero-activity days filled in.</p>
<div class="chart" role="img" aria-label="Daily total card status changes after launch.">@@DAILY_CHANGES@@</div>
<p class="caption">@@CHANGE_DAYS@@ of the @@CARD_DAYS@@ days contain at least one status change. Multiple transitions by one card on the same day count as separate events.</p>
</section>
<section class="section"><h2>3. Three product ideas to test</h2>
<p class="muted">Expected impacts below are hypotheses, not measured outcomes or guaranteed forecasts.</p>
<div class="ideas">
<article class="idea"><h3>1 · Opt-in reminders for idle cards</h3>
<p class="evidence">Evidence: 35 backlog cards have no status transitions and were already at least 14 days old at the last recorded card event.</p>
<dl><dt>Hypothesis</dt><dd>Some unfinished work is forgotten. A useful, infrequent reminder could bring users back to review a card and choose a next step.</dd>
<dt>Expected impact</dt><dd>More return visits and more active days among users who subscribe to reminders. Test the daily active rate and seven-day return rate against a randomized control group; monitor unsubscribes.</dd>
<dt>Feature</dt><dd>Let users follow a card and opt into a digest when followed cards have not moved for 14 days. Include a direct link and simple snooze and unsubscribe controls. Treat reminders as suggestions: an idle card is not necessarily blocked.</dd></dl></article>
<article class="idea"><h3>2 · A personal “Next actions” view</h3>
<p class="evidence">Evidence: 102 cards remain unfinished in the snapshot: 44 in backlog and 58 in progress.</p>
<dl><dt>Hypothesis</dt><dd>A large shared board makes it harder to decide what to do next. A small personal queue could make the product useful as a daily starting point.</dd>
<dt>Expected impact</dt><dd>More repeated use on working days and shorter time to the first useful action. Compare active days per user and the seven-day return rate in an A/B test, while checking task completion time.</dd>
<dt>Feature</dt><dd>Allow users to pin a few cards, add a next-action note and optionally set a due date. Show those cards in a compact view with direct access to the board.</dd></dl></article>
<article class="idea"><h3>3 · Completion subscriptions and a progress feed</h3>
<p class="evidence">Evidence: 103 transitions enter complete, involving 101 distinct cards. The history also contains 16 backward transitions, so work can be reopened.</p>
<dl><dt>Hypothesis</dt><dd>People who monitor work may miss relevant updates. A concise feed could give them a useful reason to return and review progress.</dd>
<dt>Expected impact</dt><dd>More return visits by followers after relevant updates. Measure incremental return activity in an A/B test; check whether a digest replaces visits instead and monitor notification opt-outs.</dd>
<dt>Feature</dt><dd>Let users subscribe to selected cards. Offer an in-app feed and an optional digest of completed or reopened work, with links to the changed cards and a short history of what happened.</dd></dl></article>
</div></section>
<section class="section"><h2>4. Definitions, limits and reproducibility</h2>
<ul>
<li><strong>DAU definition:</strong> distinct <code>user_id</code> values in <code>login_history</code> per UTC date. This measures recorded logins; it cannot detect an active user whose session carries over without a new login.</li>
<li><strong>Calendar coverage:</strong> 364 dates, including @@ZERO_DAYS@@ dates with no recorded logins. Zero filling assumes continuous data collection; the dataset has no outage metadata.</li>
<li><strong>Release boundary:</strong> 2 June 2018 is treated as the first post-release UTC day because no exact launch time or timezone is supplied.</li>
<li><strong>Card activity:</strong> count an event only when both statuses exist and differ. Include cards with zero transitions. A creation is not a transition.</li>
<li><strong>Interpretation:</strong> the supplied history spans months, despite the scenario's “one week” wording. No user-to-card ownership link, feature exposure, or support-ticket dataset is supplied. These records cannot establish why usage changed or attribute a card event to an individual user.</li>
<li><strong>Next measurement step:</strong> add user-linked feature and card-action events, capture feature exposure, and test the ideas with randomized groups of eligible users.</li>
</ul>
<p>To rerun the SQL, put <code>answer.sql</code> and <code>analyze.cjs</code> beside the repository's <code>shiptivity.db</code> and run <code>node analyze.cjs</code> with Node.js 24. The database is opened read-only; results are written to <code>analysis-results.json</code>.</p>
<div class="buttons"><a class="button" download="answer.sql" href="data:text/plain;charset=utf-8;base64,@@SQL_DOWNLOAD@@">Download SQL</a><a class="button" download="analysis-results.json" href="data:application/json;base64,@@JSON_DOWNLOAD@@">Download query results</a></div>
<details><summary>Read the complete SQL queries</summary><pre><code>@@SQL@@</code></pre></details>
</section>
<footer>Source: <a href="https://github.com/insidesherpa/-shiptivitas-3">insidesherpa/-shiptivitas-3</a> · Release date: <a href="https://github.com/insidesherpa/-shiptivitas-3/blob/master/README.md">repository README</a>.<br>
Database Git blob: <code>878a30fc1de0fc85ea35c8ed1caeff1deab8605c</code><br>
<span class="hash">Database SHA-256: @@HASH@@</span></footer>
</main></body></html>
"""
replacements = {
    "BEFORE": f"{matched_before:.2f}", "AFTER": f"{matched_after:.2f}",
    "LIFT": f"{relative_change:.1f}", "ABSOLUTE": f"{matched_after-matched_before:.2f}",
    "FULLBEFORE": f"{pre_mean:.2f}", "FULLAFTER": f"{post_mean:.2f}",
    "DAU": dau_svg, "CARDS": cards_svg, "DAILY_CHANGES": changes_svg,
    "MATCHED": matched_rows, "TRANSITIONS": transition_rows, "RAW_CARDS": raw_cards,
    "DISTRIBUTION": distribution_text, "ZERO_DAYS": str(zero_days),
    "CHANGE_DAYS": str(sum(value > 0 for value in change_values)),
    "CARD_DAYS": str(len(change_dates)),
    "SQL_DOWNLOAD": sql_data, "JSON_DOWNLOAD": json_data,
    "SQL": html.escape(sql), "HASH": payload["database_sha256"],
}
for key, value in replacements.items():
    document = document.replace("@@" + key + "@@", value)
assert "@@" not in document
(ROOT / "task3_submission.html").write_text(document, encoding="utf-8")

package_files = [
    "task3_submission.html", "answer.sql", "analyze.cjs",
    "analysis-results.json", "README_ANALYSIS.md", "build_report.py",
]
with zipfile.ZipFile(ROOT / "task3_files.zip", "w", zipfile.ZIP_DEFLATED) as package:
    for filename in package_files:
        package.write(ROOT / filename, arcname=filename)

print(json.dumps({
    "report": str(ROOT / "task3_submission.html"),
    "daily_rows": len(daily), "card_rows": len(cards),
    "status_changes": sum(values), "matched_increase_percent": relative_change,
    "full_period_means": [pre_mean, post_mean],
    "zero_login_days": zero_days,
    "card_activity_days": len(change_dates), "active_card_days": sum(v > 0 for v in change_values),
    "report_bytes": (ROOT / "task3_submission.html").stat().st_size,
    "zip_bytes": (ROOT / "task3_files.zip").stat().st_size,
}, indent=2))
