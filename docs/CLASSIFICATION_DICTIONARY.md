# KhmerHire Classification Dictionary

- Task ID: GH-ISSUE-13
- Dictionary version: 1.1
- Status: Human-approved WorkBuddy classification corrections recorded
- UI language order: Khmer, English, Chinese

## 1. Dictionary contract

Each canonical concept has:

- stable code;
- Khmer label;
- English label;
- Chinese label;
- approved aliases;
- parent code;
- matching behavior;
- reviewer status;
- version.

Canonical codes never change when a display label is translated or renamed.
Aliases are many-to-one and must not create a new occupation unless a reviewer
approves the distinction.

## 2. Job-family taxonomy

| Code | Khmer | English | Chinese |
|---|---|---|---|
| HOSPITALITY | សណ្ឋាគារ និងភោជនីយដ្ឋាន | Hospitality and food service | 酒店与餐饮 |
| RETAIL_SALES | លក់រាយ និងការលក់ | Retail and sales | 零售与销售 |
| CONSTRUCTION_TRADES | សំណង់ និងជំនាញបច្ចេកទេស | Construction and skilled trades | 建筑与技术工种 |
| MANUFACTURING | ផលិតកម្ម និងរោងចក្រ | Manufacturing and factory work | 制造与工厂 |
| LOGISTICS_TRANSPORT | ដឹកជញ្ជូន និងភស្តុភារ | Logistics and transport | 物流与运输 |
| OFFICE_ADMIN | រដ្ឋបាលការិយាល័យ | Office administration | 办公室行政 |
| FINANCE_ACCOUNTING | ហិរញ្ញវត្ថុ និងគណនេយ្យ | Finance and accounting | 财务与会计 |
| IT_DIGITAL | ព័ត៌មានវិទ្យា និងឌីជីថល | IT and digital | 信息技术与数字 |
| HEALTHCARE_CARE | សុខាភិបាល និងការថែទាំ | Healthcare and care | 医疗与护理 |
| EDUCATION_TRAINING | អប់រំ និងបណ្តុះបណ្តាល | Education and training | 教育与培训 |
| AGRICULTURE | កសិកម្ម | Agriculture | 农业 |
| SECURITY_FACILITIES | សន្តិសុខ និងថែទាំអគារ | Security and facilities | 安保与设施 |
| BEAUTY_WELLNESS | សម្រស់ និងសុខុមាលភាព | Beauty and wellness | 美容与健康 |
| OTHER_REVIEW | ផ្សេងៗ | Other | 其他 |

WorkBuddy must verify Khmer wording, local usage and whether any family should
be split or merged before implementation.

## 3. Employment and work-mode values

| Code | Khmer | English | Chinese |
|---|---|---|---|
| FULL_TIME | ពេញម៉ោង | Full-time | 全职 |
| PART_TIME | ក្រៅម៉ោង | Part-time | 兼职 |
| CONTRACT | កិច្ចសន្យាការងារ | Contract | 合同 |
| INTERNSHIP | កម្មសិក្សា | Internship | 实习 |
| SEASONAL | តាមរដូវកាល | Seasonal | 季节性 |
| ONSITE | នៅទីតាំងការងារ | Onsite | 到岗 |
| HYBRID | ចម្រុះ | Hybrid | 混合办公 |
| REMOTE | ពីចម្ងាយ | Remote | 远程 |

## 4. Language values and evidence

| Code | Khmer | English | Chinese |
|---|---|---|---|
| KM | ភាសាខ្មែរ | Khmer | 高棉语 |
| EN | ភាសាអង់គ្លេស | English | 英语 |
| ZH | ភាសាចិន | Chinese | 中文 |

### Proficiency and evidence labels

| Code | Khmer | English | Chinese |
|---|---|---|---|
| BASIC | កម្រិតមូលដ្ឋាន | Basic | 基础 |
| WORKING | កម្រិតប្រើប្រាស់ការងារ | Working | 工作可用 |
| PROFICIENT | កម្រិតជំនាញ | Proficient | 熟练 |
| EXPERT | កម្រិតជំនាញខ្ពស់ | Expert | 精通 |
| SELF_REPORTED | ប្រកាសដោយខ្លួនឯង | Self-reported | 自报 |
| DOCUMENTED | មានឯកសារផ្ទៀងផ្ទាត់ | Documented | 有证明 |
| ASSESSED | បានធ្វើតេស្ត | Assessed | 已测评 |
| EMPLOYER_CONFIRMED | បញ្ជាក់ដោយនិយោជក | Employer confirmed | 雇主确认 |

The language used by the app is never an evidence value.

## 5. Skill normalization examples

| Canonical code | Khmer label | English label | Chinese label | Approved alias examples |
|---|---|---|---|---|
| SKILL_CUSTOMER_SERVICE | សេវាកម្មអតិថិជន | Customer service | 客户服务 | cashier service, front desk service |
| SKILL_SALES | ការលក់ | Sales | 销售 | sales representative, sales promoter |
| SKILL_EXCEL | Microsoft Excel | Microsoft Excel | Microsoft Excel | spreadsheet, Excel |
| SKILL_DRIVING | បើកបរ | Driving | 驾驶 | driver, delivery driving |
| SKILL_WELDING | ផ្សារ | Welding | 焊接 | welder |
| SKILL_COOKING | ចម្អិនម្ហូប | Cooking | 烹饪 | kitchen, cook |
| SKILL_ACCOUNTING | គណនេយ្យ | Accounting | 会计 | bookkeeping, accountant |
| SKILL_PROGRAMMING | សរសេរកម្មវិធី | Programming | 编程 | software development, coding |

Dictionary v1.1 also approves these reviewed aliases: MANUFACTURING → រោងចក្រកាត់ដេរ and កាត់ដេរ; IT_DIGITAL → បច្ចេកវិទ្យា; REMOTE → ធ្វើការពីផ្ទះ. PART_TIME has an explicit anti-alias: ម៉ោងបន្ថែម (overtime) MUST NOT map to PART_TIME. Ambiguous phrases remain REVIEW_REQUIRED and cannot satisfy a hard requirement automatically.

These examples are seed entries only. Expand to at least 30 skills across the top five job families before production ranking goes live; additions still require the normal source/reviewer/version metadata.

## 6. Reason-code dictionary

| Code | Meaning | Display behavior |
|---|---|---|
| SKILL_MATCH | Canonical skill overlap | Show matched skill and source |
| ROLE_MATCH | Occupation/title fit | Show job family and role concept |
| EXPERIENCE_MATCH | Relevant experience fit | Show months or evidence band |
| LOCATION_MATCH | Location/commute fit | Show coarse location only |
| LANGUAGE_MATCH | Required language fit | Show language and evidence level |
| SCHEDULE_MATCH | Schedule compatibility | Show matching schedule fields |
| SALARY_COMPATIBLE | Salary ranges overlap | Show currency and period |
| MISSING_REQUIRED_DATA | Important data unknown | Ask for the missing field |
| HARD_REQUIREMENT_FAILED | Explicit requirement not met | Show the requirement and stop eligibility |
| TRANSLATION_UNCERTAIN | Translation or mapping uncertain | Show review flag and lower confidence |
| STALE_RECORD | Record may be outdated | Show retrieved/published date |
| SOURCE_CONFLICT | Permitted sources disagree | Show needs-review state |

## 7. Classification statuses

- AUTO_ACCEPT: canonical mapping above the approved confidence threshold.
- REVIEW_REQUIRED: ambiguous Khmer phrase, low confidence or source conflict.
- REJECTED: prohibited, invalid, expired or unusable source record.
- USER_CORRECTED: candidate or employer corrected a mapping; retain audit trail.

## 8. Normalization rules

1. Match aliases to canonical codes only within the correct job-family context.
2. Do not infer a skill from an employer brand, photo or person's name.
3. Do not infer language proficiency from interface language or script.
4. Keep both original text and canonical code.
5. Preserve negation: "no experience required" is not an experience
   requirement, and "not required to speak Chinese" is not a Chinese-language
   requirement.
6. Preserve requirement strength: required, preferred and optional are
   different values.
7. If a phrase maps to multiple codes, return REVIEW_REQUIRED.
8. Every new alias needs a source example, language, reviewer and dictionary
   version.

## 9. Review checklist

WorkBuddy should verify:

- Khmer labels sound natural to Cambodia job seekers and employers;
- English and Chinese labels preserve the canonical meaning;
- aliases do not merge distinct occupations;
- negation and requirement strength survive normalization;
- language labels are not confused with UI locale;
- hard-requirement concepts have exact-equivalence markers;
- synthetic examples cover the high-volume job families.
