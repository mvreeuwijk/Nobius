# Quickstart Guide

## Download

Clone or download the Nobius repository, which includes the rendering scripts, docs, tests, and example/tutorial fixtures.

## Prerequisites

Install the Python packages required by the scripts. They are listed in `requirements.txt` in the main download directory:

```bash
pip install -r requirements.txt
```

You'll also need access to a Mobius account with teacher permissions.

## Setup

!!! info
    Nobius relies on a small set of shared Mobius resources. Without them, rendered content will look garbled and be inoperational. More information about this is available [here][1].

In a web browser, navigate to your **Content Repository** tab in Mobius. Click the **Import** button and upload `ResourcesBundle.zip`.

Now configure Nobius so the render scripts can reference the uploaded resources correctly.

There are 2 ways to discover the needed paths:

- directly from Möbius while authoring, by browsing to the uploaded JavaScript file
- from a real exported Möbius package by inspecting `manifest.xml`

The second method is often the most reliable because it shows the exact resource URIs Möbius actually wrote into an exported assignment or Course Module.

- In the Mobius Content Repository, select **Questions** under the current class.
- Create a temporary Mobius question with **Create New -> Question/Text**.
- In the native Mobius Question Designer, use the image upload button in the question text editor.
- In the **Image Properties** window, click **Browser Server** to open CKFinder.
- Browse to the uploaded `Scripts` folder from `ResourcesBundle.zip`.
- Open `QuestionJavaScript.txt` and copy the URL, starting from and including `/web/`.

!!! Example
    An example URL might look like this: `/web/username/Public_Html/Scripts/QuestionJavaScript.txt`

- Paste that URL into the appropriate profile under `profiles.<name>.render.scripts_location` in `nobius.json`.
- Set the corresponding `profiles.<name>.render.theme_location` value to the `/themes/...` URI used by that profile.

Alternatively, if you already have a rendered question or assignment in Möbius:

- Export the question, assignment, or Course Module as a `.zip` package.
- Open the package and inspect `manifest.xml`.
- Search for:
  - `/themes/...`
  - `/web/.../QuestionJavaScript.txt`
  - or `__BASE_URI__Scripts/QuestionJavaScript.txt`
- Copy those exact values into the appropriate `profiles.<name>.render` block in `nobius.json`.

In practice this means the JavaScript is uploaded to Mobius by importing `ResourcesBundle.zip` into the class Content Repository, while the CSS theme is uploaded separately in Mobius via **Content Repository -> Create New -> Theme** and then referenced by its `/themes/...` URI in the Nobius render config. DigitalEd's theme instructions are here: <https://www.digitaled.com/support/help/admin/Content/INST-CONTENT-REPO/Themes.htm>.

DigitalEd documents theme creation and content export, but does not explicitly document where these internal URIs appear in exported XML. The `manifest.xml` inspection step above is therefore an inference from exported Möbius packages, and is the workflow verified against the real exported ZIPs used in this repo.

Nobius is now set up.

## Verify the installation

Once the dependencies are installed, you can verify that the local Nobius toolchain is healthy by running:

```bash
pytest -q tests
python -m ruff check Nobius
```

This executes the public regression suite against tutorial fixtures and importer fixtures bundled with the repo.

## Getting started

Our tools come packaged with public tutorial sheets you can render to test your installation. Once you have completed the setup, lint and render with:

```bash
python precheck.py "C:\path\to\Nobius\Questions\t01"
python export_mobius.py "C:\path\to\Nobius\Questions\t01" --write-missing-uids
```

`precheck.py` is the pre-export sanity check: it flags whitespace in
media paths, missing figures, mode-vs-answer mismatches, and other
patterns that cause Mobius to reject an import. Every export and preview
script also calls it automatically — running it explicitly while
authoring just gives you the error messages directly. See
[precheck.py](Usage/precheck.md) for the full rule set.

Detailed information for each of the scripts in Nobius is available in the [Usage][2] section of this documentation.

## UIDs and first render

Nobius expects question and sheet `uid` values to be stable. By default, rendering refuses to proceed if they are missing.

For first-time setup of a new sheet, initialize and persist missing UIDs explicitly:

```bash
python export_mobius.py "C:\path\to\sheet" --write-missing-uids
```

For a different deployment/profile, use the same command with `--profile`:

```bash
python export_mobius.py "C:\path\to\sheet" --profile exam --write-missing-uids
```

After that, normal renders should be read-only with respect to the source JSON files.

Once you've done this, a new `renders` folder will appear under the tutorial sheet folder you just rendered. This contains a `.zip` file containing all the questions and media that pertain to this sheet, ready to be uploaded to Mobius.

In the same way you uploaded `ResourcesBundle.zip`, you can upload the generated sheet `.zip` file directly to the Mobius Content Repository. A new folder will appear, containing all the questions from the sheet in the Mobius format.

If you later export edited content back out of Mobius, `import_mobius.py` can import that ZIP back into Nobius JSON. For course-module packages, the importer now reconstructs `assignmentUnits` as folders and keeps multiple assignments as nested subfolders.

You are now ready to start making your own sheets. A few useful starting points are:

- [Sheet File Structure][3]
- [export_mobius.py][2] *(This is the main script you'll be using)*
- [preview_html.py][6]
- [export_pdf.py][7]
- [import_mobius.py][8]
- [Question Files][4]
- [True-False Response Area][5]

[1]: CustomizationAndResources/QuestionJavascript.md
[2]: Usage/export_mobius.md
[3]: SheetFiles/SheetFileStructure.md
[4]: SheetFiles/Questions.md
[5]: ResponseAreas/Vanilla/true_false.md
[6]: Usage/preview_html.md
[7]: Usage/export_pdf.md
[8]: Usage/import_mobius.md

