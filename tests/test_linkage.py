"""Tests for cross-thread handoff detection.

The scenario these are built around is the one that actually went wrong: a
customer answered on the Japanese thread that they had reproduced a fault and
captured logs, head office kept asking for those logs on the English case
thread, and neither side's news ever crossed.
"""

from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mxmail.linkage import (  # noqa: E402
    CaseKey,
    ThreadRef,
    canonical_key,
    extract_keys,
    find_gaps,
    group_by_key,
    thread_has_matrox,
)
from mxmail.triage import Message, load_config  # noqa: E402

CFG = load_config(ROOT / "config" / "routing.toml")
SAMPLES = ROOT / "samples"
NOW = datetime(2026, 8, 25, 9, 0, tzinfo=timezone.utc)


def load_thread(name: str) -> ThreadRef:
    payload = json.loads((SAMPLES / name).read_text(encoding="utf-8"))
    messages = [Message.from_gmail(m) for m in payload["messages"]]
    return ThreadRef.build(payload["id"], messages)


class KeyExtractionTests(unittest.TestCase):
    def test_case_number_in_subject(self):
        message = Message(subject="Case 00092203: The CIP-DSS SDI-OUT Interruption")
        self.assertIn(CaseKey("case", "00092203"), extract_keys(message))

    def test_bare_case_number_in_body(self):
        message = Message(subject="follow up", body="please use 00092203 from now on")
        self.assertIn(CaseKey("case", "00092203"), extract_keys(message))

    def test_salesforce_thread_token(self):
        message = Message(subject="Case 1 [ thread::BHov16dNMeW43s5KmUyu2js:: ]")
        self.assertIn(
            CaseKey("sf_thread", "BHov16dNMeW43s5KmUyu2js"), extract_keys(message)
        )

    def test_po_number(self):
        message = Message(subject="NEW PO JMGS05955 (8/21/2026)")
        self.assertIn(CaseKey("po", "JMGS05955"), extract_keys(message))

    def test_japanese_project_tag(self):
        message = Message(subject="【TBS統合FB】ConvertIP DSSの動作に関する問合せ")
        self.assertIn(CaseKey("tag", "TBS統合FB"), extract_keys(message))

    def test_decorative_tags_are_not_keys(self):
        message = Message(subject="【重要】過去にご注文された商品についてのお知らせ")
        self.assertEqual(extract_keys(message), set())

    def test_tags_in_the_body_are_ignored(self):
        # 【要確認：…】 placeholders and 【…展示概要】 blocks are decoration.
        message = Message(
            subject="IBC2026のご案内",
            body="【IBC 2026 Matrox展示概要】\n〇出展概要\n【要確認：出荷予定日】",
        )
        self.assertEqual(
            {k for k in extract_keys(message) if k.kind == "tag"}, set()
        )


class RegisterTests(unittest.TestCase):
    def test_tag_and_case_number_fold_onto_the_same_case(self):
        from_tag = canonical_key(CaseKey("tag", "TBS統合FB"), CFG)
        from_number = canonical_key(CaseKey("case", "00092203"), CFG)
        from_token = canonical_key(
            CaseKey("sf_thread", "BHov16dNMeW43s5KmUyu2js"), CFG
        )
        self.assertEqual(from_tag, CaseKey("case", "00092203"))
        self.assertEqual(from_tag, from_number)
        self.assertEqual(from_tag, from_token)

    def test_unregistered_identifier_is_its_own_key(self):
        key = CaseKey("po", "JMGS05955")
        self.assertEqual(canonical_key(key, CFG), key)

    def test_threads_group_under_one_case(self):
        threads = [load_thread("linkage_jp_thread.json"), load_thread("linkage_en_case.json")]
        groups = group_by_key(threads, CFG)
        self.assertEqual(len(groups[CaseKey("case", "00092203")]), 2)


class SideTests(unittest.TestCase):
    def test_japanese_thread_has_no_matrox_participant(self):
        # The owner's own mxvideo.jp address must not count as head office --
        # it is on both sides of every thread.
        self.assertFalse(thread_has_matrox(load_thread("linkage_jp_thread.json"), CFG))

    def test_case_thread_has_matrox(self):
        self.assertTrue(thread_has_matrox(load_thread("linkage_en_case.json"), CFG))

    def test_matrox_only_in_recipients_still_counts(self):
        thread = ThreadRef.build(
            "t",
            [
                Message(
                    sender="taku_yamashita@mxvideo.jp",
                    to=["convertipsupport@matrox.com"],
                    subject="Case 00092203",
                    date="2026-08-01T00:00:00Z",
                )
            ],
        )
        self.assertTrue(thread_has_matrox(thread, CFG))


class GapTests(unittest.TestCase):
    def setUp(self):
        self.threads = [
            load_thread("linkage_jp_thread.json"),
            load_thread("linkage_en_case.json"),
        ]

    def test_both_directions_are_reported(self):
        gaps = find_gaps(self.threads, CFG, now=NOW)
        self.assertEqual({g.direction for g in gaps}, {"jp_to_matrox", "matrox_to_jp"})

    def test_jp_gap_anchors_on_the_customers_reproduction_report(self):
        gaps = find_gaps(self.threads, CFG, now=NOW)
        gap = next(g for g in gaps if g.direction == "jp_to_matrox")
        self.assertEqual(gap.news_sender, "engineer@example-enduser.co.jp")
        self.assertIn("同様の事象が発生", gap.news_snippet)
        self.assertEqual(gap.unrelayed_count, 2)

    def test_matrox_gap_ages_from_the_first_chaser_not_the_last(self):
        # The Aug 24 nudge is a day old; the Aug 11 request is two weeks old.
        # A fresh reminder must not make an old gap look new.
        gaps = find_gaps(self.threads, CFG, now=NOW)
        gap = next(g for g in gaps if g.direction == "matrox_to_jp")
        self.assertEqual(gap.news_date, "2026-08-11T17:25:28Z")
        self.assertEqual(gap.latest_date, "2026-08-24T17:58:59Z")
        self.assertEqual(gap.age_days, 13)

    def test_min_age_suppresses_same_day_traffic(self):
        gaps = find_gaps(self.threads, CFG, now=NOW, min_age_days=15)
        self.assertEqual([g.direction for g in gaps], ["jp_to_matrox"])

    def test_gaps_are_sorted_oldest_first(self):
        gaps = find_gaps(self.threads, CFG, now=NOW)
        self.assertEqual(gaps, sorted(gaps, key=lambda g: g.age_days, reverse=True))

    def test_relaying_closes_the_gap(self):
        jp, en = self.threads
        en.messages.append(
            Message(
                sender="taku_yamashita@mxvideo.jp",
                to=["convertipsupport@matrox.com"],
                subject="Re: Case 00092203",
                body="The customer reproduced it on the beta and has the logs.",
                date="2026-08-09T00:00:00Z",
            )
        )
        gaps = find_gaps([jp, en], CFG, now=NOW)
        self.assertEqual([g.direction for g in gaps], ["matrox_to_jp"])

    def test_one_sided_case_produces_no_gap(self):
        gaps = find_gaps([load_thread("linkage_en_case.json")], CFG, now=NOW)
        self.assertEqual(gaps, [])

    def test_shared_po_links_threads_without_a_register_entry(self):
        jp = ThreadRef.build(
            "jp-po",
            [
                Message(
                    sender="okada@example-distributor.co.jp",
                    to=["taku_yamashita@mxvideo.jp"],
                    subject="JMGS05955 の納期について",
                    body="お客様より納期のご確認をいただいております。",
                    date="2026-08-10T00:00:00Z",
                )
            ],
        )
        en = ThreadRef.build(
            "en-po",
            [
                Message(
                    sender="taku_yamashita@mxvideo.jp",
                    to=["ltang@matrox.com"],
                    subject="NEW PO JMGS05955",
                    body="Could you confirm the lead time?",
                    date="2026-08-05T00:00:00Z",
                )
            ],
        )
        gaps = find_gaps([jp, en], CFG, now=NOW)
        self.assertEqual([g.key for g in gaps], [CaseKey("po", "JMGS05955")])

    def test_never_relayed_reports_no_prior_relay(self):
        jp = ThreadRef.build(
            "jp-new",
            [
                Message(
                    sender="okada@example-distributor.co.jp",
                    to=["taku_yamashita@mxvideo.jp"],
                    subject="JMGS09999 について",
                    body="ご確認をお願いします。",
                    date="2026-08-01T00:00:00Z",
                )
            ],
        )
        en = ThreadRef.build(
            "en-new",
            [
                Message(
                    sender="ltang@matrox.com",
                    to=["taku_yamashita@mxvideo.jp"],
                    subject="PO JMGS09999",
                    body="Please confirm.",
                    date="2026-08-02T00:00:00Z",
                )
            ],
        )
        gaps = find_gaps([jp, en], CFG, now=NOW)
        self.assertEqual(len(gaps), 2)
        self.assertTrue(all(g.last_relay_date is None for g in gaps))


if __name__ == "__main__":
    unittest.main()
