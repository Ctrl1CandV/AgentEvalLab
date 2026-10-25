## Brief: a three-step membership form for Orbit Coworking

**Audience.** Freelancers and small teams signing up on a laptop or phone.
**Tone.** Friendly, clear, reassuring.

**Content** (`public/content.json`): the steps, field labels, the three plans with notes, button labels, and the error and success messages.

**The page must**
- show which step is current (`data-role="step-indicator"`, reading "Step 1 of 3" and so on);
- step 1: "Full name" and "Email" fields (labelled with exactly those words); "Next" (`data-role="next-button"`) moves on only with a name and a valid email; otherwise it shows the error message in `data-role="form-error"` and stays on step 1;
- step 2: the three plans as radio buttons, each labelled with the plan's name; "Back" (`data-role="back-button"`) returns to the previous step and keeps what was entered;
- step 3: a review (`data-role="review-summary"`) showing the name, the email and the plan, and the submit button (`data-role="submit-button"`), which shows the success message in `data-role="form-success"`.
