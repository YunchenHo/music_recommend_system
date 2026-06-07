"""Cold-start research helpers.

Two scenarios:
- A: leave first N=1/3/5 positives per user as train, the rest as test
- C: hold out an entire group of users (no training history), evaluate via user features only
"""
