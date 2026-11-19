# Sign-off sheet (Block E3.6)

Every register row that is ASSUMPTION or UNKNOWN and NOT yet signed off, for a review session. Source: `docs/assumptions_register.csv` and the +/-20% sensitivity runs (`docs/assumption_sensitivity.json`). Recommendations are the analyst's; the decision is the owner's. The same rows are in `docs/signoff_sheet.csv`.

## Counts

| Area | Rows to sign | feed a published claim or dashboard value | model internals | ASSUMPTION | UNKNOWN | SIGN as is | REVISE | RETIRE |
|---|---|---|---|---|---|---|---|---|
| Morale model | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Agent model | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Tier | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Digital twin | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Stage economics | 3 | 1 | 2 | 3 | 0 | 3 | 0 | 0 |
| Macro | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Other | 3 | 0 | 3 | 3 | 0 | 3 | 0 | 0 |
| **Total** | **6** | **1** | **5** | **6** | **0** | **6** | **0** | **0** |

Sensitivity column: 'yes' = a +/-20% change moves at least one published value of the function by more than 5% (relative); 'no' = it does not; 'no effect' = the published values do not move at all (the constant is inactive in the published runs). Within each area the rows that feed a published claim come first, and those that move a published value by more than 5% come first among them.

## Morale model

No unsigned row feeds a published claim in this area.

## Agent model

No unsigned row feeds a published claim in this area.

## Tier

No unsigned row feeds a published claim in this area.

## Digital twin

No unsigned row feeds a published claim in this area.

## Stage economics

| key | value | class | rationale or source | feeds | moves a published value >5%? | recommendation |
|---|---|---|---|---|---|---|
| `stage.income_basis_bracket` | {"central": "hbs_receipts_owners", "high": "ilfs_gross", "lo | ASSUMPTION | Pass 6B-1. Revenue per registrant of Active and Enterprise: CENTRAL = HBS 2017/18 receipts of owners with receipts in the reference month (Pass 6D variant V3); BRACKET HIGH = ILFS 2024 gross receipts of owners (V1); BRACKET LOW = HBS all owners with zeros kept | Table 5.1 central and bracket columns, Figure 5.3, taxable capacity, targeting and dashboard Active/Enterprise pages | not computed | **SIGN as is**: Design choice; no data bear on it. Sensitivity (+/-20%): n/a (DATA read from a file). |

## Macro

No unsigned row feeds a published claim in this area.

## Other

No unsigned row feeds a published claim in this area.

## Model internals: document only

These rows feed no published claim and no dashboard value; they are listed so that the register is complete.

| area | key | value | class | what it is | recommendation |
|---|---|---|---|---|---|
| Stage economics | `stage.formal_step_if_not_asked` | "no_formal_step" | ASSUMPTION | Pass 6B-1, stage mapping B. The formal step of a business owner is D6_4a == 'Yes' (business registered with a government authority). A respondent who was not as | **SIGN as is** |
| Stage economics | `stage.workers_unpriced` | true | ASSUMPTION | Pass 6B-1, stage mapping B. Workers 25-44 (non-owners aged 25-44: wage, casual, farm and dependent adults) stay in the population but carry no revenue lever, no | **SIGN as is** |
| Other | `hbs.cpi_uprating` | "wdi_fp_cpi_totl_mean_of_survey_years_to | ASSUMPTION | Pass 6B-1. HBS 2017/18 turnover is uprated to 2024 prices with the World Bank WDI consumer price index (FP.CPI.TOTL, Tanzania): CPI(2024) / mean of CPI(2017) an | **SIGN as is** |
| Other | `hbs.owners_with_receipts_central` | true | ASSUMPTION | Pass 6B-1. The central HBS case restricts owners to those with receipts from sources 1-4 in the reference month (about 42% of owners; 58% report none). Owners w | **SIGN as is** |
| Other | `hbs.receipts_annualisation` | "last_month_receipts_x_months_operated" | ASSUMPTION | Pass 6B-1. Annual turnover = last month's receipts (HBS Form I S10C1, sources 1-4: sales, resale, construction, services) x months the business operated in the  | **SIGN as is** |
