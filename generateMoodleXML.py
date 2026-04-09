from argparse import ArgumentParser
from pathlib import Path
import xml.etree.ElementTree as ET


DEFAULT_OUTPUT = "moodle_demo.xml"


def add_text_node(parent, tag, text, **attrs):
    node = ET.SubElement(parent, tag, attrs)
    text_node = ET.SubElement(node, "text")
    text_node.text = text
    return node


def add_nested_text(parent, tag, text, **attrs):
    node = ET.SubElement(parent, tag, attrs)
    node.text = text
    return node


def add_category_question(root, category_name="Nobius"):
    question = ET.SubElement(root, "question", {"type": "category"})
    category = ET.SubElement(question, "category")
    add_nested_text(category, "text", f"$course$/top/{category_name}")
    return question


def add_shortanswer_question(root):
    question = ET.SubElement(root, "question", {"type": "shortanswer"})
    add_text_node(question, "name", "Text Entry")
    add_text_node(question, "questiontext", "Define a fluid.", format="plain_text")
    add_text_node(question, "generalfeedback", "", format="plain_text")
    ET.SubElement(question, "defaultgrade").text = "1.0000000"
    ET.SubElement(question, "penalty").text = "0.0000000"
    ET.SubElement(question, "hidden").text = "0"
    ET.SubElement(question, "usecase").text = "0"

    answer = ET.SubElement(question, "answer", {"fraction": "100", "format": "plain_text"})
    add_nested_text(answer, "text", "A fluid is a substance that deforms continuously under shear stress.")
    add_text_node(answer, "feedback", "", format="plain_text")
    return question


def add_multichoice_question(root):
    question = ET.SubElement(root, "question", {"type": "multichoice"})
    add_text_node(question, "name", "Multiple Choice")
    add_text_node(question, "questiontext", "What is Newton's Third Law?", format="plain_text")
    add_text_node(question, "generalfeedback", "", format="plain_text")
    ET.SubElement(question, "defaultgrade").text = "1.0000000"
    ET.SubElement(question, "penalty").text = "0.3333333"
    ET.SubElement(question, "hidden").text = "0"
    ET.SubElement(question, "single").text = "true"
    ET.SubElement(question, "shuffleanswers").text = "true"
    ET.SubElement(question, "answernumbering").text = "abc"

    answers = [
        ("0", "An object at rest stays at rest unless acted on by a net force."),
        ("0", "Force equals mass times acceleration."),
        ("100", "If object A exerts a force on object B, then B exerts an equal and opposite force on A."),
    ]
    for fraction, answer_text in answers:
        answer = ET.SubElement(question, "answer", {"fraction": fraction, "format": "plain_text"})
        add_nested_text(answer, "text", answer_text)
        add_text_node(answer, "feedback", "", format="plain_text")
    return question


def add_truefalse_question(root):
    question = ET.SubElement(root, "question", {"type": "truefalse"})
    add_text_node(question, "name", "True False")
    add_text_node(question, "questiontext", "Hydrostatic pressure increases with depth in a stationary fluid.", format="plain_text")
    add_text_node(question, "generalfeedback", "", format="plain_text")
    ET.SubElement(question, "defaultgrade").text = "1.0000000"
    ET.SubElement(question, "penalty").text = "0.3333333"
    ET.SubElement(question, "hidden").text = "0"

    true_answer = ET.SubElement(question, "answer", {"fraction": "100", "format": "plain_text"})
    add_nested_text(true_answer, "text", "true")
    add_text_node(true_answer, "feedback", "", format="plain_text")

    false_answer = ET.SubElement(question, "answer", {"fraction": "0", "format": "plain_text"})
    add_nested_text(false_answer, "text", "false")
    add_text_node(false_answer, "feedback", "", format="plain_text")
    return question


def add_numerical_question(root):
    question = ET.SubElement(root, "question", {"type": "numerical"})
    add_text_node(question, "name", "Numerical")
    add_text_node(question, "questiontext", "What is the gravitational acceleration on Earth in m/s^2?", format="plain_text")
    add_text_node(question, "generalfeedback", "", format="plain_text")
    ET.SubElement(question, "defaultgrade").text = "1.0000000"
    ET.SubElement(question, "penalty").text = "0.1000000"
    ET.SubElement(question, "hidden").text = "0"

    answer = ET.SubElement(question, "answer", {"fraction": "100", "format": "plain_text"})
    add_nested_text(answer, "text", "9.81")
    ET.SubElement(answer, "tolerance").text = "0.01"
    add_text_node(answer, "feedback", "", format="plain_text")
    return question


def add_matching_question(root):
    question = ET.SubElement(root, "question", {"type": "matching"})
    add_text_node(question, "name", "Matching")
    add_text_node(question, "questiontext", "Match each quantity to its SI unit.", format="plain_text")
    add_text_node(question, "generalfeedback", "", format="plain_text")
    ET.SubElement(question, "defaultgrade").text = "1.0000000"
    ET.SubElement(question, "penalty").text = "0.3333333"
    ET.SubElement(question, "hidden").text = "0"
    pairs = [
        ("Pressure", "Pa"),
        ("Density", "kg/m^3"),
        ("Force", "N"),
    ]
    for prompt, answer_text in pairs:
        subquestion = ET.SubElement(question, "subquestion", {"format": "plain_text"})
        add_text_node(subquestion, "text", prompt)
        add_text_node(subquestion, "answer", answer_text)
    return question


def add_essay_question(root):
    question = ET.SubElement(root, "question", {"type": "essay"})
    add_text_node(question, "name", "Essay")
    add_text_node(question, "questiontext", "Briefly explain the difference between pressure and force.", format="plain_text")
    add_text_node(question, "generalfeedback", "", format="plain_text")
    ET.SubElement(question, "defaultgrade").text = "1.0000000"
    ET.SubElement(question, "penalty").text = "0.0000000"
    ET.SubElement(question, "hidden").text = "0"
    ET.SubElement(question, "responseformat").text = "editor"
    ET.SubElement(question, "responserequired").text = "1"
    ET.SubElement(question, "responsefieldlines").text = "10"
    ET.SubElement(question, "attachments").text = "0"
    ET.SubElement(question, "attachmentsrequired").text = "0"
    ET.SubElement(question, "filetypeslist").text = ""
    ET.SubElement(question, "graderinfoformat").text = "1"
    add_text_node(question, "graderinfo", "", format="plain_text")
    ET.SubElement(question, "responsetemplateformat").text = "1"
    add_text_node(question, "responsetemplate", "", format="plain_text")
    return question


def build_demo_quiz():
    root = ET.Element("quiz")
    add_category_question(root)
    add_shortanswer_question(root)
    add_multichoice_question(root)
    add_truefalse_question(root)
    add_numerical_question(root)
    add_matching_question(root)
    add_essay_question(root)
    ET.indent(root, space="  ")
    return ET.ElementTree(root)


def write_demo_quiz(output_path):
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    tree = build_demo_quiz()
    tree.write(output, encoding="utf-8", xml_declaration=True)
    return output


def main():
    parser = ArgumentParser(description="Generate a plain-text Moodle XML demo question bank.")
    parser.add_argument("output", nargs="?", default=DEFAULT_OUTPUT, help="Path to the output Moodle XML file.")
    args = parser.parse_args()
    output = write_demo_quiz(args.output)
    print(output)


if __name__ == "__main__":
    main()
