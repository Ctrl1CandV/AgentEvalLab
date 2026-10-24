"""The routes item's instances: two public samples and eight hidden instances of 50 to 800 customers.
Each entry: (seed, customers, layout, refrigerated share, van capacity, maximum route minutes)."""
import model

SAMPLES = {"s1": ("routes-sample-1", 30, "random", 0.2, 100, 480), "s2": ("routes-sample-2", 150, "clustered", 0.25, 100, 480)}
HIDDEN = {
    "h1": ("routes-hidden-1", 50, "clustered", 0.2, 100, 480),
    "h2": ("routes-hidden-2", 80, "random", 0.3, 100, 480),
    "h3": ("routes-hidden-3", 120, "clustered", 0.25, 80, 360),
    "h4": ("routes-hidden-4", 200, "random", 0.15, 100, 480),
    "h5": ("routes-hidden-5", 300, "clustered", 0.3, 120, 600),
    "h6": ("routes-hidden-6", 400, "random", 0.2, 100, 420),
    "h7": ("routes-hidden-7", 600, "clustered", 0.2, 100, 480),
    "h8": ("routes-hidden-8", 800, "random", 0.25, 120, 540),
}
THRESHOLDS = (50, 80, 90, 97)


def instance(name):
    return model.generate(*(SAMPLES | HIDDEN)[name])
