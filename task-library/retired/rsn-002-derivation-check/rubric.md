# Public Scoring Rubric: rsn-002

The automated checker validates the identified step, sample speeds, dimensional certificate, and recomputation of at least one discrimination certificate. Require both the in-domain counterexample and the independent limit certificate specified in instruction.md.

Numeric answers use one shared tolerance: absolute error at most 0.005 m/s or relative error at most 0.1%. Correct-formula symbolic equivalence and explanation quality remain unscored and must not be described as fully validated based only on numeric checks.

The task is a small synthetic physics derivation check. It is not evidence of general physics ability. Human review may assess whether the explanation and formula correctly identify the reasoning error.


## Trial score and answer format

The trial score is the fraction of content checks passed, which gives partial credit. The trial is resolved when every critical check passes. The answer must be one JSON object, as the instruction says. If the answer is not one JSON object, it is recovered when exactly one JSON object can be found in it: the only fenced code block that holds one, or else the only top-level object in surrounding prose. With no candidate, or with several, nothing is recovered. A recovered answer is graded on its content, fails the non-critical `answer-format` check, and loses 20% of its score. An answer that cannot be parsed fails every content check.
