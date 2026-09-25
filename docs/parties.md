# 関係者一覧

`taku_yamashita@mxvideo.jp` の受信箱に出てくる会社・本社担当と、その呼び方・Cc の慣行をまとめたもの。
下書きを書く前に、相手の欄を一度読む。

**この一覧に書かないこと**: 顧客・取引先の個人名、メールアドレス、電話番号
（[CLAUDE.md](../CLAUDE.md) の作業ルール）。個人の連絡先は Notion の CRM 台帳とメールボックスで引く。
会社ドメインは書いてよい。機械判定用のドメイン表は [config/routing.toml](../config/routing.toml) の `[[parties]]`
で、この文書と同じ会社を載せる。片方だけ直さない。

## 自分の差出人アドレス

| アドレス | 使いどころ |
|---|---|
| taku_yamashita@mxvideo.jp | **既定**。顧客・パートナー・本社宛はすべてこれ |
| tyamashi@matrox.com | 本社の社内アドレス。JM やソニーからここに届くことがある。返信は mxvideo.jp でよい |
| taku_yamashita@madokatech.co.jp | MADOKA / Sansan の名刺アドレス。ソニーの古いスレッドはここ宛に届く |
| mmhgf8314@gmail.com | 受信箱の実体。差出人切替を忘れるとここから出てしまう。**送信には使わない** |

`create_draft` は差出人を選べないので、下書きを報告するときは「mxvideo.jp から送る」と毎回書く。
署名は「Matrox・山下」。

## Matrox 本社（モントリオール、JST −13 時間）

英語。ファーストネームで呼ぶ。顧客向けの日本語メールで触れるときは「アジア営業統括の Mingkai Yang」のように役職を添える。

| 名前 | 役割 | 関わる案件 |
|---|---|---|
| Mingkai | アジア営業統括。日本の営業責任者 | 見積依頼（Lan に発行を指示）、Salesforce、パートナー戦略。顧客スレッドのほぼ全部に Cc |
| Franc | OEM 製品側の責任者 | ソニーメディカル（X.mio、AVIO2）、NEC ケースのエスカレーション、サイバネット価格協議 |
| Lan | 見積書（Quotation）の発行 | Mingkai の指示で作成。Franc の不在時の連絡先 |
| Dan、Wayne | 展示会デモ機材の計画 | InterBEE 2026 の JM ブース展示（機材凍結 10/16） |
| Kevin、Sandy | ConvertIP サポート | Case 00092203（NEC）など。ケースシステムからのメールは本文が HTML 側にしか入らない |
| Marwan、Anosh | ORIGIN | NTV の NMOS 問題、AWS の InterBEE 構成、ソニーの DSH 質問 |
| Katia | 貸出・SLG | REQ（貸出依頼）、90 日ローン、ライセンス返却 |
| Chantal、Jason | 法務 | NDA |
| Kim | マーケティング | 製品コピー、展示会の卓上サイン |
| Monica | 出張手配 | 11 月の来日のホテルなど |
| Donald | Pixotope 関連の照会 | LE5／LE6 の採用状況を尋ねてきた |

## 日本側のパートナー

| 会社 | ドメイン | 関係 | 呼び方・Cc の慣行 |
|---|---|---|---|
| ジャパンマテリアル株式会社（JM） | j-material.jp | 販売代理店。InterBEE は JM ブース（ホール 5、N9-4）に Matrox が同居。貸出機の在庫を持つ。ヤマハのスイッチ SWX3220-30TCs も保有 | 対外は「ジャパンマテリアル様」。Matrox 担当営業とは内部連絡で「さん」付け。ウェザーニューズ・アクワイア・サイバネットなど JM 経由の案件はこの担当が窓口 |
| ゴルタ（golter.jp） | golter.jp | 技術パートナー。バイリンガル。NTV・NEC・日興通信の技術対応、ORIGIN の LOCE セットアップ | 連絡は LINE が中心。対外メールでは「ホディノット」、内部では Andrew。顧客スレッドの Cc に入れる |
| GlobalM | globalm.media | ORIGIN をクラウド（OCI）で動かすパートナー。IBC のブースに NHK・ネクシオンを招いた | 英語。担当 2 名を Cc で揃える。hello@ はニュースレターなので無視 |
| 株式会社ネクシオン | nexion.co.jp | 放送向け SI。IBC で GlobalM ブースを訪問 | 日本語。ネクシオン側 3 名、ゴルタ、GlobalM 2 名を Cc。会議ありきにせず、日本側で手伝えることを伝える方針 |

## 顧客・見込み客（会社単位）

| 会社 | 表記 | ドメイン | 今の案件 | Cc の慣行・注意 |
|---|---|---|---|---|
| 三友株式会社 | **三友株式会社**。「三友商事」ではない | mitomo.co.jp | InterBEE で Pixotope ＋ ST 2110 展示。DSX LE5／LE6、ConvertIP ×2、ST 2110 スイッチの貸出相談 | ゴルタ、JM を Cc。スイッチは JM 在庫または ヤマハに相談 |
| 株式会社朋栄 | **FOR-A**（「4A」不可） | for-a.co.jp（返信は mpeg.co.jp から届くこともある） | IMPULSE 向け X.mio5 12G／DSX LE5 12G の検討。FA-1616 との JPEG XS 互換性検証（10 月後半に借用）。ConvertIP の PTP GM 切替ショック問題 | Mingkai、ゴルタ、JM、朋栄側 3 名を Cc。InterBEE で JPEG XS はフィーチャーしない |
| ヤマハ株式会社 | ヤマハ | music.yamaha.com | ネットワークスイッチ。InterBEE 協業（ヤマハブースで Matrox 2110、JM ブースでヤマハスイッチ）。判断は販売会社 YMJ。Case 00109445（PTP／ST 2022-7） | 先方は Confidential 付きで送ってくる。ヤマハ側 7 名程度、Mingkai、ゴルタ、JM を Cc |
| 日興通信株式会社 | 日興通信（ブランドは NIXUS） | nikkotelecom.co.jp | Web テロップの HTML 出力を ORIGIN で扱う検証（LOCE）。InterBEE 展示を検討中 | JM、ゴルタ、日興側 4 名を Cc。添付はダウンロードサイト経由で届く |
| ソニー株式会社（メディカル事業） | ソニー、ソニーメディカル | sony.com | 次世代 NUCLeUS。X.mio5／X.mio6、JPEG XS、AVIO2 ×4 の評価（REQ #12675）、ConvertIP DSH の Gateway Mode | 技術窓口と評価担当の 2 名。ゴルタ、JM、Mingkai、Marwan、Franc を Cc。本社向けに英語の要約を別送する。11 月に Mingkai 来日予定 |
| ソニー株式会社（放送機器側） | ソニー | sony.com | 8 月に打合せ。詳細は CRM 台帳 | メディカルとは別スレッド・別担当 |
| 日本電気株式会社 | NEC | nec.com（関連: nesic.com、solnet.ne.jp、erg-ventures.co.jp） | Case 00092203（ConvertIP CIP-DSS SDI-OUT 中断、TBS 統合 FB）、Case 00145453。PCAP 採取 | JM が窓口、ゴルタが技術。NEC 側は多人数 Cc |
| 日本テレビ放送網 | NTV、日本テレビ | ntv.co.jp（関連: ntv-wands.co.jp） | ORIGIN 導入。NMOS レシーバー問題（本社対応中） | 主担当はゴルタ。本人と LINE で調整し、様子見の方針（9/24） |
| NHK | NHK | nhk.or.jp | IBC 後のフォロー（GlobalM 経由の ORIGIN／クラウド）。ORIGIN の見込み客は Salesforce で担当割当済 | 部署ごとに別スレッド。GlobalM 2 名、ゴルタを Cc することが多い |
| グラスバレー | GV、Grass Valley | grassvalley.com | OPP-0021643（1 式）。購買は GV カナダ経由、モントリオールから出荷 | 日本担当から引き合いが来る。見積は Lan が発行 |
| ティアック株式会社 | TEAC | teac.jp | WHX Dubai 2026 の名刺交換から。3 月にオンライン紹介、4 月 ITEM 訪問。打合せの日程調整中 | 上長と国内営業課長、Mingkai を Cc |
| アマゾン ウェブ サービス ジャパン | AWS | amazon.co.jp | IBC で ORIGIN に関心。InterBEE で ST 2110 → Direct Connect → ORIGIN の構成。Inter BEE MoIP と関係 | 本社側は Marwan。ゴルタ・JM の MoIP 調整と重なるので、返信前に本人が確認する |
| 株式会社トラフィック・シム | トラフィック・シム | trafficsim.co.jp | CRM 台帳参照 | |
| スカパーJSAT 株式会社 | スカパーJSAT | sptvjsat.com | CRM 台帳参照 | |
| H&M Software | H&M Software | h-and-m-software.com | CRM 台帳参照 | |

### JM 経由の案件先（直接のメールはない）

| 案件先 | 内容 |
|---|---|
| ウェザーニューズ | OPP-0021784。前回と同じ構成のリピート |
| アクワイア（テレビ東京向け） | OPP-0019136。新規、5 台の単発案件 |
| サイバネット／オリンパス EndoBrain | 価格協議。Matrox（Mingkai・Franc）× JM の Teams 会議 |

## 展示会・企画

| 名称 | 時期・場所 | メモ |
|---|---|---|
| InterBEE 2026 | 11/18〜20、幕張メッセ | Matrox は JM ブース（ホール 5、N9-4）。パートナーブース候補: 三友、AWS、日興通信、ソニー、FOR-A、ヤマハ、Broad Design |
| Inter BEE MoIP | InterBEE 内の共同企画 | ConvertIP は Matrox から借用の方向。ゴルタ・JM が関与 |
| IBC 2026 | 9/11〜14、RAI Amsterdam（Hall 7、7.B15） | 終了。日本からの参加なし。現地は Mingkai |
| ITEM | 4 月 | TEAC ブース訪問 |
| WHX Dubai 2026 | 2 月 | TEAC との名刺交換 |
| NAB Show 2026 | 4 月 | ヤマハへ ConvertIP をハンドキャリー |

## 呼び方の規則

- 日本語メールの宛名は「会社名＋役職なし＋様」。本文で他社に触れるときも「様」（例: ジャパンマテリアル様、三友株式会社様）。
- JM の担当営業は内部メールでは「さん」。顧客向けメールでは「ジャパンマテリアル様」に戻す。
- 本社担当はファーストネーム。日本語メールでは「本社 ORIGIN 担当の Marwan」のように役割を添える。
- ゴルタは対外メールで「ホディノット」、内部で Andrew。
- 社名の正式表記が分からないときは、相手の署名をそのまま写す。推測で「商事」「株式会社」を補わない。
