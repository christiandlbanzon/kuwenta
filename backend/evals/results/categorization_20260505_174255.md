# Categorization eval

**Examples:** 55  
**Accuracy:** 3.64%  
**Macro F1:** 0.028

## Per-category performance

| Category | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| Bills & Utilities | 0.000 | 0.000 | 0.000 | 6 |
| Entertainment | 0.000 | 0.000 | 0.000 | 4 |
| Family Support | 0.000 | 0.000 | 0.000 | 2 |
| Food & Dining | 1.000 | 0.200 | 0.333 | 10 |
| Freelance | 0.000 | 0.000 | 0.000 | 2 |
| Government Contributions | 0.000 | 0.000 | 0.000 | 4 |
| Groceries | 0.000 | 0.000 | 0.000 | 7 |
| Healthcare | 0.000 | 0.000 | 0.000 | 4 |
| Salary | 0.000 | 0.000 | 0.000 | 1 |
| Shopping | 0.000 | 0.000 | 0.000 | 4 |
| Tithing & Donations | 0.000 | 0.000 | 0.000 | 2 |
| Transportation | 0.000 | 0.000 | 0.000 | 9 |

## Mispredictions

| Expected | Predicted | Count |
|---|---|---:|
| Transportation | ERROR: ClientError | 9 |
| Food & Dining | ERROR: ClientError | 8 |
| Groceries | ERROR: ClientError | 7 |
| Bills & Utilities | ERROR: ClientError | 6 |
| Shopping | ERROR: ClientError | 4 |
| Healthcare | ERROR: ClientError | 4 |
| Government Contributions | ERROR: ClientError | 4 |
| Entertainment | ERROR: ClientError | 4 |
| Family Support | ERROR: ClientError | 2 |
| Tithing & Donations | ERROR: ClientError | 2 |
| Freelance | ERROR: ClientError | 2 |
| Salary | ERROR: ClientError | 1 |

**Avg confidence on correct:** 0.950  
**Avg confidence on wrong:** 0.000
