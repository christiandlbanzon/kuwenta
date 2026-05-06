# OCR eval dataset

Drop receipt images (jpg/png/webp) in this directory and add a corresponding entry to `ground_truth.jsonl` (one JSON object per line).

Each ground-truth entry:

```json
{
  "image": "jollibee_2026_04_15.jpg",
  "merchant": "Jollibee",
  "total": "180",
  "occurred_at": "2026-04-15T12:30:00+08:00",
  "payment_method": "gcash",
  "category": "Food & Dining",
  "min_line_items": 2
}
```

Fields:
- `image`: filename relative to this directory
- `merchant`: expected vendor (case-insensitive fuzzy match, ≥ 0.8 similarity counts)
- `total`: expected total amount (within ₱1)
- `occurred_at`: optional — if present, eval checks date matches (time tolerance: same day)
- `payment_method`: optional — exact match
- `category`: expected category name (exact)
- `min_line_items`: optional — eval checks `len(line_items) >= min_line_items`

The eval runs every receipt in `ground_truth.jsonl` through Gemini Vision and reports per-field accuracy.
