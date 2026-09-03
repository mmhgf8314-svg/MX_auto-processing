"""Tests for the reply-waiting bookkeeping.

The cases here are the ones that actually went wrong in the mailbox on
2026-09-03, written down so they cannot go wrong the same way twice:

  * elapsed days counted off a clock two days behind, and in the wrong zone;
  * fourteen copies of one event announcement entering the waiting list;
  * eleven duplicate chase drafts from runs that overlapped.
"""

from __future__ import annotations

import json
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mxmail.followup import (  # noqa: E402
    Assessment,
    FollowupSettings,
    assess,
    business_days_elapsed,
    chase_plan,
    find_bulk,
    load_followup_settings,
    owner_send_address,
)
from mxmail.triage import Config, Message  # noqa: E402

SAMPLES = ROOT / "samples"

OWNER = "taku_yamashita@mxvideo.jp"
ALIASES = ("taku_yamashita@madokatech.co.jp", "mmhgf8314@gmail.com")

CFG = Config(
    owner_mailbox=OWNER,
    owner_aliases=ALIASES,
    owner={"mailbox": OWNER},
    matrox_domains=("matrox.com", "mxvideo.jp"),
    ignore_addresses=(),
    ignore_localpart_patterns=(),
    ignore_domains=(),
    ignore_subject_patterns=(),
    parties=(),
    handoff_signals=(),
    low_signals=(),
    case_alias_index={},
    case_names={},
)


def msg(sender, date_, *, body="", subject="s", thread="t", to=None) -> Message:
    return Message(
        sender=sender,
        subject=subject,
        body=body,
        to=list(to or []),
        date=date_,
        thread_id=thread,
    )


# ---------------------------------------------------------------------------
# Business days
# ---------------------------------------------------------------------------


class BusinessDaysTest(unittest.TestCase):
    def test_same_day_is_zero(self):
        # Both instants fall on 27 Aug in Tokyo (16:39 and 21:00).
        self.assertEqual(
            business_days_elapsed("2026-08-27T07:39:00Z", "2026-08-27T12:00:00Z"), 0
        )

    def test_thursday_to_tuesday_skips_the_weekend(self):
        # Thu 27 Aug -> Tue 1 Sep JST: Fri, Mon, Tue.
        self.assertEqual(
            business_days_elapsed("2026-08-27T07:39:00Z", "2026-09-01T00:00:00Z"), 3
        )

    def test_counted_in_jst_not_utc(self):
        """23:00 UTC is already the next morning in Tokyo.

        The routine fires at 23:00 UTC. Counting in UTC loses a day on every
        single run, which is how a Thursday chase slips to Friday.
        """
        sent = "2026-08-27T07:39:00Z"
        self.assertEqual(business_days_elapsed(sent, "2026-08-31T23:01:00Z"), 3)

    def test_holidays_are_not_business_days(self):
        # 2026-09-21 (Mon) as a public holiday.
        holidays = [date(2026, 9, 21)]
        both = ("2026-09-18T00:00:00Z", "2026-09-22T09:00:00Z")
        self.assertEqual(business_days_elapsed(*both), 2)
        self.assertEqual(business_days_elapsed(*both, holidays=holidays), 1)

    def test_future_send_never_goes_negative(self):
        self.assertEqual(
            business_days_elapsed("2026-09-10T00:00:00Z", "2026-09-01T00:00:00Z"), 0
        )


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


class SettingsTest(unittest.TestCase):
    def test_repo_config_carries_the_followup_table(self):
        settings = load_followup_settings(ROOT / "config" / "routing.toml")
        self.assertEqual(settings.waiting_label, "00_返信待ち")
        self.assertEqual(settings.chased_label, "00_催促済み")
        self.assertEqual(settings.chase_after_business_days, 3)
        self.assertEqual(settings.max_chases_per_run, 5)
        self.assertIn(date(2026, 9, 23), settings.holidays)
        self.assertEqual(settings.default_from, OWNER)
        self.assertIn("gsx.co.jp", settings.from_map)

    def test_missing_file_falls_back_to_defaults(self):
        settings = load_followup_settings(ROOT / "config" / "does-not-exist.toml")
        self.assertEqual(settings, FollowupSettings())


# ---------------------------------------------------------------------------
# Bulk announcements
# ---------------------------------------------------------------------------


ANNOUNCEMENT = """{name}様

いつもお世話になっております。
GlobalMの山下でございます。

9月11日から14日にアムステルダムのRAIで開催されますIBC2026に、弊社GlobalMも出展いたします。
{name}様は今年のIBCにご参加のご予定はございますでしょうか。

今回は、クラウド・ハイブリッド・オンプレミスの各環境で同一のライブIPワークフローを
展開できる、ソフトウェア定義メディアプラットフォームの最新版をご紹介いたします。
"""


def announcements(n: int) -> list[Message]:
    names = ["三澤", "新野", "露口", "小沢", "朝比奈", "平田", "太田"][:n]
    return [
        msg(
            OWNER,
            "2026-08-31T09:50:00Z",
            body=ANNOUNCEMENT.format(name=name),
            subject="【GlobalM】IBC2026 出展のご案内",
            thread=f"thread-{i}",
            to=[f"p{i}@example.co.jp"],
        )
        for i, name in enumerate(names)
    ]


class FindBulkTest(unittest.TestCase):
    def test_mail_merge_collapses_onto_one_fingerprint(self):
        bulk = find_bulk(announcements(7))
        self.assertEqual(len(bulk), 7)
        self.assertEqual(len({g.fingerprint for g in bulk.values()}), 1)
        self.assertEqual(next(iter(bulk.values())).size, 7)

    def test_a_question_does_not_rescue_an_announcement(self):
        """The body asks 'ご参加のご予定はございますでしょうか' outright.

        No keyword test can separate that from a genuine request. The shape
        can: a request goes to one person, an announcement goes to a list.
        """
        self.assertIn("ご参加のご予定", ANNOUNCEMENT)
        bulk = find_bulk(announcements(7))
        self.assertEqual(set(bulk), {f"thread-{i}" for i in range(7)})

    def test_two_copies_are_not_a_mail_merge(self):
        self.assertEqual(find_bulk(announcements(2)), {})

    def test_genuine_requests_are_left_alone(self):
        messages = [
            msg(OWNER, "2026-08-31T08:35:00Z", body="岡田さん\n\n貸出機材の確保をMatrox本社に依頼します。留意点をお教えください。", thread="a"),
            msg(OWNER, "2026-08-31T08:52:00Z", body="Hi Franc,\n\nFollowing up on the ST 2110 loaner campaign for Japan.", thread="b"),
            msg(OWNER, "2026-08-31T04:01:00Z", body="松本様\n\nオンラインミーティングのリンクをお待ちしております。", thread="c"),
        ]
        self.assertEqual(find_bulk(messages), {})

    def test_sample_sent_file_is_one_announcement(self):
        payload = json.loads((SAMPLES / "followup_sent_bulk.json").read_text(encoding="utf-8"))
        bulk = find_bulk([Message.from_gmail(m) for m in payload])
        self.assertEqual(len(bulk), 4)
        self.assertEqual(len({g.fingerprint for g in bulk.values()}), 1)


# ---------------------------------------------------------------------------
# Assessment
# ---------------------------------------------------------------------------


class AssessTest(unittest.TestCase):
    # The routine's own fire time: 23:01 UTC, which is 08:01 JST the *next*
    # morning -- Friday 4 September. Every count below is anchored there.
    NOW = "2026-09-03T23:01:00Z"

    def test_owner_wrote_last_is_waiting(self):
        thread = [
            msg("okada@j-material.jp", "2026-08-24T23:25:00Z", thread="t"),
            msg(OWNER, "2026-08-27T07:39:00Z", thread="t"),
        ]
        a = assess("t", thread, CFG, self.NOW)
        self.assertEqual(a.state, "waiting")
        self.assertTrue(a.is_waiting)
        # Sent Thu 27 Aug JST; Fri 28, Mon 31, Tue 1, Wed 2, Thu 3, Fri 4.
        self.assertEqual(a.business_days, 6)
        self.assertEqual(a.counterparty, "okada@j-material.jp")

    def test_inbound_last_is_the_owners_ball(self):
        thread = [
            msg(OWNER, "2026-08-31T07:47:00Z", thread="t"),
            msg("myang@matrox.com", "2026-08-31T13:53:00Z", thread="t"),
        ]
        a = assess("t", thread, CFG, self.NOW)
        self.assertEqual(a.state, "owner_ball")
        self.assertEqual(a.business_days, 0)
        self.assertFalse(a.is_waiting)

    def test_acknowledgement_only_reply_is_flagged(self):
        """'we will get back to you' is not an answer.

        The state is still owner_ball by the blunt rule, but the flag is what
        stops the agent dropping the label on a thread that is, in substance,
        still stalled on the other side.
        """
        thread = [
            msg(OWNER, "2026-08-31T19:25:00Z", thread="t"),
            msg(
                "rgnagne@matrox.com",
                "2026-08-31T19:40:00Z",
                body="Hi Taku,\n\nThank you for clarifying, we will get back to you as soon as possible.",
                thread="t",
            ),
        ]
        self.assertTrue(assess("t", thread, CFG, self.NOW).ack_only_signal)

    def test_a_real_answer_is_not_flagged(self):
        thread = [
            msg(OWNER, "2026-08-31T07:47:00Z", thread="t"),
            msg(
                "myang@matrox.com",
                "2026-08-31T13:53:00Z",
                body="Hi Taku,\n\nBefore we quote, I would like to understand this project more.",
                thread="t",
            ),
        ]
        self.assertFalse(assess("t", thread, CFG, self.NOW).ack_only_signal)

    def test_bulk_thread_never_enters_the_waiting_list(self):
        thread = [msg(OWNER, "2026-08-31T09:50:00Z", body=ANNOUNCEMENT.format(name="三澤"), thread="t")]
        bulk = find_bulk(
            [
                msg(OWNER, "2026-08-31T09:50:00Z", body=ANNOUNCEMENT.format(name=n), thread=f"t{i}")
                for i, n in enumerate(["三澤", "新野", "露口"])
            ]
            + [msg(OWNER, "2026-08-31T09:50:00Z", body=ANNOUNCEMENT.format(name="平田"), thread="t")]
        )
        a = assess("t", thread, CFG, self.NOW, bulk=bulk)
        self.assertEqual(a.state, "bulk")
        self.assertFalse(a.is_waiting)

    def test_empty_thread(self):
        self.assertEqual(assess("t", [], CFG, self.NOW).state, "empty")

    def test_to_dict_round_trips_the_fields(self):
        thread = [msg(OWNER, "2026-08-27T07:39:00Z", thread="t", to=["x@example.co.jp"])]
        d = assess("t", thread, CFG, self.NOW).to_dict()
        self.assertEqual(d["threadId"], "t")
        self.assertEqual(d["state"], "waiting")
        self.assertEqual(d["businessDays"], 6)
        self.assertEqual(d["counterparty"], "x@example.co.jp")
        self.assertEqual(d["fromAddress"], OWNER)


class OwnerSendAddressTest(unittest.TestCase):
    def test_reuses_the_identity_already_used_in_the_thread(self):
        thread = [
            msg("htsuji@gsx.co.jp", "2026-08-24T02:10:00Z"),
            msg("taku_yamashita@madokatech.co.jp", "2026-08-24T07:23:00Z"),
            msg("htsuji@gsx.co.jp", "2026-08-30T05:14:00Z"),
        ]
        self.assertEqual(
            owner_send_address(thread, CFG, OWNER), "taku_yamashita@madokatech.co.jp"
        )

    def test_falls_back_when_the_owner_has_not_written_yet(self):
        thread = [msg("someone@example.com", "2026-08-24T02:10:00Z")]
        self.assertEqual(owner_send_address(thread, CFG, OWNER), OWNER)


# ---------------------------------------------------------------------------
# Chase planning
# ---------------------------------------------------------------------------


def waiting(thread_id: str, days: int) -> Assessment:
    return Assessment(
        thread_id=thread_id,
        subject=thread_id,
        state="waiting",
        business_days=days,
        from_address=OWNER,
    )


class ChasePlanTest(unittest.TestCase):
    def test_only_threads_past_the_threshold(self):
        due, _ = chase_plan([waiting("a", 3), waiting("b", 2)])
        self.assertEqual([c.thread_id for c in due], ["a"])

    def test_the_chased_label_suppresses_a_second_chase(self):
        due, _ = chase_plan([waiting("a", 9)], already_chased={"a"})
        self.assertEqual(due, [])

    def test_an_open_draft_suppresses_a_second_chase(self):
        """The guard the label cannot provide.

        A concurrent run has not labelled anything yet, but its draft is
        already in the mailbox. Eleven duplicates arrived exactly this way.
        """
        due, _ = chase_plan([waiting("a", 9)], has_open_draft={"a"})
        self.assertEqual(due, [])

    def test_oldest_first_and_capped(self):
        assessments = [waiting(f"t{i}", i + 3) for i in range(8)]
        due, deferred = chase_plan(
            assessments, settings=FollowupSettings(max_chases_per_run=5)
        )
        self.assertEqual(len(due), 5)
        self.assertEqual(len(deferred), 3)
        self.assertEqual([c.business_days for c in due], [10, 9, 8, 7, 6])

    def test_threads_holding_the_owners_ball_are_never_chased(self):
        stalled = Assessment(thread_id="x", subject="x", state="owner_ball", business_days=30)
        due, deferred = chase_plan([stalled])
        self.assertEqual(due, [])
        self.assertEqual(deferred, [])

    def test_chase_carries_the_send_address_and_reason(self):
        due, _ = chase_plan([waiting("a", 4)])
        self.assertEqual(due[0].from_address, OWNER)
        self.assertEqual(due[0].reason, "4 business days with no reply")


# ---------------------------------------------------------------------------
# The sample run from the migration notes
# ---------------------------------------------------------------------------


class SampleRunTest(unittest.TestCase):
    """3 threads, 1 waiting, 4 announcement copies excluded, 1 chase due."""

    NOW = "2026-09-04T08:00:00+09:00"

    def _assessments(self):
        sent = json.loads((SAMPLES / "followup_sent_bulk.json").read_text(encoding="utf-8"))
        bulk = find_bulk([Message.from_gmail(m) for m in sent])
        threads = json.loads((SAMPLES / "followup_threads.json").read_text(encoding="utf-8"))
        return [
            assess(t["id"], [Message.from_gmail(m) for m in t["messages"]], CFG, self.NOW, bulk=bulk)
            for t in threads
        ]

    def test_states(self):
        by_id = {a.thread_id: a for a in self._assessments()}
        self.assertEqual(by_id["t-mitomo"].state, "waiting")
        self.assertEqual(by_id["t-mitomo"].business_days, 6)
        self.assertEqual(by_id["t-raoul"].state, "owner_ball")
        self.assertTrue(by_id["t-raoul"].ack_only_signal)
        self.assertEqual(by_id["t-mingkai"].state, "owner_ball")
        self.assertFalse(by_id["t-mingkai"].ack_only_signal)

    def test_one_chase_due_unless_already_covered(self):
        assessments = self._assessments()
        due, deferred = chase_plan(assessments)
        self.assertEqual([c.thread_id for c in due], ["t-mitomo"])
        self.assertEqual(deferred, [])
        self.assertEqual(chase_plan(assessments, already_chased={"t-mitomo"})[0], [])
        self.assertEqual(chase_plan(assessments, has_open_draft={"t-mitomo"})[0], [])


if __name__ == "__main__":
    unittest.main()
