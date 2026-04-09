import xml.etree.ElementTree as ET

from generateMoodleXML import build_demo_quiz, write_demo_quiz


def test_build_demo_quiz_contains_plain_text_shortanswer_and_multichoice():
    tree = build_demo_quiz()
    root = tree.getroot()

    questions = root.findall("question")
    assert len(questions) == 7
    assert questions[0].attrib["type"] == "category"
    assert questions[1].attrib["type"] == "shortanswer"
    assert questions[2].attrib["type"] == "multichoice"
    assert questions[3].attrib["type"] == "truefalse"
    assert questions[4].attrib["type"] == "numerical"
    assert questions[5].attrib["type"] == "matching"
    assert questions[6].attrib["type"] == "essay"

    shortanswer = questions[1]
    assert shortanswer.find("./name/text").text == "Text Entry"
    assert shortanswer.find("./questiontext").attrib["format"] == "plain_text"
    assert shortanswer.find("./questiontext/text").text == "Define a fluid."
    assert "<" not in shortanswer.find("./questiontext/text").text
    assert shortanswer.find("./answer").attrib["fraction"] == "100"

    multichoice = questions[2]
    assert multichoice.find("./name/text").text == "Multiple Choice"
    assert multichoice.find("./questiontext").attrib["format"] == "plain_text"
    assert multichoice.find("./single").text == "true"
    assert len(multichoice.findall("./answer")) == 3
    assert any(answer.attrib["fraction"] == "100" for answer in multichoice.findall("./answer"))

    truefalse = questions[3]
    assert truefalse.find("./name/text").text == "True False"
    assert len(truefalse.findall("./answer")) == 2

    numerical = questions[4]
    assert numerical.find("./name/text").text == "Numerical"
    assert numerical.find("./answer/tolerance").text == "0.01"

    matching = questions[5]
    assert matching.find("./name/text").text == "Matching"
    assert len(matching.findall("./subquestion")) == 3

    essay = questions[6]
    assert essay.find("./name/text").text == "Essay"
    assert essay.find("./responseformat").text == "editor"
    assert essay.find("./attachments").text == "0"


def test_write_demo_quiz_writes_valid_xml(tmp_path):
    output_path = tmp_path / "moodle_demo.xml"

    written = write_demo_quiz(output_path)

    assert written == output_path
    assert output_path.exists()

    parsed = ET.parse(output_path)
    assert parsed.getroot().tag == "quiz"
