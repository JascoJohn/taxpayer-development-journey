"""E2 - leakage review of the retained targeting features about banking, credit, insurance, pensions, formal employment and
formal-sector products.

Question asked of every such feature: does OBTAINING or HOLDING the product REQUIRE a TIN in Tanzania? If so, the feature is
mechanically tied to the outcome (TIN holding) and is leakage.

Classes
  REQUIRES_TIN    a statute or official source makes a TIN compulsory for the transaction behind the feature -> excluded from the refit
  NO_REQUIREMENT  no requirement found in the sources read (the basis says which) -> kept
  UNCERTAIN       the feature mixes cases (personal vs business accounts, titles acquired by transfer, an indirect chain through a
                  registered vehicle or a trade licence) or the sources could not be read -> kept in the refit, dropped in the sensitivity fit

The judgement is made per product FAMILY (the rules below, first match wins) and applied to every retained survey column of the
family. Formal employment registered for PAYE is a legitimate predictor, not leakage: TRA observes it. It is kept by decision.

Sources were read on 2026-11-12 (read-only look-ups). What could not be read is said so in the basis; nothing here is inferred from
memory. The statutory text is the Tax Administration Act, Cap. 438 R.E. 2019 (s. 24 and the Third Schedule); later amendments were not
checked, and the 2016 and 2025 General Regulations on the TRA site could not be read (the fetch failed).
"""

import re

ACCESSED = "2026-11-12"

SOURCES = {
    "TAA": ("Tax Administration Act, Cap. 438 R.E. 2019: s. 24(2)-(3) and Third Schedule 'Transactions for which Taxpayer Identification Number is required' (read verbatim from the Ministry of Finance PDF)",
            "https://www.mof.go.tz/uploads/documents/en-1676548563-THE%20TAX%20ADMINISTRATION_ACT,%20CAP%20438.pdf"),
    "FBA": ("FB Attorneys legal update, 19 Aug 2020: each employee must have a TIN (s. 22 TAA; PAYE interim TIN)", "https://fbattorneys.co.tz/tin-mandatory-for-all-employees/"),
    "BOB": ("Bank of Baroda Tanzania, current account page: 'TIN certificate copy (for both company and signatories)'; individuals are not named in the TIN line",
            "https://bankofbaroda.co.tz/bank-account/current-deposits/current-account-from-banks"),
    "CRDBTC": ("CRDB Bank general terms and conditions for account opening and operation, July 2023 (15 pages read; no mention of a TIN)",
               "https://crdbbank.co.tz/storage/app/media/eng-crdb-bank-plc-account-opening-and-account-operation-general-tc-english-version-july-2023.pdf"),
    "NMBSAL": ("NMB salaried worker's loan page: requirements are salary slips, employment letter, staff ID (no TIN)", "https://www.nmbbank.co.tz/personal-banking/borrow/nmb-salaried-worker-s-loan"),
    "NMBSME": ("NMB SME loans page: needs a business licence or permit from the local authority in the borrower's name; no TIN named", "https://www.nmbbank.co.tz/business-banking/business-banking/sme-loans"),
    "CRDBPL": ("CRDB personal loan page: salary slips, proof of identity, employer letters (no TIN found; page partly summarised)", "https://crdbbank.co.tz/en/for-you/bank-loan/personal-loan"),
    "NSSF": ("NSSF membership page: registration by National Identification Number through a registered employer (no TIN named)", "https://www.nssf.go.tz/pages/members"),
    "PSSSF": ("PSSSF FAQs: national ID or passport, employment letter (no TIN named)", "https://www.psssf.go.tz/faqs"),
    "TIRA": ("TIRA website and FAQs: no TIN requirement for buying a policy found (the pages read do not describe the purchase documents)", "https://www.tira.go.tz/faqs"),
    "BOTMFI": ("Bank of Tanzania, licence application checklist for Tier 2 microfinance service providers (individual money lenders): a certified TIN certificate is required of the LENDER",
               "https://www.bot.go.tz/Publications/Acts,%20Regulations,%20Circulars,%20Guidelines/Procedures/en/2020033023042463.pdf"),
}
NOT_READ_NOTE = "Not checked: Bank of Tanzania KYC guidance and the TRA General Regulations (fetch failed); later amendments to the Act; individual institutions' internal policies."

REQUIRES, NONE, UNSURE = "REQUIRES_TIN", "NO_REQUIREMENT", "UNCERTAIN"

ATTITUDE_RX = re.compile(r"(?i)reason|agree|confident|comfortable|dislike|value most|heard of|understand|aware|\bwhy\b|statements|feel|prefer|trust|"
                         r"interest they charge|information about|difficult|problem|experienc|knowledge|would you|expect|important|satisf|treat")

# (family, topic, name regex (fullmatch) , class, basis, [source ids], decision note)
RULES = [
    ("vehicle ownership", "formal-sector asset", r"D6_3a__4", REQUIRES,
     "Registration of ownership or transfer of vehicles under the Road Traffic Act and licensing of motor vehicles under the Transport Licensing Act are Third Schedule transactions: the institution must require a TIN (s. 24(2)). The item is 'owns motorised transport (car, motorcycle ...) for the business'; unregistered vehicles exist, so the link is strong, not perfect.",
     ["TAA"], "excluded from the REQUIRES_TIN refit"),
    ("motor insurance", "insurance", r"ins3_1__(1|16)", UNSURE,
     "Motor insurance presupposes a registered vehicle, and registering a vehicle requires a TIN (Third Schedule); the insurance purchase itself has no TIN requirement in the sources read (TIRA pages describe no purchase documents). Indirect chain.",
     ["TAA", "TIRA"], ""),
    ("land title documents", "formal-sector asset", r"c12_[13]", UNSURE,
     "Registration of title upon transfer of ownership (Commissioner for Lands) is a Third Schedule transaction that requires a TIN; titles granted originally or held customarily do not pass through a transfer. The item mixes both.",
     ["TAA"], ""),
    ("formal employment", "formal employment", r"D2_1__1|D3_1|IncomeMain", NONE,
     "Employees must hold a TIN, issued through the employer's PAYE registration (s. 22 TAA; FB Attorneys 2020). TRA observes PAYE-registered employment in its own data, so it is a legitimate predictor, not leakage.",
     ["FBA", "TAA"], "KEPT by decision (brief E2): formal employment registered for PAYE is observable by TRA"),
    ("bank current / cheque account", "banking", r"comm8_1__1|micro8_0__1", UNSURE,
     "Company and sole-proprietor current accounts: the bank asks for a TIN certificate (Bank of Baroda). Personal accounts: no TIN found. The survey item does not separate the two.",
     ["BOB", "CRDBTC"], ""),
    ("pension / social security", "pensions", r"pens\d.*|PENSION|D2_1__7|gov_1__3|f_5_n_1__2|serv1_1__8", NONE,
     "NSSF and PSSSF register members by National ID / employer; no TIN is named. No Third Schedule entry for pensions.",
     ["NSSF", "PSSSF", "TAA"], ""),
    ("insurance", "insurance", r"ins.*|INSURANCE|serv1_1__7", NONE,
     "No TIN requirement for buying insurance found in the sources read; no Third Schedule entry for insurance.", ["TIRA", "TAA"], ""),
    ("government securities / investments", "formal-sector products", r"f_5_n_[12].*|FORM_INVESTMENTS", NONE,
     "No Third Schedule entry; no TIN requirement found for buying Treasury bills or bonds (the Bank of Tanzania / DSE account form searched asks for the National ID).", ["TAA"], ""),
    ("formal credit (bank, MFI, SACCOS, mobile)", "credit", r"cred.*|micro.*|MFI|lender.*|serv1_1__(2|4)|mob11.*|mob12.*|mob13.*|g_5_.*|g_2_.*|g_12.*|g_10.*|g_6.*|g_8.*|g_9.*", UNSURE,
     "Personal loans: no TIN named (NMB, CRDB pages). SME loans: a business licence is required (NMB, CRDB), and a trade licence is a Third Schedule transaction requiring a TIN, so business loans are tied to a TIN indirectly. Survey items do not separate personal from business borrowing. Several loan pages could not be read in full.",
     ["NMBSAL", "CRDBPL", "NMBSME", "TAA"], ""),
    ("banking", "banking", r"BANKED|comm.*|serv1_1__1|serv2_.*|serv5_.*|F4_1__1|pb2_[234]|bill2_[234]|pb4.*|pb5.*|e_5_.*|e_7_.*|D7a|OVERALL_FORMAL|OTHER_FORMAL", UNSURE,
     "Personal bank accounts: no TIN requirement found (no banking entry in the Third Schedule; CRDB general terms mention no TIN; Bank of Baroda names TIN for company accounts only). Business accounts: TIN certificate required (Bank of Baroda). The survey cannot tell them apart. Aggregates built from bank items (BANKED, OVERALL_FORMAL, OTHER_FORMAL) inherit this.",
     ["TAA", "CRDBTC", "BOB"], ""),
    ("informal / community credit and saving", "credit", r"INFORMAL.*|serv1_1__(10|12)|cmg.*|SACCO|g_1_.*|g_7|g_3.*|g_4.*|g_11.*|e_11_2_n_[12]|F4_.*|F5.*|f_3.*|f_4.*|c18_1__(3|11)", NONE,
     "Informal lenders, savings groups and attitudes to borrowing: no TIN requirement; no Third Schedule entry.", ["TAA"], ""),
    ("mobile money / payments", "formal-sector products", r"mob.*|MM|pb3.*|pay.*|bill.*|pb2_5", NONE,
     "SIM and mobile-money registration is by National ID; mobile money is not a Third Schedule transaction (merchant 'Lipa namba' terms of the operators were not read).", ["TAA"], ""),
    ("government assistance", "formal-sector products", r"gov_.*", NONE, "Social assistance payments: no TIN requirement; no Third Schedule entry.", ["TAA"], ""),
]
COMPILED = [(f, t, re.compile(n), c, b, s, d) for f, t, n, c, b, s, d in RULES]
ATTITUDE_BASIS = "Attitude, awareness or reason item: it records no product held or used, so no TIN requirement can attach to it."

TOPIC_RX = re.compile(r"(?i)\bbank|ATM|debit|credit|cheque|loan|borrow|lend|SACCO|micro ?finance|MFI|insur|pension|NSSF|PSSSF|salar|wage|formal|"
                      r"invest|treasury|bond|overdraft|mortgage|\bmobile money|\bwallet|owe\b|debt|saving")


def review(columns, labels):
    """columns: retained source column names; labels: name -> data-map label. Returns one dict per reviewed column
    (feature, label, family, topic, class, basis, source URL(s), decision)."""
    rows = []
    for c in columns:
        lab = re.sub(r"\s+", " ", labels.get(c, "")).strip()
        hit = next((r for r in COMPILED if r[2].fullmatch(c)), None)
        if hit is None and not (TOPIC_RX.search(lab) or TOPIC_RX.search(c)):
            continue
        if hit is None:
            rows.append({"feature": c, "label": lab[:160], "family": "other topic-matched item", "topic": "formal-sector products", "class": UNSURE,
                         "basis": "Matched the topic search but no family rule covers it: treated as UNCERTAIN until reviewed.", "source_url": "", "decision": ""})
            continue
        fam, topic, _, cls, basis, srcs, dec = hit
        decision = dec
        if cls != REQUIRES and fam not in ("formal employment", "vehicle ownership", "motor insurance", "land title documents") and ATTITUDE_RX.search(lab):
            cls, basis, srcs = NONE, ATTITUDE_BASIS, ["TAA"]
            decision = ""
        rows.append({"feature": c, "label": lab[:160], "family": fam, "topic": topic, "class": cls, "basis": basis,
                     "source_url": " ; ".join(SOURCES[s][1] for s in srcs), "decision": decision})
    return rows
