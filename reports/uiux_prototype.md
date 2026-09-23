# UI/UX Prototype Validation (km / en / zh) — JOB-001 (GH-ISSUE-13)

- Reviewer: WorkBuddy (trilingual UI reviewer / UI-UX acceptance)
- Input: PRD §3 + §6, CLASSIFICATION_DICTIONARY §6/§7, RECRUITMENT_RULES §7/§8
- Verdict: **APPROVED WITH BINDING UI STRING SET** — PRD §6 requirements are implementable; ChatGPT must ship the strings below in dictionary v1.1 and follow the Khmer typography rules.

## 1. State and action labels (binding v1 set)

| Concept | Khmer | English | Chinese |
|---|---|---|---|
| eligible | សមស្រប | Eligible | 匹配合格 |
| needs_review | ត្រូវពិនិត្យ | Needs review | 待审核 |
| ineligible | មិនសមស្រប | Not eligible | 不合格 |
| View reasons | មើលមូលហេតុ | View reasons | 查看匹配原因 |
| Score display | ពិន្ទុ ៧៨/១០០ (or 78/100) | Score 78/100 | 匹配度 78/100 |
| Machine translated | បានបកប្រែដោយស្វ័យប្រវត្តិ | Machine translated | 机器翻译 |
| Stale warning | ព័ត៌មានអាចមិនទាន់ពេលវេលា | May be outdated | 信息可能已过期 |
| Missing data hint | បំពេញ {field} ដើម្បីបង្កើនភាពជឿជាក់ | Add {field} to improve confidence | 补充{字段}可提高可信度 |
| Sponsored (non-ranking) | ផ្សព្វផ្សាយ | Sponsored | 推广 |

Use Western digits for scores (Khmer numerals optional as a display setting; never mix in one view).

## 2. Binding UX rules from PRD §6 (confirmed implementable)

1. Khmer default rendering — ✅ with typography rules in §3 below.
2. "View reasons" on every score — ✅; reasons render as an ordered list of reason codes with localized text; a result without reasons must not render (RULES §8).
3. Language switch without re-ranking — ✅; locale switch must not refetch scores, only re-render localized fields.
4. Three states visually distinct — ✅ use color + icon + label, never color alone (accessibility).
5. Missing-data hints — ✅ must name the exact field key from missing_information.
6. Paid status never adjacent to score/confidence — ✅ sponsored items render with the ផ្សព្វផ្សាយ badge and a fixed visual slot, outside the organic list.
7. No exact address / private contact / protected attributes in UI — ✅ location renders province/district level only.

## 3. Khmer typography requirements (blocking for frontend)

1. Font: Noto Sans Khmer (or Battambang) first in stack; include Khmer OS fallbacks (Khmer OS Battambang / Khmer OS Content) — many Cambodian users only have these locally.
2. line-height ≥ 1.7 for Khmer text; never apply `letter-spacing` or `text-transform` to Khmer; disable justification (Khmer has no spaces — justification creates broken clusters).
3. Mixed Khmer-Latin-Chinese lines: isolate Latin runs (`<span lang>`) to prevent font fallback corruption; ZWNJ handling tested.
4. Chinese fallback font (system PingFang/Microsoft YaHei/Noto Sans SC) — no CJK glyph gaps.
5. Mobile-first: target 360px width; Khmer clusters wrap whole-syllable (test word-wrap with long occupational labels).
6. Low-end Android + slow 3G profile: match list must render without web fonts blocking first paint (font-display: swap).

## 4. Prototype walkthrough scenarios (for acceptance later)

Each scenario must pass in all three locales with identical ordering:
1. Job card with score 78 + reasons list + missing salary field hint.
2. Candidate card for employer: eligible/needs_review/ineligible trio.
3. Language switcher km→en→zh: ordering, reasons, and states unchanged.
4. Sponsored job injected: badge visible, position outside organic ranking, no score inflation.
5. Machine-translated title: marker shown; original available on tap.
6. Stale job: stale warning shown; not described as current.
7. Translation correction flow: reviewer + taxonomy version recorded (PRD §6.6).

## 5. Handoff to ChatGPT

Component list for implementation: MatchCard, ReasonList, StateBadge, LanguageSwitcher, MissingDataHint, SponsoredSlot, StaleBanner, TranslationMarker, ScoreBadge. All strings via i18n keys, km as default locale, English fallback, zh third; no hardcoded strings in components.

— WorkBuddy, trilingual UI/UX validation
