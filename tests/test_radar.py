"""Tests for the scoring, trend and playbook layers.

Nothing here touches the network - every test builds its own repo fixtures.
"""

import datetime
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import generate_site  # noqa: E402
import playbook  # noqa: E402
import scanner  # noqa: E402
import trends  # noqa: E402

NOW = datetime.datetime(2026, 7, 27, tzinfo=datetime.timezone.utc)


def repo(**overrides):
    base = {
        "full_name": "acme/thing",
        "name": "thing",
        "description": "A tool",
        "topics": [],
        "html_url": "https://github.com/acme/thing",
        "stargazers_count": 1000,
        "forks_count": 10,
        "open_issues_count": 5,
        "created_at": "2026-07-01T00:00:00Z",
        "pushed_at": "2026-07-26T00:00:00Z",
        "homepage": "https://example.com",
        "license": {"key": "mit"},
        "archived": False,
        "disabled": False,
        "fork": False,
    }
    base.update(overrides)
    return base


class ScoringTests(unittest.TestCase):
    def test_velocity_uses_repo_age(self):
        vel, age = scanner.velocity_of(
            repo(stargazers_count=2600, created_at="2026-07-01T00:00:00Z"), NOW
        )
        self.assertEqual(age, 26)
        self.assertEqual(round(vel), 100)

    def test_score_is_capped_at_100(self):
        score, _, _ = scanner.score_repo(
            repo(
                stargazers_count=200000,
                description="claude agent mcp skill llm assistant framework",
                homepage="",
                license=None,
                open_issues_count=500,
                forks_count=50000,
            ),
            NOW,
        )
        self.assertEqual(score, 100)

    def test_score_never_goes_negative(self):
        score, _, _ = scanner.score_repo(
            repo(
                stargazers_count=1,
                created_at="2020-01-01T00:00:00Z",
                pushed_at="2020-01-01T00:00:00Z",
                homepage="https://x.com",
            ),
            NOW,
        )
        self.assertGreaterEqual(score, 0)

    def test_components_sum_to_score(self):
        score, _, components = scanner.score_repo(
            repo(stargazers_count=3000, description="an agent framework", homepage=""),
            NOW,
        )
        self.assertEqual(score, sum(c["points"] for c in components))

    def test_stale_push_is_penalised(self):
        fresh, _, _ = scanner.score_repo(repo(pushed_at="2026-07-26T00:00:00Z"), NOW)
        stale, _, comps = scanner.score_repo(
            repo(pushed_at="2026-05-01T00:00:00Z"), NOW
        )
        self.assertLess(stale, fresh)
        self.assertIn("Maintenance risk", [c["label"] for c in comps])

    def test_missing_homepage_scores_a_commercial_gap(self):
        _, _, comps = scanner.score_repo(repo(homepage=""), NOW)
        details = " ".join(c["detail"] for c in comps)
        self.assertIn("no official site", details)

    def test_archived_and_forked_repos_are_ineligible(self):
        self.assertFalse(scanner.is_eligible(repo(archived=True)))
        self.assertFalse(scanner.is_eligible(repo(fork=True)))
        self.assertFalse(scanner.is_eligible(repo(disabled=True)))
        self.assertTrue(scanner.is_eligible(repo()))

    def test_ideas_are_deduplicated_and_never_empty(self):
        ideas = scanner.opportunity_ideas(
            repo(description="an mcp agent skill", homepage="", stargazers_count=9000)
        )
        self.assertEqual(len(ideas), len(set(ideas)))
        self.assertTrue(ideas)
        self.assertTrue(scanner.opportunity_ideas(repo(description="a css reset")))


class TrendTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir)

    def snap(self, date, items):
        trends.save_snapshot({"date": date, "items": items}, self.dir)

    def test_round_trip_and_ordering(self):
        self.snap("2026-07-20", [{"name": "a", "stars": 10, "score": 50}])
        self.snap("2026-07-13", [{"name": "a", "stars": 5, "score": 40}])
        dates = [s["date"] for s in trends.load_snapshots(self.dir)]
        self.assertEqual(dates, ["2026-07-13", "2026-07-20"])

    def test_same_day_rescan_overwrites(self):
        self.snap("2026-07-20", [{"name": "a", "stars": 10, "score": 50}])
        self.snap("2026-07-20", [{"name": "a", "stars": 99, "score": 50}])
        snaps = trends.load_snapshots(self.dir)
        self.assertEqual(len(snaps), 1)
        self.assertEqual(snaps[0]["items"][0]["stars"], 99)

    def test_first_appearance_is_new(self):
        self.snap("2026-07-27", [{"name": "a", "stars": 10, "score": 50}])
        items = [{"name": "a", "stars": 10, "score": 50}]
        trends.annotate(items, trends.load_snapshots(self.dir))
        self.assertEqual(items[0]["status"], "new")
        self.assertIsNone(items[0]["star_delta"])

    def test_growth_thresholds_are_normalised_per_day(self):
        # +20% over 7 days is ~2.9%/day: accelerating.
        self.snap("2026-07-20", [{"name": "a", "stars": 100, "score": 50}])
        self.snap("2026-07-27", [{"name": "a", "stars": 120, "score": 55}])
        items = [{"name": "a", "stars": 120, "score": 55}]
        trends.annotate(items, trends.load_snapshots(self.dir))
        self.assertEqual(items[0]["status"], "accelerating")
        self.assertEqual(items[0]["star_delta"], 20)
        self.assertEqual(items[0]["score_delta"], 5)
        self.assertEqual(items[0]["days_since_compared"], 7)

    def test_same_growth_over_one_day_is_still_accelerating(self):
        self.snap("2026-07-26", [{"name": "a", "stars": 100, "score": 50}])
        self.snap("2026-07-27", [{"name": "a", "stars": 120, "score": 50}])
        items = [{"name": "a", "stars": 120, "score": 50}]
        trends.annotate(items, trends.load_snapshots(self.dir))
        self.assertEqual(items[0]["status"], "accelerating")

    def test_flat_growth_is_cooling(self):
        self.snap("2026-07-20", [{"name": "a", "stars": 100, "score": 50}])
        self.snap("2026-07-27", [{"name": "a", "stars": 101, "score": 50}])
        items = [{"name": "a", "stars": 101, "score": 50}]
        trends.annotate(items, trends.load_snapshots(self.dir))
        self.assertEqual(items[0]["status"], "cooling")

    def test_history_is_capped_for_the_sparkline(self):
        for day in range(1, 20):
            self.snap(
                "2026-06-%02d" % day, [{"name": "a", "stars": day * 10, "score": 50}]
            )
        items = [{"name": "a", "stars": 200, "score": 50}]
        trends.annotate(items, trends.load_snapshots(self.dir))
        self.assertLessEqual(len(items[0]["history"]), trends.SPARK_POINTS)

    def test_departed_lists_repos_that_fell_off(self):
        self.snap(
            "2026-07-20",
            [
                {"name": "a", "stars": 10, "score": 80, "url": "u"},
                {"name": "b", "stars": 10, "score": 70, "url": "u"},
            ],
        )
        self.snap("2026-07-27", [{"name": "a", "stars": 20, "score": 80, "url": "u"}])
        gone = trends.departed(trends.load_snapshots(self.dir))
        self.assertEqual([g["name"] for g in gone], ["b"])

    def test_board_summary_counts_and_deltas(self):
        self.snap(
            "2026-07-20",
            [{"name": "a", "stars": 100, "score": 80}, {"name": "b", "stars": 50, "score": 40}],
        )
        self.snap(
            "2026-07-27",
            [{"name": "a", "stars": 160, "score": 80}, {"name": "c", "stars": 20, "score": 75}],
        )
        s = trends.board_summary(trends.load_snapshots(self.dir))
        self.assertEqual(s["tracked"], 2)
        self.assertEqual(s["high_conviction"], 2)
        self.assertEqual(s["high_conviction_delta"], 1)
        self.assertEqual(s["new_entries"], 1)
        self.assertEqual(s["stars_gained"], 60)
        self.assertEqual(s["days_since_previous"], 7)

    def test_empty_history_summary_is_safe(self):
        self.assertEqual(trends.board_summary([]), {})


class PlaybookTests(unittest.TestCase):
    def test_docs_play_wins_when_a_big_repo_has_no_site(self):
        play = playbook.pick_play(
            {"name": "a", "description": "an agent", "homepage": "", "stars": 5000}
        )
        self.assertEqual(play["key"], "docs")

    def test_support_play_when_issues_pile_up(self):
        play = playbook.pick_play(
            {"name": "a", "description": "a tool", "homepage": "x", "stars": 100, "open_issues": 90}
        )
        self.assertEqual(play["key"], "support")

    def test_every_repo_gets_a_play(self):
        play = playbook.pick_play({"name": "z", "description": "", "stars": 1})
        self.assertIsNotNone(play)
        self.assertTrue(play["steps"])

    def test_focus_prefers_an_open_window_over_a_higher_score(self):
        items = [
            {"name": "high", "url": "u", "score": 95, "status": "cooling", "velocity": 5},
            {"name": "open", "url": "u", "score": 80, "status": "accelerating", "velocity": 5},
        ]
        self.assertEqual(playbook.focus_for(items)["name"], "open")

    def test_focus_falls_back_when_nothing_is_new(self):
        items = [{"name": "only", "url": "u", "score": 60, "status": "steady", "velocity": 1}]
        self.assertEqual(playbook.focus_for(items)["name"], "only")

    def test_focus_of_an_empty_board_is_none(self):
        self.assertIsNone(playbook.focus_for([]))

    def test_build_attaches_the_loop_and_per_item_plays(self):
        data = playbook.build(
            {"items": [{"name": "a", "url": "u", "score": 70, "status": "new", "velocity": 3}]}
        )
        self.assertTrue(data["daily_loop"])
        self.assertEqual(data["loop_minutes"], sum(s["minutes"] for s in playbook.DAILY_LOOP))
        self.assertTrue(data["items"][0]["play"])
        self.assertTrue(data["items"][0]["why_now"])


class SiteTests(unittest.TestCase):
    def board(self):
        return {
            "date": "2026-07-27",
            "items": [
                {
                    "name": "acme/<script>alert(1)</script>",
                    "score": 80,
                    "stars": 100,
                    "velocity": 5.0,
                    "description": "</script><img src=x onerror=alert(1)>",
                    "reasons": ["fast"],
                    "ideas": ["sell it"],
                    "url": "https://github.com/acme/thing",
                    "found_via": "test",
                    "status": "new",
                    "history": [{"date": "2026-07-27", "stars": 100, "score": 80}],
                }
            ],
            "summary": {"tracked": 1},
            "focus": None,
            "daily_loop": playbook.DAILY_LOOP,
            "loop_minutes": 110,
        }

    def test_untrusted_strings_cannot_break_out_of_the_json_block(self):
        page = generate_site.build_page(self.board(), {})
        self.assertNotIn("</script><img", page)
        self.assertIn("<\\/script>", page)

    def test_config_urls_are_attribute_escaped(self):
        page = generate_site.build_page(
            self.board(), {"newsletter_url": "https://x.com/?a=1'onmouseover='alert(1)"}
        )
        self.assertNotIn("'onmouseover='", page)

    def test_no_placeholders_survive(self):
        page = generate_site.build_page(self.board(), {"site_title": "T"})
        for token in ("__TITLE__", "__TAGLINE__", "__CTA__", "__DATA__"):
            self.assertNotIn(token, page)

    def test_embedded_payload_round_trips(self):
        board = self.board()
        page = generate_site.build_page(board, {})
        start = page.index('id="radar-data">') + len('id="radar-data">')
        end = page.index("</script>", start)
        payload = json.loads(page[start:end].replace("<\\/", "</"))
        self.assertEqual(payload["items"][0]["score"], 80)


if __name__ == "__main__":
    unittest.main()
