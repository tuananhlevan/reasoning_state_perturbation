import re

with open('/home/levantuananh/FFT_FPT/mutate/prompts/original_text_fig.md', 'r') as f:
    text = f.read()

replacements = [
    (
        "Your task is to generate exactly one counterfactual claim that is decisively contradicted by a fact directly visible in the figure.\n\nThe counterfactual may be rewritten freely at the surface level — wording, grammar, syntax, sentence structure, and vocabulary are all unrestricted. However, exactly one independently falsifiable semantic proposition may differ from the original. All surface edits must serve that single semantic change and must not introduce any additional falsifiable claim.",
        "Your task is to generate exactly two claims: one entailed claim that is fully supported by the figure and aligned with the original statement, and exactly one counterfactual claim that is decisively contradicted by a fact directly visible in the figure.\n\nFor the counterfactual, it may be rewritten freely at the surface level — wording, grammar, syntax, sentence structure, and vocabulary are all unrestricted. However, exactly one independently falsifiable semantic proposition may differ from the original. All surface edits must serve that single semantic change and must not introduce any additional falsifiable claim. The entailed claim should also be propositionally aligned with the original statement and can be rewritten at the surface level, but must remain entirely true based on the figure."
    ),
    (
        "1. The counterfactual must be false because of evidence directly visible in the figure.\n2. It must remain propositionally aligned with the original statement.\n3. It must change only one independently falsifiable, figure-verifiable semantic aspect.\n4. It must preserve all non-figure context and assumptions unless grammatical changes are necessary.\n5. Among valid candidates, prefer the most plausible, subtle, and natural counterfactual.\n6. Difficulty must reflect only the minimum visual reasoning required to disprove the claim.",
        "1. The counterfactual must be false because of evidence directly visible in the figure.\n2. The entailed claim must be true and fully supported by evidence directly visible in the figure.\n3. Both claims must remain propositionally aligned with the original statement.\n4. The counterfactual must change only one independently falsifiable, figure-verifiable semantic aspect.\n5. Both claims must preserve all non-figure context and assumptions unless grammatical changes are necessary.\n6. Among valid candidates, prefer the most plausible, subtle, and natural counterfactual.\n7. Difficulty must reflect only the minimum visual reasoning required to disprove the counterfactual claim."
    ),
    (
        "The counterfactual must be false because of visible evidence in the figure, not because of outside knowledge, an unstated definition, a technical convention, or an inferred assumption.",
        "The counterfactual must be false because of visible evidence in the figure, not because of outside knowledge, an unstated definition, a technical convention, or an inferred assumption. The entailed claim must similarly rely only on visible evidence."
    ),
    (
        "The counterfactual does not need to preserve the original wording or sentence structure.\n\nHowever, it must preserve the original statement's general:\n\n* subject;\n* measure or outcome;\n* population or category scope;\n* time frame, unless time is the single modified dimension;\n* comparison or interpretive focus;\n* non-figure context.\n\nThe counterfactual should express substantially the same underlying proposition as the original while changing exactly one figure-verifiable semantic aspect.\n\nAfter removing the altered figure-verifiable component, the original and the counterfactual should communicate essentially the same remaining proposition.",
        "The generated claims do not need to preserve the original wording or sentence structure.\n\nHowever, they must preserve the original statement's general:\n\n* subject;\n* measure or outcome;\n* population or category scope;\n* time frame, unless time is the single modified dimension;\n* comparison or interpretive focus;\n* non-figure context.\n\nThe counterfactual should express substantially the same underlying proposition as the original while changing exactly one figure-verifiable semantic aspect. The entailed claim should express the same underlying proposition without changing its truth value.\n\nAfter removing the altered figure-verifiable component, the original, the entailed claim, and the counterfactual should communicate essentially the same remaining proposition."
    ),
    (
        "* The counterfactual must refer to the same primary subject and primary measure as the original statement.",
        "* Both generated claims must refer to the same primary subject and primary measure as the original statement."
    ),
    (
        "## Counterfactual construction requirements\n\nThe counterfactual claim must:\n\n* be fluent and contextually appropriate;",
        "## Claim construction requirements\n\nThe entailed claim must:\n\n* be fluent and contextually appropriate;\n* remain propositionally aligned with the original;\n* be strictly true based on the figure;\n* preserve non-figure context.\n\nThe counterfactual claim must:\n\n* be fluent and contextually appropriate;"
    ),
    (
        "Surface rephrasing is unrestricted. The counterfactual may differ substantially from the original in wording, grammar, and sentence structure. Among valid candidates that achieve the same single semantic pivot, prefer the most natural and plausible rephrasing, not the one most similar to the original wording.",
        "Surface rephrasing is unrestricted. The generated claims may differ substantially from the original in wording, grammar, and sentence structure. Among valid candidates for the counterfactual that achieve the same single semantic pivot, prefer the most natural and plausible rephrasing, not the one most similar to the original wording."
    ),
    (
        "2. **Alignment check**\n   Confirm that the counterfactual preserves the same subject, measure, scope, and interpretive focus, except for the single modified semantic dimension.",
        "2. **Alignment check**\n   Confirm that the counterfactual preserves the same subject, measure, scope, and interpretive focus, except for the single modified semantic dimension. Confirm that the entailed claim also preserves these aspects while remaining strictly true."
    ),
    (
        "Original claim:\n[Copy the input exactly.]\n\nCounterfactual claim:\nCannot generate a figure-grounded counterfactual.",
        "Original claim:\n[Copy the input exactly.]\n\nEntailed claim:\nCannot generate a figure-grounded entailed claim.\n\nCounterfactual claim:\nCannot generate a figure-grounded counterfactual."
    ),
    (
        "Original claim:\n[Copy the input exactly.]\n\nCounterfactual claim:\nCannot generate a decisive figure-grounded counterfactual.",
        "Original claim:\n[Copy the input exactly.]\n\nEntailed claim:\nCannot generate a decisive figure-grounded entailed claim.\n\nCounterfactual claim:\nCannot generate a decisive figure-grounded counterfactual."
    ),
    (
        "{\n  \"internal_verification\": \"[Briefly execute the 7th step of your internal check: list the intended semantic pivot and confirm no other verifiable facts are altered.]\",\n  \"original_claim\": \"[Copy the supported statement verbatim, preserving wording and punctuation.]\",\n  \"counterfactual_claim\": \"[Write one false but propositionally aligned claim. MANDATORY: You must completely rewrite the sentence structure and vocabulary of the surrounding text based on your rephrasing plan. Free and extensive surface rephrasing is allowed, but exactly one semantic proposition may differ from the original.]\",",
        "{\n  \"internal_verification\": \"[Briefly execute the 7th step of your internal check: list the intended semantic pivot and confirm no other verifiable facts are altered.]\",\n  \"original_claim\": \"[Copy the supported statement verbatim, preserving wording and punctuation.]\",\n  \"entailed_claim\": \"[Write one true claim that is fully entailed by the figure and propositionally aligned with the original statement. Surface rephrasing is allowed, but the underlying semantics must remain true.]\",\n  \"counterfactual_claim\": \"[Write one false but propositionally aligned claim. MANDATORY: You must completely rewrite the sentence structure and vocabulary of the surrounding text based on your rephrasing plan. Free and extensive surface rephrasing is allowed, but exactly one semantic proposition may differ from the original.]\","
    )
]

for old, new in replacements:
    if old not in text:
        print(f"FAILED TO FIND:\n{old}\n\n")
    text = text.replace(old, new)

with open('/home/levantuananh/FFT_FPT/mutate/prompts/original_text_fig.md', 'w') as f:
    f.write(text)

