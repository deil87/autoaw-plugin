# Building the eval set

The optimisation is only as real as these rows. Each rule below exists because
breaking it has produced a confident number that measured nothing.

## Where rows come from, best first

1. **Logged production inputs**: request logs, traces (LangSmith, Langfuse,
   Phoenix exports), support tickets. These are the real distribution.
2. **Existing tests and fixtures**: `tests/fixtures/*.json`, eval notebooks,
   golden files. They often carry expected answers already.
3. **Examples in docs**: README usage examples, docstrings.
4. **Synthetic inputs**: only to fill gaps. Write them in the style of the
   real ones and label them `stratum: "synthetic"`, so their effect can be seen
   separately.

## Expected answers

- Copy them where they exist. Do not invent them.
- If none exist, either:
  - draft labels and have the user review every one, or
  - use `llm_judge` with a rubric the user approves. Rubrics should be concrete:
    "names the order id; offers a refund only if the order is under 30 days old",
    not "is helpful".
- For classification outputs, use `reference` with `exact_match`. Make the
  expected label match what the workflow actually outputs, including case,
  whitespace and any wrapping JSON. A smoke run where every row scores 0.0 is
  usually a format mismatch, not a bad workflow.

## Size and balance

- 30+ rows is good, 10 is the floor, 500 the cap.
- The gold label works as a `stratum` for a classifier. The stratum is only
  used for sampling; the model never sees it.
- If the inputs have kinds (ticket category, difficulty, language), set a
  `stratum` on each row. AutoAW samples round-robin across strata. Without
  labels, a file sorted by kind gets its first kind sampled and nothing else.
- Include the hard cases the user actually worries about. A set the workflow
  already aces leaves nothing to improve.

## Privacy

The rows are uploaded to AutoAW, stored per account, and not shared. Even so,
before including names, emails, account numbers or health data, ask the user.
Offer to redact them (`<NAME>`, `<EMAIL>`) consistently, so that the redacted
input still makes sense.
