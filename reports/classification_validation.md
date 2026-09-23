# Khmer Taxonomy & Classification Validation — JOB-001 (GH-ISSUE-13)

- Reviewer: WorkBuddy (classification validation engineer, Khmer reviewer role)
- Input: docs/CLASSIFICATION_DICTIONARY.md v1.0
- Verdict: **CONDITIONALLY APPROVED** — labels are usable; 6 label fixes and 1 missing table must land in dictionary v1.1 before any alias satisfies a hard requirement.

## 1. Job-family Khmer labels (14/14 reviewed)

| Code | Khmer | Verdict |
|---|---|---|
| HOSPITALITY | សណ្ឋាគារ និងភោជនីយដ្ឋាន | ✅ natural |
| RETAIL_SALES | លក់រាយ និងការលក់ | ✅ natural |
| CONSTRUCTION_TRADES | សំណង់ និងជំនាញបច្ចេកទេស | ✅ natural |
| MANUFACTURING | ផលិតកម្ម និងរោងចក្រ | ✅ natural; add alias រោងចក្រកាត់ដេរ (garment factory) in v1.1 |
| LOGISTICS_TRANSPORT | ដឹកជញ្ជូន និងភស្តុភារ | ✅ natural |
| OFFICE_ADMIN | រដ្ឋបាលការិយាល័យ | ✅ natural |
| FINANCE_ACCOUNTING | ហិរញ្ញវត្ថុ និងគណនេយ្យ | ✅ natural |
| IT_DIGITAL | ព័ត៌មានវិទ្យា និងឌីជីថល | ✅ acceptable; add alias បច្ចេកវិទ្យា (technology) — very common in postings |
| HEALTHCARE_CARE | សុខាភិបាល និងការថែទាំ | ✅ natural |
| EDUCATION_TRAINING | អប់រំ និងបណ្តុះបណ្តាល | ✅ natural |
| AGRICULTURE | កសិកម្ម | ✅ natural |
| SECURITY_FACILITIES | សន្តិសុខ និងថែទាំអគារ | ✅ natural |
| BEAUTY_WELLNESS | សម្រស់ និងសុខុមាលភាព | ✅ natural |
| OTHER_REVIEW | ផ្សេងទៀត ត្រូវពិនិត្យ | ⚠️ functional but awkward as a user-visible label; display ផ្សេងៗ (Others) and keep needs_review internal only |

## 2. Employment / work-mode labels — 2 ambiguity risks

| Code | Khmer | Verdict |
|---|---|---|
| FULL_TIME | ពេញម៉ោង | ✅ standard |
| PART_TIME | ក្រៅម៉ោង | ⚠️ **ambiguity risk**: ក្រៅម៉ោง is also read as "after hours / extra hours". Add anti-alias rule: must NOT map ម៉ោងបន្ថែម (overtime) to PART_TIME. Recommend testing the label with local reviewers; fallback to displaying "Part-time" alongside Khmer. |
| CONTRACT | កិច្ចសន្យា | ⚠️ generic word for "agreement/contract". Recommend label កិច្ចសន្យាការងារ (employment contract) or display "Contract · កិច្ចសន្យា" |
| INTERNSHIP | កម្មសិក្សា | ✅ |
| SEASONAL | តាមរដូវកាល | ✅ |
| ONSITE | នៅទីតាំងការងារ | ✅ |
| HYBRID | ចម្រុះ | ✅ |
| REMOTE | ពីចម្ងាយ | ✅ add alias ធ្វើការពីផ្ទះ (work from home) |

## 3. Missing table (blocking): proficiency values are unlabeled

Dictionary §4 defines BASIC / WORKING / PROFICIENT / EXPERT and evidence types but gives **no Khmer or Chinese labels** for them. The UI cannot render these in Khmer. Required in v1.1 (proposed):

| Code | Khmer (proposed) | Chinese |
|---|---|---|
| BASIC | កម្រិតមូលដ្ឋាន | 基础 |
| WORKING | កម្រិតប្រើប្រាស់ការងារ | 工作可用 |
| PROFICIENT | កម្រិតជំនាញ | 熟练 |
| EXPERT | កម្រិតជំនាញខ្ពស់ | 精通 |
| SELF_REPORTED | ប្រកាសដោយខ្លួនឯង | 自报 |
| DOCUMENTED | មានឯកសារផ្ទៀងផ្ទាត់ | 有证明 |
| ASSESSED | បានធ្វើតេស្ត | 已测评 |
| EMPLOYER_CONFIRMED | បញ្ជាក់ដោយនិយោជក | 雇主确认 |

## 4. Skill seeds (8/8 reviewed)

SKILL_CUSTOMER_SERVICE / SALES / EXCEL / DRIVING / WELDING / COOKING / ACCOUNTING / PROGRAMMING — Khmer labels natural (ផ្សារ welding ✅, ចម្អិនម្ហូប cooking ✅, សរសេរកម្មវិធី programming ✅). Seed scope is too small for launch; minimum 30 skills across the top 5 families before ranking goes live. Add high-frequency aliases: រោងបាយ (kitchen staff), លក់ក្នុងហាង (in-shop sales), សួស្តីម៉ៅការ not needed — keep list data-driven from permitted sources.

## 5. Normalization rules validation

- Negation preservation (RULES: "no experience required" ≠ experience requirement) — ✅ critical and correctly specified; must be fixture-tested in Khmer ("មិនទាមទារបទពិសោធន៍").
- Requirement strength (required/preferred/optional) — ✅.
- Multi-meaning Khmer phrase → REVIEW_REQUIRED — ✅ correct behavior; never auto-select.
- No inference from brand/photo/name, no proficiency from script — ✅ both are the two most common bad heuristics; correctly banned.
- Language labels vs UI locale separation — ✅ (dictionary explicitly states UI language is never evidence).

## 6. Reviewer decision

Dictionary v1.0 = **REVIEW_REQUIRED overall** (not REJECTED): no wrong concepts, but the PART_TIME/CONTRACT ambiguities and the missing proficiency label table must be fixed in v1.1 before any of these entries can satisfy a **hard requirement**. Soft usage (ranking hints only) may proceed during implementation.

Required for v1.1:
1. proficiency + evidence label table (§3 above),
2. PART_TIME anti-alias (overtime) + CONTRACT label fix,
3. aliases: រោងចក្រកាត់ដេរ, បច្ចេកវិទ្យា, ធ្វើការពីផ្ទះ, កាត់ដេរ,
4. OTHER_REVIEW display label ផ្សេងៗ,
5. skill seed expansion plan (≥30 skills).

— WorkBuddy, Khmer classification reviewer
