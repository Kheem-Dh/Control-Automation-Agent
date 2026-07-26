# Eval Results

Exception detection measured against labelled synthetic ground truth (confidence threshold 0.7).

| Control | Precision | Recall | False-positive rate | Escalated to human |
|---------|-----------|--------|---------------------|--------------------|
| AC-1 (termination) | 1.00 | 1.00 | 0.00 | 2 |
| AC-2 (SoD) | 1.00 | 1.00 | 0.00 | 2 |
| AC-3 (privileged) | 1.00 | 1.00 | 0.00 | 2 |

**Confusion matrix (per control).**

| Control | Population | TP | FP | FN | TN |
|---------|-----------|----|----|----|----|
| AC-1 | 23 | 6 | 0 | 0 | 17 |
| AC-2 | 198 | 5 | 0 | 0 | 193 |
| AC-3 | 18 | 6 | 0 | 0 | 12 |

**Why both precision and recall matter.** A false negative is a missed control failure; a false positive is wasted auditor time. Accuracy alone would hide that trade-off.

