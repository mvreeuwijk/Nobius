# Field Reference

This page is the single reference for question JSON fields used by Nobius. It combines:

- the validation schema
- the authoring documentation
- the current render and import behavior

`Required` means required by the validation schema for authored Nobius JSON. `Implemented` means the field affects current validation, rendering, preview, export, or import behavior.

## Question-level fields

| Field | Type | Required | Implemented | Notes |
| --- | --- | --- | --- | --- |
| `title` | `string` | Yes | Yes | Question title shown in rendered output. |
| `master_statement` | `string` | No | Yes | Introductory question statement shown above parts. |
| `media` | `string[]` | No | Yes | Rendered as `<img>` / `<video>` in the question header and bundled into Mobius packages when present. |
| `icon_data` | `object` | No | Yes | Controls the difficulty and par-time icons. |
| `icon_data.difficulty` | `integer` | Required inside `icon_data` | Yes | Allowed values are `1`, `2`, `3`. |
| `icon_data.par_time` | `integer[2]` | Required inside `icon_data` | Yes | Used for the icon display and time analysis summary. |
| `icon_data.statement` | `string` | No | Yes | Rendered as the icon guidance blurb in themed question output. |
| `parts` | `object[]` | Yes | Yes | Main question content. Each item is a part object. |
| `uid` | `string` | Yes | Yes | Source identifier used in rendered/exported Mobius packages. |
| `algorithm` | `string` | No | Yes | Included in rendered question XML when present. |
| `adaptive` | `object` | No | Partly | Used by validation to enforce response restrictions for adaptive questions. It does not enable a separate adaptive render mode. |
| `adaptive.enabled` | `boolean` | Required inside `adaptive` | Yes | Turns adaptive validation checks on. |
| `adaptive.notes` | `string` | No | Yes | Metadata only. Preserved for authoring context. |

## Part-level fields

| Field | Type | Required | Implemented | Notes |
| --- | --- | --- | --- | --- |
| `statement` | `string` | Yes | Yes | Main statement for the part. |
| `media` | `string[]` | No | Yes | Rendered below the part statement and bundled into Mobius packages. |
| `response` | `object` | No | Yes | Single response area for the part. Mutually exclusive with `responses` and `custom_response`. |
| `responses` | `object[]` | No | Yes | Multiple response areas shown within the same part. |
| `custom_response` | `object` | No | Yes | Custom HTML layout that places one or more standard response areas. |
| `pre_response_text` | `string` | No | Yes | Text rendered immediately before a response area. |
| `post_response_text` | `string` | No | Yes | Text rendered immediately after a response area. |
| `input_symbols` | `string[][]` | No | Yes | Rendered into the equation-help panel for symbolic inputs. |
| `final_answer` | `object` | No | Yes | Adds the final-answer help panel. |
| `final_answer.text` | `string` | No | Yes | Rendered in the final-answer panel. |
| `final_answer.equation` | `string` | No | Yes | Rendered in the final-answer panel as equation content. |
| `final_answer.media` | `string[]` | No | Yes | Media shown inside the final-answer panel. |
| `worked_solutions` | `object[]` | No | Yes | Step-by-step worked solutions panel. |
| `worked_solutions[].text` | `string` | No | Yes | Per-step explanatory text. |
| `worked_solutions[].equation` | `string` | No | Yes | Per-step equation content. |
| `worked_solutions[].media` | `string[]` | No | Yes | Per-step media. |
| `worked_solutions[].is_final_answer` | `boolean` | No | Yes | When `true`, renders the part final answer in the step-by-step flow. |
| `structured_tutorial` | `object[]` | No | Yes | Step-by-step tutorial/help flow. |
| `structured_tutorial[].text` | `string` | No | Yes | Per-step tutorial text. |
| `structured_tutorial[].equation` | `string` | No | Yes | Per-step equation content. |
| `structured_tutorial[].h5p_link` | `string` | No | Yes | Embedded activity link when present. |
| `structured_tutorial[].media` | `string[]` | No | Yes | Per-step tutorial media. |
| `structured_tutorial[].response` | `object` | No | Yes | Single response area inside a tutorial step. |
| `structured_tutorial[].responses` | `object[]` | No | Yes | Multiple response areas inside a tutorial step. |
| `structured_tutorial[].custom_response` | `object` | No | Yes | Custom response layout inside a tutorial step. |
| `id` | `string` | No | No | Seen in some imported JSON, but not used in current validation or rendered/exported Mobius output. Nobius generates its own DOM ids such as `part1`, `part2`. |

## Response object fields

These fields belong inside `response`, items inside `responses`, or response objects nested in `structured_tutorial`.

### Common response fields

| Field | Type | Required | Implemented | Notes |
| --- | --- | --- | --- | --- |
| `name` | `string` | Yes | Yes | Logical response name in the rendered Mobius XML. Missing or invalid values are normalised during export where needed. |
| `mode` | `string` | Yes | Yes | Selects the response type. |
| `weighting` | `number` | Yes | Yes | Marks weighting passed through to Mobius response definitions. |
| `comment` | `string` | Yes | Yes | Passed through to response definitions. |

### Maple

| Field | Required | Implemented | Notes |
| --- | --- | --- | --- |
| `type` | Yes | Yes | `formula` or `maple`. |
| `plot` | Yes | Yes | Currently expected to be an empty string. |
| `allow2d` | Yes | Yes | Controls Maple input mode. |
| `mathConversionMode` | Yes | Yes | Expected schema value is `0`. |
| `mapleAnswer` | Yes | Yes | Correct expression. |
| `maple` | Yes | Yes | Grading code. |
| `custompreview` | Yes | Yes | Preview hook. |
| `libname` | No | Yes | Optional library path. |

### List

| Field | Required | Implemented | Notes |
| --- | --- | --- | --- |
| `display` | Yes | Yes | Object with `display` and `permute`. |
| `grader` | Yes | Yes | `exact`, `relaxed`, or `regex`. |
| `answers` | Yes | Yes | Accepted answers. |
| `credits` | Yes | Yes | Mark allocation per answer. |

### Non Permuting Multiple Choice / Multiple Selection / True False

| Field | Required | Implemented | Notes |
| --- | --- | --- | --- |
| `display` | Yes except `True False` | Yes | `vertical` or `horizontal`. |
| `choices` | Yes | Yes | Answer labels or true/false labels. |
| `answer` | Yes | Yes | Correct option or encoded selection string. |

### Numeric

| Field | Required | Implemented | Notes |
| --- | --- | --- | --- |
| `negStyle` | Yes | Yes | `minus`, `paren`, or `both`. |
| `numStyle` | Yes | Yes | Mobius number formatting options. |
| `grading` | Yes | Yes | Exact or tolerance-based grading mode. |
| `showUnits` | Yes | Yes | Controls whether the units input is shown. |
| `answer.num` | Yes | Yes | Numeric answer value. |
| `answer.units` | Yes | Yes | Units string. Empty when `showUnits` is `false`. |
| `digit` | Conditional | Yes | Required for significant-digit grading modes. |
| `err` | Conditional | Yes | Required for absolute or significant-digit tolerance modes. |
| `perc` | Conditional | Yes | Required for percentage tolerance mode. |

### Matching

| Field | Required | Implemented | Notes |
| --- | --- | --- | --- |
| `matchings` | Yes | Yes | List of terms and definitions. |
| `format` | Yes | Yes | Integer or one-item integer list. |

### Essay

| Field | Required | Implemented | Notes |
| --- | --- | --- | --- |
| `keywords` | Yes | Yes | Author keywords list. |
| `maxWordcount` | Yes | Yes | Maximum word count. |

### HTML

| Field | Required | Implemented | Notes |
| --- | --- | --- | --- |
| `gradingType` | Yes | Yes | `auto` or `manual`. |
| `html` / `css` / `javascript` | One supported trio required | Yes | Current concise field names. |
| `questionHTML` / `questionCSS` / `questionJavaScript` | Alternative supported trio | Yes | Legacy Mobius-style field names accepted by schema and importer. |
| `answer` | Conditional | Yes | Required for auto-graded HTML questions. |
| `gradingCode` or `grading_code` | Conditional | Yes | Required for auto-graded HTML questions. |

### Document Upload

| Field | Required | Implemented | Notes |
| --- | --- | --- | --- |
| `uploadMode` | Yes | Yes | `direct` or `code`. |
| `fileExtensions` | Yes | Yes | Allowed upload extensions. |
| `forceUpload` | Yes | Yes | Whether a file must be uploaded. |
| `nonGradeable` | Yes | Yes | Upload is submitted without automatic grading. |
| `notGraded` | No | Yes | Accepted as additional metadata. |
| `codeType` | No | Yes | Optional code classification. |

## Notes on effective support

- A field may be present in imported JSON without being part of the supported authored interface.
- `part.id` is the main current example of that: it can appear in imported data, but the renderer and real Mobius exports do not use it.
- Figure/media support is part of the effective authored interface: referenced media files are bundled into `web_folders/<sheet name>/...` and referenced from the manifest with `__BASE_URI__<sheet name>/...` paths, matching current Möbius package structure.
