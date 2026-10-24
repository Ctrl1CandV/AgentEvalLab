# Task: Check a Sliding-Block Derivation (rsn-002)

A student derivation below contains an error. Locate it, give the correct result, and provide evidence that a fixed checker can recompute. The problem statement, step IDs, and input data are in this file and public/samples.json.

## Physics setup

A block of mass m starts at rest and slides a distance L down an incline at angle theta. The kinetic friction coefficient is mu and gravitational acceleration is g. The problem states that the block accelerates downhill; do not determine whether it starts moving.

Domain: 0 < theta < 90 degrees, mu >= 0, and tan(theta) > mu. Every public sample is in this domain.

## Student derivation

- S1: Normal force N = mg.
- S2: Kinetic friction f = mu*N = mu*mg, opposite the direction along the incline.
- S3: By work-energy, mgL sin(theta) - mu*mgL = 1/2*m*v^2.
- S4: Cancel mass and rearrange to v = sqrt(2gL(sin(theta) - mu)).

## Output format

Emit one JSON object only, without Markdown fences. Numeric certificates must contain evaluated numbers, not only formulas.

    {
      "errorStepId": "<step ID>",
      "correctFormula": "<correct speed relation in words or symbols>",
      "v": {"s1": 0, "s2": 0, "s3": 0},
      "dimensionCertificate": {
        "g": {"m": 1, "s": -2}, "L": {"m": 1, "s": 0},
        "mu": {"m": 0, "s": 0}, "v": {"m": 1, "s": -1}
      },
      "counterexampleCertificate": {
        "thetaDeg": 60, "mu": 0.2, "L": 2, "g": 9.8,
        "studentV": 0, "correctV": 0
      },
      "limitCertificate": {
        "mu": 0.2, "L": 2, "g": 9.8,
        "correctLimit": 0, "studentLimit": 0
      },
      "explanation": "<brief explanation and diagnostic basis>"
    }

Submit both recomputable discrimination certificates:

- counterexampleCertificate: choose thetaDeg, mu, L, and g inside the stated domain, then fill correctV and studentV as predicted by the correct and student models.
- limitCertificate: for 0 < mu < 1 and positive L and g, give each model's speed limit as theta approaches 90 degrees. This boundary evidence is required independently; a finite in-domain example cannot replace it.

Use a single tolerance for all numbers: absolute error <= 0.005 m/s or relative error <= 0.1% (either is sufficient). Speeds use m/s; certificate lengths and gravitational acceleration use m and m/s^2.

Automated checks cover the step ID, sample values, structured dimensions, and at least one recomputed discrimination certificate. Correct-formula symbolic equivalence and explanation quality remain unscored; do not claim the full task passed based only on numeric checks.
