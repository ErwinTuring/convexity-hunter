# Hunter Discovery Policy v0.1 Validation

## Protocol

This record validates
[`Hunter Discovery Policy v0.1`](hunter-discovery-policy-v0.1.md) through
sequential bounded Web Search batches. Each batch uses a previously unused
inclusive seven-calendar-day source-publication window, retains at most ten
source-backed provisional candidates, presents them in deterministic neutral
order, and stops before translation for explicit human selection of one ID or
`NONE`.

For every batch the human evaluates willingness to continue, event novelty,
connection novelty, credibility versus speculation, rejection reasons, and the
lane that produced any useful candidate. A candidate is not an accepted Event
Intelligence hypothesis or recommendation.

## Batch 01 — human review complete

```text
batch_id=hunter-discovery-policy-v0.1-2026-08-11-17-batch-01
window=2026-08-11..2026-08-17 inclusive
producer=bounded-web-search
candidate_count=9
selection=2026-08-14-second-order-ai-power-financing
translation=COMPLETE
```

The repository-external validator constructed the unchanged
`EventCandidateBatch` contract, enforced the canonical lane grammar, checked
all retained source dates against the declared window, verified unique IDs and
deduplication keys, and verified neutral ordering by earliest source-publication
date then `candidate_id`. Validation passed. Exact source publication
timestamps were not invented when a page exposed only a date.

| Candidate ID | Lane | Provisional underlying(s) | Source fact | Hunter interpretation | Main uncertainty | Public source(s) |
| --- | --- | --- | --- | --- | --- | --- |
| `2026-08-12-explicit-aevex-blacksea` | `EXPLICIT_CATALYST` | `AVEX` | AEVEX signed a conditional agreement to acquire BlackSea for up to $650 million, combining air, surface, and subsea autonomy. | The transaction could broaden AVEX's capability and program mix while adding financing, dilution, closing, and integration exposure. | Closing and projected program or margin benefits are not established. | [SEC-filed issuer release](https://www.sec.gov/Archives/edgar/data/2096300/000119312526346904/d139310dex991.htm) |
| `2026-08-13-explicit-bmy-iberdomide` | `EXPLICIT_CATALYST` | `BMY` | FDA granted accelerated approval to BMY's iberdomide combination for certain previously treated multiple-myeloma patients. | The named asset now has a changed launch and clinical path, widening outcomes around uptake, confirmatory evidence, safety management, and portfolio contribution. | Accelerated approval, a surrogate endpoint, boxed warning, and REMS do not establish durable uptake. | [FDA approval notice](https://www.fda.gov/drugs/resources-information-approved-drugs/fda-grants-accelerated-approval-iberdomide-daratumumab-and-hyaluronidase-fihj-and-dexamethasone) |
| `2026-08-13-explicit-rocketlab-iridium` | `EXPLICIT_CATALYST` | `IRDM`, `RKLB` | RKLB reported HSR expiration, an S-4 filing, FCC applications, and a debt/equity financing plan for its proposed IRDM acquisition. | Concrete deal milestones can change both issuers' closing and capital-structure outcome ranges. | FCC, shareholder, lender, financing, dilution, and integration outcomes remain unresolved. | [SEC-filed issuer release](https://www.sec.gov/Archives/edgar/data/1819994/000175392626001463/g085846_ex99-2.htm) |
| `2026-08-13-explicit-zoetis-screwworm-eua` | `EXPLICIT_CATALYST` | `ZTS` | FDA authorized Zoetis-sponsored Simparica TRIO to treat screwworm in dogs and puppies while describing current U.S. detections as geographically limited. | Emergency veterinary demand and outbreak-response relevance could widen ZTS outcomes, conditional on outbreak scale. | FDA says most U.S. dogs are at low risk; the EUA is temporary and does not cover prevention. | [FDA EUA announcement](https://www.fda.gov/news-events/press-announcements/fda-issues-emergency-use-authorization-drug-treat-new-world-screwworm-dogs-and-puppies) |
| `2026-08-13-narrative-dynatrace-ai-observability` | `NARRATIVE_BELIEF_SHIFT` | `DT` | Dynatrace agreed to acquire AI evaluation and observability provider Arize for $915 million in cash and stock. | The purchase is provisional evidence that enterprise observability may be extending from infrastructure telemetry to continuous model and agent evaluation. | One unclosed acquisition and acquirer claims do not establish category durability or adoption. | [Dynatrace release](https://www.dynatrace.com/news/press-release/dynatrace-to-acquire-arize/) |
| `2026-08-14-narrative-core-scientific-power` | `NARRATIVE_BELIEF_SHIFT` | `CORZ` | CORZ completed a $444 million acquisition securing about 440 MW of operating grid-connected capacity and said most revenue now comes from high-density colocation. | The completed acquisition is provisional evidence of a business-identity shift from bitcoin mining toward power-backed AI colocation. | Capacity ownership does not prove conversion, customer demand, financing, or returns. | [CORZ 8-K exhibit](https://investors.corescientific.com/sec-filings/all-sec-filings/content/0001839341-26-000018/polarisclosingvf20260814.htm) |
| `2026-08-14-second-order-ai-power-financing` | `SECOND_ORDER_TRANSMISSION` | `NVDA` | Texas described developer power/water/infrastructure obligations; OpenAI later announced an approximately 8 IT-GW Ohio project using NVIDIA compute, with NVIDIA investing $1.5 billion in SB Energy and providing initial-build credit support. | AI-campus execution may transmit to NVDA through capital and credit exposure as well as chip demand, binding its outcomes to power, permitting, financing, and counterparty execution. | Project scale and timing, permits, financing, and NVIDIA's exact credit-risk scope remain unresolved. | [Texas Governor](https://gov.texas.gov/news/post/governor-abbott-announces-stack-infrastructure-anthropic-and-nightpeak-energy-commit-to-comply-with-his-data-center-standards), [OpenAI project announcement](https://openai.com/index/openai-joins-ports-pike-project/) |
| `2026-08-17-explicit-intuitive-machines-satellites` | `EXPLICIT_CATALYST` | `LUNR` | LUNR said an undisclosed customer authorized work to begin on a multi-satellite communications program with anticipated value above $600 million. | The authorization could widen outcomes through backlog conversion, manufacturing, customer concentration, and schedule execution. | Customer, contract structure, funding, and revenue timing are undisclosed; anticipated value is not recognized revenue. | [LUNR issuer release](https://intuitivemachines.gcs-web.com/news-releases/news-release-details/intuitive-machines-selected-multi-satellite-communications) |
| `2026-08-17-narrative-uhs-talkspace-continuum` | `NARRATIVE_BELIEF_SHIFT` | `UHS` | UHS completed its TALK acquisition, combining virtual behavioral care with facilities, outpatient sites, and payer/employer channels. | The combination is provisional evidence of a shift from standalone telehealth toward integrated virtual-to-facility behavioral-care pathways. | Integration, provider and payer retention, patient adoption, and claimed synergies are unproven. | [UHS release](https://uhs.com/news/universal-health-services-inc-completes-acquisition-of-talkspace-inc/) |

### Human review record

```text
selection=2026-08-14-second-order-ai-power-financing
willingness_to_continue=YES
event_new_to_human=YES
connection_new_to_human=YES
impact_or_transmission_credibility=MIXED
useful_lane=SECOND_ORDER_TRANSMISSION
```

The human rejected the other rows because most were direct first-order company
catalysts or single-company narrative changes. The selected item was worth
continuing specifically to test whether Hunter could join multiple public facts
into a second-order distribution-change hypothesis that had not been
pre-specified.

### Candidate translation and Event Intelligence result

Supplemental primary-source research added NVIDIA's own PORTS-Pike release and
exposure explanation plus an SEC filing establishing the exact listed equity
identity. NVIDIA confirms a USD 1.5 billion SB Energy investment, exclusive
NVIDIA compute at the site, and credit support for the initial 4.25 IT-GW. It
also limits that support to defined portions of lease and power payments plus a
specified residual-value commitment rather than the whole site or all tenant
obligations, with phased activation as capacity enters service during
2028--2030.

The exact translation retained five sources, six fact/interpretation statements,
and one `NVDA` / `XNAS` / equity / USD
`BIDIRECTIONAL_EXPANSION` hypothesis. Existing Event Intelligence assessment
returned:

```text
status=INCOMPLETE
issue_codes=(incomplete_expected_window,)
```

This is the intended fail-closed result. The sources describe calendar years
and a 20-year lease but do not provide an exact date suitable for the required
inclusive expected-window end. No day was inferred merely to obtain acceptance.
All other acceptance semantics were complete. No market-data call, Futu
exercise, or Direct Entry work ran.

## Batch 02 — human review complete

```text
batch_id=hunter-discovery-policy-v0.1-2026-08-04-10-batch-02
window=2026-08-04..2026-08-10 inclusive
producer=bounded-web-search
candidate_count=6
selection=2026-08-10-narrative-ai-compute-finance-asset-class
translation=COMPLETE
```

The repository-external validator constructed the unchanged
`EventCandidateBatch` contract, checked every retained source date against the
declared window, validated the canonical lane grammar, and verified neutral
ordering by earliest source-publication date then `candidate_id`. Each event
date is an explicit, source-stated event or announcement date; it is not copied
implicitly from the publication date. A seventh provisional Energy Vault item
was excluded before presentation because an in-window primary source could not
be verified. No score, ranking, recommendation, expected window, or downstream
submission was produced.

| Candidate ID | Lane | Provisional underlying(s) | Source fact | Hunter interpretation | Main uncertainty | Public source(s) |
| --- | --- | --- | --- | --- | --- | --- |
| `2026-08-04-explicit-lucid-operational-reset` | `EXPLICIT_CATALYST` | `LCID` | Lucid launched an operational reset focused on cash, cost, customer, quality, and organization, including production restraint intended to reduce inventory. | The reset may widen LCID outcomes around liquidity preservation, execution, inventory conversion, program timing, and future financing. | Stated cash-flow opportunities are not realized savings; production restraint can have more than one explanation. | [Lucid release](https://ir.lucidmotors.com/news-releases/news-release-details/lucid-announces-operational-reset-and-second-quarter-2026/) |
| `2026-08-05-explicit-takeda-orzeyful` | `EXPLICIT_CATALYST` | `TAK` | FDA approved Takeda's ORZEYFUL for adults with narcolepsy type 1; U.S. availability remains subject to DEA scheduling. | A first-in-class approval changes TAK's launch and orexin-franchise path, with dispersion around scheduling, uptake, safety, and class expansion. | Takeda says the approval is not expected to materially affect its current full-year forecast; scheduling, adoption, and economics remain unresolved. | [FDA](https://www.fda.gov/news-events/press-announcements/fda-approves-first-drug-treat-full-range-narcolepsy-type-1-symptoms), [Takeda](https://www.takeda.com/newsroom/newsreleases/2026/orzeyful-approved-narcolepsy/) |
| `2026-08-06-explicit-replimune-tudriqev` | `EXPLICIT_CATALYST` | `REPL` | FDA granted accelerated approval to Replimune's TUDRIQEV with nivolumab for specified anti-PD-1-refractory advanced melanoma patients. | The approval moves REPL into commercial execution while preserving a wide outcome range around uptake, confirmatory evidence, safety, and continued approval. | Approval rests on response rate and duration in a single-arm setting and requires post-approval verification of benefit. | [FDA](https://www.fda.gov/news-events/press-announcements/fda-approves-new-engineered-viral-immunotherapy-patients-treatment-resistant-advanced-melanoma), [Replimune](https://ir.replimune.com/news-releases/news-release-details/replimune-announces-fda-accelerated-approval-tudriqevtm) |
| `2026-08-07-explicit-crh-antitrust-remedy` | `EXPLICIT_CATALYST` | `CRH` | DOJ and Tennessee required two asphalt-plant divestitures under a proposed settlement for CRH's Standard Construction acquisition. | The remedy changes the retained local asset footprint and closing path, with outcomes tied to divestiture and judicial execution. | The remedy is proposed and geographically narrow; broader financial materiality is not established. | [U.S. DOJ](https://www.justice.gov/opa/pr/justice-department-partners-tennessee-attorney-general-preserve-competition-asphalt-western) |
| `2026-08-07-explicit-elanco-screwworm-eua` | `EXPLICIT_CATALYST` | `ELAN` | FDA authorized Elanco's CLiK Extra for emergency prevention of New World screwworm infestations across specified livestock and wildlife species. | The authorization may change ELAN's outbreak-response relevance and product demand, conditional on the scale and duration of the emergency. | The authorization is temporary and limited; outbreak scale and realized utilization are unknown. | [FDA authorization summary](https://www.fda.gov/media/194124/download?attachment=), [Elanco](https://investor.elanco.com/news-releases/news-release-details/elancos-cliktm-extra-dicyclanil-topical-suspension-wound-spray) |
| `2026-08-10-narrative-ai-compute-finance-asset-class` | `NARRATIVE_BELIEF_SHIFT` | `NVDA` | NVIDIA announced memorandums with six financial institutions for independent compute-financing platforms intended to mobilize more than USD 500 billion over time. | The proposal is evidence that AI compute is being framed as a financeable infrastructure asset, potentially linking NVDA demand to underwriting and capital-market conditions. | Memorandums and mobilization aims are not funded commitments; economics, deployment dates, and compute residual values are unproven. The theme overlaps Batch 01 but is a distinct event. | [NVIDIA](https://nvidianews.nvidia.com/news/nvidia-partners-with-apollo-blackrock-blackstone-brookfield-goldman-sachs-and-kkr-to-establish-ai-compute-infrastructure-financing-platforms-to-mobilize-over-500-billion-of-third-party-capital) |

### Human review record

```text
selection=2026-08-10-narrative-ai-compute-finance-asset-class
willingness_to_continue=YES
event_new_to_human=YES
connection_new_to_human=YES
impact_or_transmission_credibility=MIXED
useful_lane=NARRATIVE_BELIEF_SHIFT
```

The other five rows were rejected as mostly first-order issuer regulation,
approval, transaction, or operating events. Although the selected item is
thematically related to Batch 01, its distinct facts independently point toward
AI compute being financialized or treated as an infrastructure asset. The
selection therefore tests whether `NARRATIVE_BELIEF_SHIFT` can repeatedly
surface the same structural change through separate public developments.

### Candidate translation and Event Intelligence result

Supplemental primary-source research retained NVIDIA's dated explanation,
Apollo's participant-side announcement, and an SEC filing establishing the
exact listed `NVDA` identity. NVIDIA states that the more-than-USD-500-billion
amount is an aggregate capital-mobilization objective rather than NVIDIA
revenue, one fund, or a commitment to one customer. It says institutions will
independently underwrite demand, utilization, cash flow, and residual value,
and that NVIDIA may provide project-specific residual-value support of up to
25 percent in some cases.

The exact translation retained four sources, six fact/interpretation
statements, and one `NVDA` / `XNAS` / equity / USD
`BIDIRECTIONAL_EXPANSION` hypothesis. Existing Event Intelligence assessment
returned:

```text
status=INCOMPLETE
issue_codes=(incomplete_expected_window,)
```

This is fail-closed. The sources say only that capital may be mobilized “over
time” and disclose no exact platform-deployment or impact-window end date. No
date was inferred. No market-data call, Futu exercise, or Direct Entry work
ran.

## Batch 03 — human review complete

```text
batch_id=hunter-discovery-policy-v0.1-2026-07-28-08-03-batch-03
window=2026-07-28..2026-08-03 inclusive
producer=bounded-web-search
candidate_count=8
selection=2026-07-28-narrative-ionq-skywater-vertical-integration
translation=COMPLETE
```

The repository-external validator constructed the unchanged contract, checked
all source dates against the exact window, retained explicit source-stated
event dates, validated the lane grammar, and verified deterministic neutral
ordering. This batch contains five explicit catalysts and three narrative or
belief-shift interpretations. It contains no second-order row because the
bounded evidence did not support one without manufacturing a transmission
path. The GPUS row deliberately has no authoritative source ID: it remains an
issuer-supplied distributed discovery lead whose limitation is explicit.

| Candidate ID | Lane | Provisional underlying(s) | Source fact | Hunter interpretation | Main uncertainty | Public source(s) |
| --- | --- | --- | --- | --- | --- | --- |
| `2026-07-28-explicit-drs-raft-acquisition` | `EXPLICIT_CATALYST` | `DRS` | Leonardo DRS signed a USD 450 million all-cash agreement to acquire defense mission-software, data-fusion, and AI company Raft. | The transaction may widen DRS outcomes through software mix, national-security customer exposure, financing, closing, and integration. | Closing and integration remain conditional; price does not prove future awards, revenue, or margins. | [SEC-filed issuer release](https://www.sec.gov/Archives/edgar/data/1833756/000183375626000034/exhibit991-raftacquisition.htm) |
| `2026-07-28-narrative-ionq-skywater-vertical-integration` | `NARRATIVE_BELIEF_SHIFT` | `IONQ`, `SKYT` | IonQ received final regulatory approval to complete its acquisition of U.S. semiconductor foundry SkyWater. | The combination is provisional evidence that quantum firms may pursue foundry vertical integration instead of relying only on external fabrication. | Regulatory approval does not prove integration, manufacturing acceleration, scale, or economics; one deal does not establish an industry shift. | [IonQ](https://investors.ionq.com/news/news-details/2026/IonQ-Receives-Regulatory-Approval-to-Complete-Acquisition-of-SkyWater-Technology/default.aspx) |
| `2026-07-29-explicit-teleflex-ezplaz` | `EXPLICIT_CATALYST` | `TFX` | FDA licensed Teleflex subsidiary Vascular Solutions' EZPLAZ, the first U.S.-licensed freeze-dried plasma product, for specified adult transfusion use. | The license changes TFX's emergency-medicine product path around military, ambulance, remote-care, manufacturing, and adoption execution. | The indication is limited; launch timing, production, pricing, procurement, and adoption are not established. | [FDA](https://www.fda.gov/news-events/press-announcements/fda-licenses-first-ever-freeze-dried-plasma-product-us), [Teleflex](https://investors.teleflex.com/news/news-details/2026/Teleflex-Announces-FDA-BLA-Approval-of-EZPLAZ-Freeze-Dried-Plasma/default.aspx) |
| `2026-07-30-narrative-gpus-bitcoin-ai-financing` | `NARRATIVE_BELIEF_SHIFT` | `GPUS` | An issuer-supplied distributed release said Hyperscale Data would deploy Bitcoin holdings and establish Bitcoin-backed credit to fund its Michigan AI data-center campus. | This is provisional evidence of a shift from treating Bitcoin primarily as treasury reserve toward collateral and capital for physical AI infrastructure. | No in-window regulator filing was retained; borrowing terms, collateral risk, deployment, and customers are incomplete, and one small issuer does not establish a broader trend. | [Issuer-supplied distributed release](https://www.prnewswire.com/news-releases/hyperscale-data-repurposes-bitcoin-treasury-strategy-to-accelerate-development-of-michigan-ai-data-center-302838654.html) |
| `2026-07-30-narrative-supermicro-rack-deployment` | `NARRATIVE_BELIEF_SHIFT` | `SMCI` | Supermicro introduced pre-engineered AI racks intended for same-day integration and shorter time-to-online. | The launch is provisional evidence that AI-infrastructure competition may be shifting toward rack integration, cooling, deployment speed, and operational time-to-online. | Product claims lack customer deployment, independent benchmarking, adoption, margin, and revenue evidence; one launch does not prove an industry bottleneck shift. | [Supermicro](https://www.supermicro.com/en/pressreleases/supermicro-expands-dcbbs-precision-engineered-ai-rack-series-accelerate-deployment) |
| `2026-07-31-explicit-mckinley-space-eyes` | `EXPLICIT_CATALYST` | `MKLY` | McKinley Acquisition and private Space-Eyes signed a conditional business-combination agreement with a stated USD 638 million pro forma equity value. | The proposed combination may widen MKLY outcomes through counter-drone and geospatial-AI exposure together with PIPE, redemption, closing, and commercialization risks. | Closing, listing, PIPE funding, approval, forecasts, and valuation remain conditional. | [SEC-filed joint release](https://www.sec.gov/Archives/edgar/data/2067592/000121390026085668/ea029966201ex99-1.htm) |
| `2026-08-03-explicit-brady-honeywell-pss` | `EXPLICIT_CATALYST` | `BRC`, `HON` | Brady completed its USD 1.4 billion acquisition of Honeywell's Productivity Solutions and Services business using cash and debt. | Completion changes BRC's scale, debt, product mix, and integration exposure while HON transferred the named business. | Expected contribution and synergies are forward-looking; integration, retention, debt effects, and HON materiality remain unresolved. | [SEC-filed Brady release](https://www.sec.gov/Archives/edgar/data/746598/000074659826000034/exhibit991-pressreleasex20.htm) |
| `2026-08-03-explicit-integer-kkr-take-private` | `EXPLICIT_CATALYST` | `ITGR`, `KKR` | Integer signed an agreement for KKR-managed funds to acquire all shares for USD 127 each in a transaction valued around USD 5.7 billion. | The deal creates a bounded merger outcome for ITGR and deployment, financing, regulatory, and portfolio exposure for KKR. | Financing, approvals, closing, termination, and materiality to KKR remain unresolved. | [SEC-filed joint release](https://www.sec.gov/Archives/edgar/data/1114483/000095010326011683/dp251107_ex9901.htm) |

### Human review record

```text
selection=2026-07-28-narrative-ionq-skywater-vertical-integration
willingness_to_continue=YES
event_new_to_human=YES
connection_new_to_human=YES
impact_or_transmission_credibility=MIXED
useful_lane=NARRATIVE_BELIEF_SHIFT
```

The other rows were rejected mostly as direct issuer catalysts. The SMCI and
GPUS narratives were novel but had thinner evidence. The selected row combined
a clear, verifiable transaction with the less-obvious question of whether a
quantum-computing company is beginning to control manufacturing through
vertical integration, making it the stronger test of the narrative lane.

### Candidate translation and Event Intelligence result

Supplemental SEC evidence established that the acquisition completed on July
31, SkyWater became a wholly owned IonQ subsidiary, and `IONQ` common stock is
listed on `XNYS`. The SEC-filed completion release says SkyWater will continue
serving merchant-foundry customers and explicitly classifies roadmap
acceleration and vertical-integration benefits as forward-looking. The
translation therefore did not treat ownership as proof of captive capacity,
realized manufacturing improvement, or an industry-wide trend.

The exact translation retained three sources, six fact/interpretation
statements, and one `IONQ` / `XNYS` / equity / USD
`BIDIRECTIONAL_EXPANSION` hypothesis. Existing Event Intelligence assessment
returned:

```text
status=INCOMPLETE
issue_codes=(incomplete_expected_window,)
```

This is fail-closed. Acquisition completion provides a precise start for the
integration hypothesis but no exact end date for its expected distribution
impact. No end date was inferred. No market-data call, Futu exercise, or Direct
Entry work ran.
