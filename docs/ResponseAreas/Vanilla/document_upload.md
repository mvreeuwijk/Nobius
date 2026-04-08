# Document Upload

A `Document Upload` response collects a file from the student instead of a typed answer.

Typical uses include:

- scanned handwritten work
- annotated PDFs
- spreadsheets
- code files

## Example

```json
"response": {
  "mode": "Document Upload",
  "uploadMode": "code",
  "codeType": "alphanumeric",
  "fileExtensions": ["pdf", "png"],
  "notGraded": true
}
```

## Parameters

- `uploadMode`
  - `direct`: the student uploads the file during the activity
  - `code`: Möbius generates a document code and the file can be uploaded later on the student's behalf
- `codeType`
  - `numeric`
  - `alphabetic`
  - `alphanumeric`
- `fileExtensions`: allowed upload extensions without dots
- `notGraded`: whether the response is treated as not graded / manual collection

## Notes

- Document upload questions are manually reviewed in Möbius workflows.
- Nobius normalizes this response type to the lower-level fields used by the rendered Mobius package.
- Adaptive questions in Nobius reject `Document Upload` response areas during validation.
