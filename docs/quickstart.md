# Quickstart Guide
## Download
Clone or download the Nobius repository, which includes the rendering scripts, docs, tests, and example/tutorial fixtures.


## Prerequisites
To start off, you'll have to install the python packages required by each script. These are stored in a file called `requirements.txt` available in the main download directory. Acquiring them can easily be done using `pip` (the python package installer):

```bash
pip install -r requirements.txt
```

You'll also need access to a Mobius account, as a teacher.

## Setup

!!! info
    Our set of tools requires a few files to be uploaded to your Mobius content repository. Instead of repeating the same code at the bottom of each rendered question, these "global" script and styling files are used. Without them, uploaded content will look garbled and be inoperational. More information about this is available [here][1].

In a web browser, navigate to your **Content Repository** tab on your Mobius account. Click the **Import** button towards the top of the page and upload the `ResourcesBundle.zip` file.

Now, the Nobius rendering scripts need to be setup to correctly reference the files you just uploaded. They need to know where to look for the global scripts, once sheets are rendered. This is a slightly convoluted step...

- Opening the Mobius Content Repository in a web browser, select **? Questions** under the *Current Class* tab.
- You'll then be able to create a Mobius question (you'll be able to delete it later)
    - Click the **Create New** button at the bottom of the page, and select *Question/Text*
- Now that you're in the native Mobius *Question Designer* tool, within the editor in the *Question Text* section, select the *Image* upload button, as seen in the screenshot below. ![Image upload example from Mobius](Assets\Screenshots\MobiusImageUpload.jpg)
- In the *Image Properties* window that pops up, click the **Browser Server** button. This will open a new *CKFinder* window, which allows you to browse through the static files you have stored on mobius.
- You should be able to see a *Scripts* folder within the file structure, this comes from the `ResourcesBundle` you uploaded earlier. Click on it.
- Within the folder, will be a `QuestionsJavascript.txt` file. Rightclick it, and select **View**, as in the screenshot below: ![CKFinder screenshot showing QuestionJavascript.txt](Assets\Screenshots\CKFinderQuestionJavascript.png)
- This will open the `QuestionJavaScript.txt` file in a new window. Copy the URL of this page, starting from and including */web/*.

!!! Example
    An example URL might look like this: `/web/username/Public_Html/Scripts/QuestionJavaScript.txt`

- Once you have grabbed that URL, open the `nobius.json` file from the Nobius toolset in a text editor and paste it into `render.scripts_location`. If your exam rendering profile uses a different script path, also update `render.exam_scripts_location`.

- If your Mobius theme URI is different, set `render.theme_location` and optionally `render.exam_theme_location` in the same `nobius.json` file.

!!! warning
    The default `nobius.json` values are placeholders. Rendering will fail until you replace them with real Mobius paths for your deployment.

Nobius is now all setup!

## Verify the installation

Once the dependencies are installed, you can verify that the local Nobius toolchain is healthy by running:

```bash
python -m pytest -q
```

This executes the public regression suite against tutorial fixtures and importer fixtures bundled with the repo.

## Getting started
Our tools come packaged with public tutorial sheets you can render to test your installation. Once you have completed the setup, simply run the command below. Detailed information for each of the scripts in Nobius are available in the [Usage][2] section of this documentation.

```unix
python generateGroup.py "C:\path\to\Nobius\Questions\t01" --write-missing-uids
```

## UIDs and first render

Nobius expects question and sheet `uid` values to be stable. By default, rendering refuses to proceed if they are missing.

For first-time setup of a new sheet, initialize and persist missing UIDs explicitly:

```bash
python generateGroup.py "C:\path\to\sheet" --write-missing-uids
```

For exam-style rendering, use the same command with the exam render profile:

```bash
python generateGroup.py "C:\path\to\sheet" --render-profile exam --write-missing-uids
```

After that, normal renders should be read-only with respect to the source JSON files.

Once you've done this, a new `renders` folder will appear under the tutorial sheet folder you just rendered. This contains a *.zip* file containing all the questions and media that pertain to this test sheet, nicely bundled and ready to be uploaded to Mobius!

In the same way you uploaded the `ResourcesBundle.zip`, you can upload the generated tutorial-sheet `.zip` file directly to your Mobius Content Repository (in your browser). A new folder within the content repository will appear, containing all the questions from the sheet you just uploaded, in the Mobius format.

You are now ready to start making your own sheets! have a look at the different sections of this documentation for more help, below are a few suggestions:

- [Sheet File Structure][3]
- [GenerateGroup.py][2] *(This is the main script you'll be using)*
- [Question Files][4]
- [True-False Response Area][5]

[1]: CustomizationAndResources\QuestionJavascript
[2]: Usage\generateGroup
[3]: SheetFiles\SheetFileStructure
[4]: SheetFiles\Questions
[5]: ResponseAreas\Vanilla\true_false
