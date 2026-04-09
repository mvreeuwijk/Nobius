# HTML Response

Nobius supports a first-class `HTML` response mode for questions that need a custom HTML/CSS/JavaScript interaction without overloading `custom_response`.

This maps to Möbius's HTML response component concept: the student interacts with a custom widget, JavaScript returns a response value, and that value can be automatically or manually graded.

## Example

```json
"response": {
  "mode": "HTML",
  "gradingType": "auto",
  "answer": "42",
  "html": "<div id=\"widget\"></div>",
  "css": "#widget { min-height: 20px; }",
  "javascript": "function initialize(interactiveMode) {}\nfunction setFeedback(response, answer) {}\nfunction getResponse() { return '42'; }",
  "grading_code": "evalb(($ANSWER)-($RESPONSE)=0);"
}
```

## Parameters

- `gradingType`: `auto` or `manual`
- `answer`: Maple expression for the correct answer when auto-graded
- `grading_code`: Maple grading code used for automatic grading
- `html`: HTML rendered inside the component
- `css`: CSS scoped to the component
- `javascript`: component JavaScript, typically defining:
  - `initialize(interactiveMode)`
  - `setFeedback(response, answer)`
  - `getResponse()`

## Notes

- Use `HTML` when the student interaction itself is custom.
- Use `custom_response` when you only want custom layout for standard Möbius response areas.
- Manual grading is supported by Möbius for HTML components, but Nobius only enforces adaptive-question restrictions for essay and document-upload components.
