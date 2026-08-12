# Supported question patterns

Gemini interprets these business questions and returns candidate SQL:

- Daily transaction count, total amount, and historical validation percentage
- Amount-range transaction and high-review-priority comparisons
- Review-priority comparisons by time segment or time window
- Recent or high-priority analyst review queue records

Every Gemini response is checked by the application SQL validator before Snowflake receives it. Unsupported or unsafe SQL is rejected.
