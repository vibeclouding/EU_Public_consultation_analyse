# EU Tobacco Regulation Consultation Analysis (Hungarian Dataset)

This repository contains an automated text analysis and classification code for processing Hungarian-language public feedback submitted to the European Commission regarding revisions to tobacco control regulations (Tobacco Advertising / Tobacco Products Directives).

---

## Project Overview

The primary goal of this script (`HU_elemzes_v4`) is to load raw public consultation submissions, extract Hungarian-language entries, and perform rule-based natural language classification to determine:
1. **Who is speaking?** (Stakeholder grouping based on strict self-identification or platform metadata)
2. **What stance do they take?** (Pro-restriction, anti-restriction, differentiated, or mixed)
3. **What specific arguments, products, and policy tools are mentioned?** (Drill-down dimensions D1–D7)

---

## Methodology & Logic

Because the target feedback dataset consists of Hungarian text, the rule-based classification uses **Hungarian regular expressions (Regex)** tailored to specific linguistic constructs, idioms, and industry framing.

### 1. Stakeholder Classification (Groups C1–C5)
Entries are classified into one of five mutually exclusive stakeholder categories:

| Code | Stakeholder Group | Classification Logic |
| :--- | :--- | :--- |
| **C1** | **Tobacco Grower / Producer** | Strict first-person self-identification (`"mint gyártó"`, `"dohányt termesztünk"`) or metadata (`COMPANY` / `BUSINESS_ASSOCIATION`). |
| **C2** | **Retailer (Tobacconist)** | First-person shop/retailer identification (`"a boltom"`, `"trafikosként"`, `"vevőim"`). |
| **C3** | **Consumer / Individual** | **Default / Remainder group.** Contains sub-flags for self-identified consumers (`"dohányzom"`, `"vape-et szívok"`), short comments (≤10 words), and industry-aligned argument patterns. |
| **C4** | **Civil Organization / NGO** | NGO metadata or organizational phrasing (`"egyesületünk nevében"`, `"érdekképviseletként"`). |
| **C5** | **Healthcare Expert** | Medical/academic metadata or professional identification (`"orvosként"`, `"betegeim"`, `"kórházban dolgozom"`). |

> **Contextual Disambiguation:** Ambiguous terms like *"gazdaságunk"* (our farm vs. national economy) or *"vállalkozásunk"* (our business) are only credited to C1/C2 if specific role-related keywords appear within a $\pm 200$-character window.

---

### 2. Stance Detection
Stance is evaluated at two levels:
* **Level T1 (Explicit Stance):** Direct expression of agreement, disagreement, or request for differentiated regulation (`"ellenzem"`, `"támogatom"`, `"kockázatarányos"`).
* **Level T2 (Argument Family Pattern):** Used when explicit phrasing is absent. Evaluates the ratio of **Industry Argument Families** (black market, economic harm, adult choice, harm reduction) vs. **EU/Public Health Argument Families** (youth protection, public health, marketing bans, environment).

Classification labels:
* `MELLETTE (szigorítás-párti)` — Pro-restriction
* `ELLENE (szigorítás-ellenes)` — Anti-restriction
* `DIFFERENCIÁLT (kockázatarányos)` — Differentiated / Risk-proportionate
* `VEGYES / ambivalens` — Mixed / Ambivalent
* `NEM ÉRTELMEZHETŐ` — Not applicable / Neutral

---

### 3. Drill-Down Dimensions (D1–D7)

* **D1 (Regulatory Instruments):** Tracks mentions of specific policy tools (flavor bans, plain packaging, disposable vapes, nicotine pouches, heated tobacco, online advertising, taxation, sales restrictions).
* **D2 (Defended Product Category):** Identifies which specific product is being defended in anti-restriction feedback.
* **D3 (Industry Signature Claims):** Detects standardized talking points (e.g., *"95% less harmful"*, *"Swedish model"*, *"prohibition fails"*, *"black market shift"*, *"cessation tool"*).
* **D4 (Domestic Regulatory Framing):** Captures local context references (Hungarian national tobacco shop monopoly *"trafik"*, excise taxes, local laws).
* **D5 (Youth Protection Appropriation):** Flags anti-restriction comments that utilize youth protection arguments.
* **D6 (Narrative Register):** Differentiates personal stories (E/1 experience) from structured, impersonal policy essays.
* **D7 (Temporal Mobilization):** Identifies peak submission dates to measure coordinated campaign timing.

---

## Input Data Requirements

The script expects a JSON or JSON Lines file named `eu_TAD_revision_hozzaszolasok_900.json` in one of the following paths:
* `/content/eu_TAD_revision_hozzaszolasok_900.json` (Google Colab)
* `/mnt/user-data/uploads/eu_TAD_revision_hozzaszolasok_900.json`
* `./eu_TAD_revision_hozzaszolasok_900.json` (Local directory)

### Required Data Fields:
* `feedback`: The textual content of the public comment.
* `language`: Two-letter language code (`HU` is extracted).
* `dateFeedback`: Timestamp of submission (`YYYY/MM/DD HH:MM:SS`).
* `userType`: Portal metadata (e.g., `COMPANY`, `NGO`, `CITIZEN`).

---

## Execution & Output

### Prerequisites
Install required Python libraries:
```bash
pip install pandas openpyxl
