# Question Part
This parameter is stored in the [`parts`][1] list in a [question][2] JSON file. It is the primary unit of content inside a question, holding:

 - [part statement][3]
 - [response area][4]
 - [media][5]
 - [final answer][6]
 - [worked solutions][7]
 - [structured tutorial][8]

For a concise summary of supported part fields, whether they are required, and whether they are implemented, see the [Field Reference](FieldReference.md).

[1]: Questions.md#parts
[2]: Questions.md

[3]: #statement
[4]: #response-areas
[5]: #media
[6]: #final_answer
[7]: #worked_solutions
[8]: #structured_tutorial

## `statement`
Part statement

??? abstract "Example"
    ```json
    "statement": "Derive an expression for the acceleration"
    ```

## Response areas
Optional, these are items which students can interact with and submit their response(s) to a question's part, possibly getting feedback. We distinguish 2 types of response areas: Vanilla response areas, which are native to Mobius, and Advanced response areas which use these vanilla response areas to construct more complex response areas.

!!! warning
    For a given part, there can only be one of `response`, `responses` or `custom_response` fields.

### Pre and Post Response area text
Sometimes, extra text needs to be placed before (to specify which answer to add) or after a response area (to add units for example). This is what the `pre_response_text` and `post_response_text` parameters achieve. Placed in the main question part dictionary, these will add some text before or after a response area. Again, these are **part level** parameters.

??? abstract "Example"
    ```json
    "pre_response_text": "f(x) = "
    ```

### Importing single response areas
All vanilla inputs (as well as the [Matrix][9] response area) can be added to a question by adding a `response` dictionary which holds all the parameters required by that type. These parameters are described in length in their relative documentation pages (see the Response Areas section)

??? abstract "Example"
    ```json
    "response": {
      "mode": "Maple",
      "mapleAnswer": "m*x + c"
    }
    ```

[9]: ../ResponseAreas/Advanced/matrix.md

### Importing Multiple response areas
If multiple response areas are required for a part, these can be included similarly to [single response areas][10], but in a list of dictionaries each containing a `response`. When multiple response areas are displayed in a part, `pre_response_text` and `post_response_text` should be used to indicate which answer belongs where. They can be added inside each item in the `responses` list when needed.

??? abstract "Example"
    ```json
    "responses": [
      {
        "pre_response_text": "f(x) = ",
        "response": {
          "mode": "Maple",
          "mapleAnswer": "17*x + b"
        }
      },
      {
        "pre_response_text": "g = ",
        "response": {
          "mode": "Numeric",
          "showUnits": true,
          "answer": {
            "num": "9.81",
            "units": "m/s/s"
          }
        },
        "post_response_text": "m/s^2"
      }
    ]
    ```

[10]: #importing-single-response-areas

### Importing a custom response area
When both the `response` and `responses` modules aren't enough, you can include a `custom_response` to your part. This gives author ultimate control over the position and styling of their response areas by allowing HTML, JavaScript and CSS to be input. [Take me to the `custom_response` docs][11].

[11]: ../ResponseAreas/Advanced/custom.md

### Importing an HTML response component
If the student interaction itself needs to be a custom HTML/CSS/JavaScript widget, use the `HTML` response mode rather than `custom_response`.

`custom_response` is for arranging standard response areas in custom layouts. `HTML` is for authoring a distinct custom component with JavaScript hooks and grading behaviour. [Take me to the `HTML` response docs][13].

[13]: ../ResponseAreas/Advanced/html.md

## `media`
Optional, This parameter has the same syntax as the one used at the master statement question level. It will include any media referenced at part-level. [Take me to its docs][12].

[12]: Questions.md#media

## `final_answer`
Optional, part of the `help` module
final answer block. Supports:

- `text`
- `equation`
- `media`

## `worked_solutions`
Optional, part of the `help` module
step-by-step worked solution content. Each step can contain:

- `text`
- `equation`
- `media`
- `is_final_answer`

## `structured_tutorial`
Optional, part of the `help` module
step-by-step tutorial content. Each step can contain:

- `text`
- `equation`
- `h5p_link`
- `media`
- `response`
- `responses`
- `custom_response`
