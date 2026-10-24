"""The routes item's checks for the manifest builder: four score thresholds per hidden instance, and (grader 1.7.0)
`feasible`, a feasible plan for at least one hidden instance. The routes grader (grade_routes in grader.py) runs and
scores the instances itself."""
HIDDEN = ["h1", "h2", "h3", "h4", "h5", "h6", "h7", "h8"]
THRESHOLDS = (50, 80, 90, 97)
FIXTURES = [(f"{name}-{threshold}", name, None, None) for name in HIDDEN for threshold in THRESHOLDS] + [("feasible", None, None, None)]
