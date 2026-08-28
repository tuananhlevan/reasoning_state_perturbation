You are given:

1. A figure, chart, table, or data visualization.
2. A natural-language statement intended to be true based on that figure.

Your task is to generate exactly two claims: one entailed claim that is fully supported by the figure and aligned with the original statement, and exactly one counterfactual claim that directly contradicts the generated entailed claim and is decisively contradicted by a fact directly visible in the figure.

For the counterfactual, it may be rewritten freely at the surface level — wording, grammar, syntax, sentence structure, and vocabulary are all unrestricted. However, exactly one independently falsifiable semantic proposition may differ from the original. All surface edits must serve that single semantic change and must not introduce any additional falsifiable claim. The entailed claim should also be propositionally aligned with the original statement and can be rewritten at the surface level, but must remain entirely true based on the figure.

## Surface edits versus semantic pivots

These two levels must be treated separately:

**Surface edits** (unrestricted): changes to wording, phrasing, grammar, sentence structure, vocabulary, or style. Any number of surface edits is allowed.

**Semantic pivots** (exactly one): a change to an independently falsifiable proposition — a fact, comparison, ranking, trend, value, category, scope, or relationship that can be checked against the figure. Only one semantic pivot is permitted.

A counterfactual may differ substantially from the original in surface form while still containing exactly one semantic pivot. Do not confuse surface variety with semantic change.

## Priority order

When rules appear to conflict, follow this priority order:

1. The counterfactual must be false because of evidence directly visible in the figure.
2. The entailed claim must be true and fully supported by evidence directly visible in the figure.
3. The counterfactual claim must directly contradict the generated entailed claim.
4. Both claims must remain propositionally aligned with the original statement.
5. The counterfactual must change only one independently falsifiable, figure-verifiable semantic aspect.
6. Both claims must preserve all non-figure context and assumptions unless grammatical changes are necessary.
7. Among valid candidates, prefer the most plausible, subtle, and natural counterfactual.
8. Difficulty must reflect only the minimum visual reasoning required to disprove the counterfactual claim.

## Evidence-bound interpretation

Separate the original statement into two parts:

### Figure-verifiable content

Content that can be checked directly from the visualization, including:

* values;
* comparisons;
* rankings;
* trends;
* categories or subgroups;
* time periods;
* proportions, shares, rates, or counts;
* uncertainty intervals;
* baselines;
* aggregation levels;
* missing values;
* relationships across panels, axes, or series;
* quantifiers such as "most," "largest," "only," "consistently," or "on average."

### Non-figure content

Content that is not explicitly represented in the visualization, including:

* definitions;
* background knowledge;
* domain interpretation;
* causal explanations;
* contextual descriptions;
* terminology;
* methodological assumptions;
* claims about sampling, representativeness, or data collection.

Evaluate and modify only the figure-verifiable content.

Preserve non-figure content and ignore whether it is independently true, false, properly defined, or fully supported.

The counterfactual must be false because of visible evidence in the figure, not because of outside knowledge, an unstated definition, a technical convention, or an inferred assumption. The entailed claim must similarly rely only on visible evidence.

## Propositional alignment

The generated claims do not need to preserve the original wording or sentence structure.

However, they must preserve the original statement's general:

* subject;
* measure or outcome;
* population or category scope;
* time frame, unless time is the single modified dimension;
* comparison or interpretive focus;
* non-figure context.

The counterfactual should express substantially the same underlying proposition as the original while changing exactly one figure-verifiable semantic aspect. The entailed claim should express the same underlying proposition without changing its truth value.

After removing the altered figure-verifiable component, the original, the entailed claim, and the counterfactual should communicate essentially the same remaining proposition.

Do not replace the original claim with an unrelated false statement about another visible part of the figure.

Mandatory rule:

* Both generated claims must refer to the same primary subject and primary measure as the original statement. Do not pivot to a different element, series, or panel of the figure even if that element is easier to contradict decisively.

## Core objective

Create a false claim by changing one consequential, figure-verifiable semantic dimension while preserving the original proposition's overall focus and interpretation.

The changed aspect must be directly and decisively contradicted by the figure.

The counterfactual should remain plausible after a quick reading. Detecting the contradiction should require inspecting the visualization rather than relying only on wording.

## Acceptable figure-verifiable changes

You may alter one primary semantic dimension explicitly represented in the figure, such as:

* category, subgroup, series, or population;
* displayed time period or reference point;
* direction or magnitude of a trend;
* comparison baseline;
* count, share, rate, percentage, level, rank, or cumulative value;
* quantifier scope;
* whether a pattern applies to all observations or only selected observations;
* aggregation or normalization;
* uncertainty intervals;
* missing-value status;
* the relationship between displayed measures, panels, axes, or series.

Surface-level edits — wording, grammar, sentence structure, vocabulary — are unrestricted and may be as extensive as needed to produce a natural, plausible counterfactual.

Do not introduce a second independently falsifiable factual alteration, even through rephrasing or restructuring.

## Handling partially supported statements

The original statement does not need to be fully entailed word for word.

It is sufficient that it contains at least one clear proposition that can be verified from the figure.

When the statement mixes visible evidence with contextual or interpretive language:

1. identify the directly verifiable core;
2. preserve the unverifiable context;
3. modify only one directly verifiable semantic aspect;
4. explain the contradiction using only visible evidence.

Do not reject the input merely because some definitions, interpretations, or contextual details are absent from the figure.

## Visual certainty

Use only contradictions supported with reasonable visual certainty.

Do not rely on:

* tiny or ambiguous visual differences;
* insignificant rounding discrepancies;
* exact values when the figure permits only approximate reading;
* uncertain ordering caused by overlapping marks;
* comparisons that are unresolved because of overlapping uncertainty intervals;
* unreadable labels or values;
* hidden calculations that cannot be reconstructed from displayed information.

When uncertainty intervals are displayed, do not claim that one group is definitively higher or lower unless the visualization itself establishes that relationship.

## Content that must not be used as the contradiction

Do not create the falsehood by changing or disputing:

* a definition not written in the figure;
* the meaning of a technical term not explained in the figure;
* outside facts or domain knowledge;
* causal interpretation unless causation is explicitly represented;
* contextual wording that the figure neither confirms nor denies;
* assumptions about methodology, sampling, or representativeness unless explicitly shown;
* an unstated denominator, baseline, or population;
* an ambiguous detail that the figure does not resolve;
* a claim that is merely unsupported rather than visibly contradicted.

When a phrase is not directly represented in the figure, preserve it and do not use it as the source of contradiction.

## Claim construction requirements

The entailed claim must:

* be fluent and contextually appropriate;
* remain propositionally aligned with the original;
* be strictly true based on the figure;
* preserve non-figure context.

The counterfactual claim must:

* be fluent and contextually appropriate;
* remain propositionally aligned with the original;
* change exactly one primary figure-verifiable semantic dimension;
* use only categories, measures, periods, and relationships shown in the figure;
* conflict with at least one clearly identifiable visual fact;
* directly contradict the generated entailed claim and be incompatible with the original figure-verifiable proposition under the same reasonable interpretation;
* preserve non-figure context;
* remain plausible enough that a shallow system could overlook the error.

Surface rephrasing is unrestricted. The generated claims may differ substantially from the original in wording, grammar, and sentence structure. Among valid candidates for the counterfactual that achieve the same single semantic pivot, prefer the most natural and plausible rephrasing, not the one most similar to the original wording.

## Prohibited strategies

Do not:

* merely append new, false specific details to the original claim. The counterfactual must logically contradict the generated entailed claim (i.e., they cannot both be true simultaneously). If the original claim is vague, you must change that specific proposition to something mutually exclusive, rather than just adding a false constraint;
* insert explicit negation such as "not," "never," or "did not";
* create the falsehood solely through an obvious antonym substitution;
* reverse an elementary comparison when one immediate lookup reveals the error;
* invent an arbitrary or implausible number;
* introduce a second independently falsifiable semantic alteration, even through rephrasing or restructuring;
* introduce a category, measure, period, or variable absent from the figure;
* switch to an unrelated proposition about another part of the visualization;
* rely on outside knowledge;
* challenge wording that the figure cannot verify;
* convert a merely unsupported statement into the counterfactual;
* exploit an ambiguity that the figure does not resolve;
* rely on insignificant rounding differences.

Directional changes such as "increased" versus "decreased" are allowed only when detecting the contradiction also requires resolving a displayed period, baseline, subgroup, measure, or related visual distinction.

## Internal verification

Before answering, internally complete the following checks:

1. **Verifiable-core check**
   Identify the exact proposition in the original statement that can be checked directly from the figure.

2. **Alignment check**
   Confirm that the counterfactual preserves the same subject, measure, scope, and interpretive focus, except for the single modified semantic dimension. Confirm that the entailed claim also preserves these aspects while remaining strictly true.

3. **Preservation check**
   Leave definitions, context, and non-visual assumptions unchanged except where grammatical adjustment is necessary.

4. **Contradiction check**
   Identify the exact visible value, comparison, trend, category, interval, or relationship that makes the counterfactual false.

5. **Evidence-only check**
   Confirm that no outside knowledge, unstated definition, or hidden assumption is needed.

6. **Mutual-exclusivity check**
   Confirm that the entailed and counterfactual figure-verifiable propositions are strictly mutually exclusive logical statements (i.e., they directly contradict each other). The counterfactual cannot simply be the entailed statement with a new, false specific detail appended to it.

7. **Single-pivot check**
   List every semantic claim in the counterfactual. Confirm that exactly one differs from the original, regardless of how many surface-level edits were made. If rephrasing has unintentionally changed the meaning of a second clause, revise before outputting.

8. **Surface-vs-semantic check**
   Identify all surface-level changes made to the original wording. Confirm that none of them introduce a second independently falsifiable proposition. Surface variety is acceptable; semantic variety is not.

9. **Nontriviality check**
   Confirm that the contradiction is not based only on explicit negation, an obvious antonym, or an arbitrary number.

10. **Visual-certainty check**
    Confirm that the figure resolves the contradiction clearly enough to support a decisive judgment.

11. **Difficulty-calibration check**
    Assign difficulty according to the minimum visual and semantic reasoning needed to disprove the claim.

## Difficulty-rating rubric

Rate the counterfactual according to the minimum reasoning required to identify the contradiction.

Do not base the rating on technical terminology, writing fluency, subject-matter complexity, surface dissimilarity from the original, or information outside the figure.

### Easy

Use **Easy** when one direct lookup or one immediately visible comparison disproves the claim.

Examples:

* checking one bar, point, cell, label, or legend entry;
* identifying a clearly incorrect category or period;
* reading one displayed value;
* noticing an obvious ranking or direction.

Mandatory rule:

* If one direct visual lookup is sufficient, the rating must be Easy.

### Medium

Use **Medium** when the reader must resolve one non-obvious visual distinction and inspect no more than two closely related figure elements.

Examples:

* distinguishing count from share;
* distinguishing level from change;
* identifying the correct baseline or subgroup;
* comparing two displayed values;
* interpreting a legend, axis, denominator, or time reference.

Two values used in one direct pairwise comparison normally count as one comparison operation and should usually be rated Medium at most.

Mandatory rule:

* If one semantic distinction and no more than two observations are sufficient, the rating cannot exceed Medium.

### Hard

Use **Hard** only when disproving the claim requires integrating at least two distinct pieces of visual evidence.

Examples:

* comparing several groups or periods;
* combining evidence from separate panels or series;
* distinguishing cumulative from period-specific values;
* evaluating a quantifier across multiple observations;
* combining a displayed denominator with a displayed rate or share.

Hard requires more than one simple pairwise comparison.

Mandatory rule:

* At least two distinct visual facts or reasoning operations must be combined.

### Very hard

Use **Very hard** only when all of the following are true:

1. The counterfactual remains strongly aligned with the original proposition.
2. The contradiction lies in a latent but explicitly displayed relationship.
3. At least three relevant visual facts must be combined, or two complex displayed dimensions must be jointly resolved.
4. No single value, label, or pairwise comparison reveals the error.
5. The claim remains plausible after a quick inspection.
6. The figure decisively contradicts the claim once the relevant evidence is integrated.

Do not assign Very hard because the statement contains specialized terminology, outside context, or extensive surface rephrasing.

Mandatory rule:

* Every Very hard condition must be satisfied.
* When uncertain between two ratings, choose the lower rating.

## Failure cases

Decline only when no decisive figure-grounded counterfactual can be constructed.

### No figure-verifiable proposition

Return:

Original claim:
[Copy the input exactly.]

Entailed claim:
Cannot generate a figure-grounded entailed claim.

Counterfactual claim:
Cannot generate a figure-grounded counterfactual.

Why it is false:
The statement contains no claim that can be directly verified or contradicted using the displayed figure.

Reasoning trap:
Insufficient figure-grounded evidence.

Difficulty check:
No valid contradiction can be constructed without relying on information outside the figure.

Difficulty rating:
Not applicable

### Ambiguous or unreadable visual evidence

Return:

Original claim:
[Copy the input exactly.]

Entailed claim:
Cannot generate a decisive figure-grounded entailed claim.

Counterfactual claim:
Cannot generate a decisive figure-grounded counterfactual.

Why it is false:
The relevant visual evidence is too ambiguous, approximate, or unreadable to establish a decisive contradiction.

Reasoning trap:
Insufficient visual certainty.

Difficulty check:
A contradiction would require assumptions or precision not supported by the displayed figure.

Difficulty rating:
Not applicable

## Output format

Return your response as a valid JSON object matching this exact schema. Do not include markdown formatting or extra text outside the JSON.

{
  "internal_verification": "[Briefly execute the 7th step of your internal check: list the intended semantic pivot and confirm no other verifiable facts are altered.]",
  "original_claim": "[Copy the supported statement verbatim, preserving wording and punctuation.]",
  "entailed_claim": "[Write one true claim that is fully entailed by the figure and propositionally aligned with the original statement. Surface rephrasing is allowed, but the underlying semantics must remain true.]",
  "counterfactual_claim": "[Write one false but propositionally aligned claim that directly contradicts the generated entailed claim. MANDATORY: You must completely rewrite the sentence structure and vocabulary of the surrounding text based on your rephrasing plan. Free and extensive surface rephrasing is allowed, but exactly one semantic proposition may differ from the original.]",
  "why_it_is_false": "[State the single altered semantic proposition, then identify the exact visible evidence incompatible with it. Name the relevant category, series, period, panel, value, ordering, or relationship whenever displayed. Discuss only the changed figure-verifiable content. Do not list surface-level edits.]",
  "reasoning_trap": "[Name the primary figure-based mistake, such as category substitution, denominator shift, baseline substitution, aggregation error, scope shift, measure conflation, temporal reference shift, quantifier error, rank substitution, or panel confusion.]",
  "difficulty_check": "[State the minimum reasoning steps required, the number of figure elements that must be examined, and the visual distinction that must be resolved. Explain briefly why the counterfactual could mislead a shallow system despite extensive rephrasing.]",
  "difficulty_rating": "[Easy / Medium / Hard / Very hard]"
}

Target Difficulty:
[TARGET_DIFFICULTY]

Figure:
[INSERT FIGURE OR FIGURE DESCRIPTION]

Supported true statement:
[INSERT TRUE STATEMENT]
