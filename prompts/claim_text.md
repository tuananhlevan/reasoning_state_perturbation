Create one adversarial counterfactual for semantic-equivalence and contradiction evaluation.

Rewrite the original claim fluently while changing exactly one independently falsifiable semantic proposition (such as one fact, relation, condition, quantity, date, causal link, scope, comparison, or temporal order). Surface wording and syntax may change freely, but every unaffected proposition, named entity, contextual assumption, and level of detail must retain its meaning.

The counterfactual must directly contradict the original under the same interpretation; contain no second contradiction, unsupported detail, or unrelated change; remain plausible and easy to mistake for a paraphrase; avoid mere weakening, generalization, qualification, obvious antonym swaps, and reliance on explicit negation; and consist of exactly one false sentence.

Difficulty is the minimum reasoning required:

- Easy

* The changed fact is locally visible and can be detected by comparing one word, number, date, entity, or relation.
* Little or no contextual reasoning is required.
* A simple lexical, numeric, or entity-level comparison would probably detect it.
* Examples include a plainly changed date, quantity, location, direction, or role.

- Medium

* The contradiction requires interpreting a phrase, clause, comparison, scope marker, or temporal relation.
* The relevant words may overlap heavily, but the altered meaning is still confined to a small part of the sentence.
* A careful sentence-level model should detect it without needing multi-step reasoning.
* Examples include changing "before" to "after," shifting who acted on whom, or altering the scope of a condition.

- Hard

* The contradiction requires combining information from multiple parts of the sentence or resolving syntax, reference, causality, qualification, or nested scope.
* The altered claim remains highly similar in meaning and is likely to be mistaken for a paraphrase.
* Detection requires at least two linked reasoning steps.
* The contradiction should still be explicit enough to justify from the text alone.

Assign the lowest valid rating. Surface dissimilarity, length, and technical vocabulary do not increase difficulty. Explicitly verify that exactly one meaning-bearing element changed, all others are preserved, the claims are incompatible, and the requested difficulty matches the result. Put this concise verification in `reasoning`; identify the original proposition, the single altered proposition, and why they cannot both be true. Do not provide hidden chain-of-thought or unrelated analysis.

Return only this valid JSON object:

{
  "claim": "[exactly one counterfactual sentence]",
  "reasoning": "[concise verification of the single semantic change and direct contradiction]",
  "difficulty": "[TARGET_DIFFICULTY]",
  "label": "refuted"
}

The response must contain exactly these four fields. `claim` and `reasoning` must be non-empty strings, `difficulty` must exactly equal `[TARGET_DIFFICULTY]`, and `label` must exactly equal `refuted`.

Target difficulty:
[TARGET_DIFFICULTY]

Original claim:
[INSERT TRUE STATEMENT]
