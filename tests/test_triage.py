"""Tests for the routing rules in :mod:`mxmail.triage`.

The cases below are the four the specification actually turns on:
Matrox writes in (EN), a customer writes in (JA), a customer writes in English
(the stated exception), and traffic that should never get a draft at all.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mxmail.triage import (  # noqa: E402
    Message,
    classify,
    counterparty_language,
    detect_language,
    domain_of,
    load_config,
    normalize_address,
    strip_quoted,
)

CFG = load_config(ROOT / "config" / "routing.toml")
SAMPLES = ROOT / "samples"


def load_thread(name: str) -> list[Message]:
    payload = json.loads((SAMPLES / name).read_text(encoding="utf-8"))
    return [Message.from_gmail(m) for m in payload["messages"]]


class AddressTests(unittest.TestCase):
    def test_normalize_strips_display_name(self):
        self.assertEqual(
            normalize_address("Taku Yamashita <Taku_Yamashita@MXVIDEO.jp>"),
            "taku_yamashita@mxvideo.jp",
        )

    def test_domain_of(self):
        self.assertEqual(domain_of("ltang@matrox.com"), "matrox.com")

    def test_matrox_side_covers_subdomains(self):
        self.assertTrue(CFG.is_matrox("someone@mail.matrox.com"))
        self.assertFalse(CFG.is_matrox("someone@notmatrox.com"))

    def test_owner_aliases(self):
        self.assertTrue(CFG.is_owner("taku_yamashita@matrox.com"))
        self.assertTrue(CFG.is_owner("Taku <taku_yamashita@mxvideo.jp>"))
        self.assertFalse(CFG.is_owner("ltang@matrox.com"))

    def test_party_lookup(self):
        party = CFG.party_for("takaaki.okada@j-material.jp")
        self.assertIsNotNone(party)
        self.assertEqual(party.kind, "distributor")


class LanguageTests(unittest.TestCase):
    def test_plain_japanese(self):
        self.assertEqual(detect_language("お世話になっております。山下です。"), "ja")

    def test_plain_english(self):
        self.assertEqual(detect_language("Hi Taku,\n\nStock is fine.\n\nLan"), "en")

    def test_english_body_quoting_japanese_is_english(self):
        body = (
            "Hi Taku-san,\n\nPlease confirm the shipment schedule.\n\nToshiko\n\n"
            "2026年8月19日 山下 卓 <taku_yamashita@mxvideo.jp>:\n"
            "> お世話になっております。\n"
            "> 発注書を受領いたしました。\n"
        )
        self.assertEqual(detect_language(body), "en")
        # Without stripping the quote the Japanese history would dominate.
        self.assertEqual(detect_language(body, ignore_quotes=False), "ja")

    def test_japanese_body_with_english_product_names(self):
        body = (
            "岡田様\n\nお世話になっております。\n"
            "X.mio3 LP SDK のドキュメントを確認いたしました。\n\n山下"
        )
        self.assertEqual(detect_language(body), "ja")

    def test_empty_body_defaults_to_english(self):
        self.assertEqual(detect_language("   "), "en")

    def test_strip_quoted_falls_back_when_everything_is_quoted(self):
        body = "> quoted only\n> more quoted"
        self.assertEqual(strip_quoted(body), body.strip())


class MatroxSideTests(unittest.TestCase):
    """Rule 1: mail from Matrox, in English."""

    def setUp(self):
        self.thread = load_thread("thread_matrox_po.json")
        self.incoming = self.thread[-1]

    def test_reply_is_english(self):
        result = classify(self.incoming, CFG, thread=self.thread)
        self.assertEqual(result.action, "draft")
        self.assertEqual(result.side, "matrox")
        self.assertEqual(result.reply_language, "en")

    def test_companion_goes_to_the_customer_in_japanese(self):
        result = classify(self.incoming, CFG, thread=self.thread)
        self.assertIsNotNone(result.companion)
        self.assertEqual(result.companion.audience, "customer")
        self.assertEqual(result.companion.language, "ja")
        self.assertEqual(result.companion.confidence, "suggested")

    def test_short_acronyms_do_not_match_fragments(self):
        # "shipping point" must not register as a "PO" signal.
        result = classify(self.incoming, CFG, thread=self.thread)
        self.assertNotIn("PO", result.companion.matched_signals)
        self.assertIn("lead time", result.companion.matched_signals)


class CustomerJapaneseTests(unittest.TestCase):
    """Rule 2: mail from a customer, in Japanese."""

    def setUp(self):
        self.message = Message(
            sender="okabe@nikkotelecom.co.jp",
            subject="X.mio5 の不具合についてご相談",
            body=(
                "山下様\n\nお世話になっております。日興テレコムの岡部でございます。\n"
                "先日納品いただいたボードで映像に乱れが出ております。\n"
                "ご確認いただけますでしょうか。\n\n岡部"
            ),
            to=["taku_yamashita@mxvideo.jp"],
            labels=["INBOX"],
        )

    def test_reply_is_japanese(self):
        result = classify(self.message, CFG)
        self.assertEqual(result.side, "external")
        self.assertEqual(result.incoming_language, "ja")
        self.assertEqual(result.reply_language, "ja")

    def test_report_to_matrox_is_english(self):
        result = classify(self.message, CFG)
        self.assertEqual(result.companion.audience, "matrox")
        self.assertEqual(result.companion.language, "en")
        self.assertEqual(result.companion.confidence, "suggested")

    def test_fault_report_without_the_word_fuguai_still_flags_a_handoff(self):
        # Real fault reports describe the symptom rather than saying 不具合,
        # and that phrasing has to reach Matrox as a companion report.
        message = Message(
            sender="dyagi@nikkotelecom.co.jp",
            subject="hp Z4G6iとMIO5の組み合わせで映像に乱れが出る件",
            body=(
                "お世話になっております。\n"
                "MIO5を入れたところ、映像に乱れが出る症状が発生しています。\n"
                "テストに使用したドライバーは 10.5.100.1781 です。\n"
                "この現象について回避方法などわかりますでしょうか？"
            ),
            to=["taku_yamashita@mxvideo.jp"],
        )
        result = classify(message, CFG)
        self.assertEqual(result.companion.confidence, "suggested")
        self.assertEqual(result.companion.audience, "matrox")
        self.assertEqual(result.companion.language, "en")

    def test_party_is_resolved(self):
        result = classify(self.message, CFG)
        self.assertIsNotNone(result.party)
        self.assertEqual(result.party.name_en, "Nikko Telecom")
        self.assertEqual(result.notes, [])


class EnglishCustomerExceptionTests(unittest.TestCase):
    """The exception: a customer writes in English, so everything stays English."""

    def setUp(self):
        self.thread = load_thread("thread_customer_en.json")
        self.incoming = self.thread[-1]

    def test_reply_and_report_are_both_english(self):
        result = classify(self.incoming, CFG, thread=self.thread)
        self.assertEqual(result.incoming_language, "en")
        self.assertEqual(result.reply_language, "en")
        self.assertEqual(result.companion.language, "en")
        self.assertTrue(result.unified_english)

    def test_matrox_mail_on_an_english_thread_keeps_the_customer_draft_english(self):
        # Same thread, but now head office is the one writing in.
        from_matrox = Message(
            sender="ltang@matrox.com",
            subject="RE: Payment for PO SAMPLE-0451",
            body="Hi Taku,\n\nThe order will ship on the 25th.\n\nThanks\nLan",
            to=["taku_yamashita@mxvideo.jp"],
        )
        thread = self.thread + [from_matrox]
        result = classify(from_matrox, CFG, thread=thread)
        self.assertEqual(result.side, "matrox")
        self.assertEqual(result.reply_language, "en")
        self.assertEqual(result.companion.audience, "customer")
        self.assertEqual(result.companion.language, "en")
        self.assertTrue(result.unified_english)

    def test_japanese_thread_keeps_the_customer_draft_japanese(self):
        thread = load_thread("thread_matrox_po.json")
        result = classify(thread[-1], CFG, thread=thread)
        self.assertFalse(result.unified_english)
        self.assertEqual(result.companion.language, "ja")

    def test_counterparty_language_ignores_matrox_and_owner(self):
        thread = load_thread("thread_matrox_po.json")
        # Newest non-Matrox, non-owner message in that thread is Japanese.
        self.assertEqual(counterparty_language(thread, CFG), "ja")


class SkipTests(unittest.TestCase):
    def test_bulk_sender(self):
        message = Message(
            sender="video@matrox.com", subject="IBC 2026", body="Newsletter"
        )
        result = classify(message, CFG)
        self.assertEqual(result.action, "skip")

    def test_noreply_localpart(self):
        message = Message(sender="no-reply@example.com", subject="Receipt", body="hi")
        self.assertEqual(classify(message, CFG).action, "skip")

    def test_private_domain(self):
        message = Message(
            sender="someone@docomo.ne.jp", subject="物件の件", body="お世話になります"
        )
        self.assertEqual(classify(message, CFG).action, "skip")

    def test_calendar_notice(self):
        message = Message(
            sender="myang@matrox.com",
            subject="Canceled: Bi Weekly Update - Japan",
            body="Microsoft Teams meeting",
        )
        self.assertEqual(classify(message, CFG).action, "skip")

    def test_own_sent_mail(self):
        message = Message(
            sender="taku_yamashita@mxvideo.jp", subject="Re: anything", body="hi"
        )
        self.assertEqual(classify(message, CFG).action, "skip")

    def test_unknown_external_domain_is_flagged_not_skipped(self):
        message = Message(
            sender="new.person@unknown-broadcaster.co.jp",
            subject="Matrox 製品のお問い合わせ",
            body="はじめまして。製品についてお伺いしたく存じます。",
        )
        result = classify(message, CFG)
        self.assertEqual(result.action, "draft")
        self.assertTrue(any("Unknown domain" in n for n in result.notes))


if __name__ == "__main__":
    unittest.main()
