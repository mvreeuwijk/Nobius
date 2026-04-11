import urllib.parse
import json
import html
import re

import bs4

RECOVERED_RESPONSE_PLACEHOLDER = object()


def report_warning(report, message, context=None):
    if report is not None:
        report.warn(message, context)
    if context:
        print(f"{message} [{context}]")
    else:
        print(message)


def report_info(report, message, context=None):
    if report is not None:
        if hasattr(report, "info"):
            report.info(message, context)
        else:
            report.warn(message, context)
    if context:
        print(f"{message} [{context}]")
    else:
        print(message)

"""
Main Method
"""

def get_question_data(html, report=None):
    """
    Method to scrape question data from its html using the data-propname attribute.
    ---
    Returns a dictionary structured depending on the data propnames.
    
    To create a propname, it is inserted in the html as an attribute:
    ```
    <div data-propname="parent.name">value</div>
    ```
    The propname tells the code how to nest the information within the html
    element. This should be a set of names or 'properties' that are separated by a dot,
    similarly to accessing properties in python: the name after a dot becomes a child of
    the property with the name before. Note all propnames must start at the root.

    For example to nest a value into the structure:
    ```
    {
        grandparent: {
            parent: {
                name: value
            }
        }
    }
    ```
    The element containing value must have the data-propname `grandparent.parent.name`.

    For arrays, the index is used, although it begins at 1, similar to the syntax of the
    datasource attribute in Mobius.

    For example, to nest values within a list:
    ```
    {
        parent: {
            name: [
                value_1,
                value_2
            ]
        }
    }
    ```
    the element containing value_1 and value_2 must use `parent.name.1` and `parent.name.2`
    as their propnames respectively.
    """
    question = {}
    missed_properties = 0

    # Find all elements in html with a data-propname atribute
    data_propname_elements = get_elements_with_data_propname_attribute(html)
    
    duplicate_statement_propnames = get_duplicate_statement_propnames(html)

    for element in data_propname_elements:
        # Get list of all property names from propname string
        properties = get_properties(element['data-propname'])
        if properties:
            if should_skip_duplicate_statement_element(element, duplicate_statement_propnames):
                continue
            # Get its value from the html
            value = get_element_value(properties, element, report)
            if value is RECOVERED_RESPONSE_PLACEHOLDER:
                continue
            # Nest the value into the question dictionary
            error = nest_dictionary(question, properties, value, report)
            if error:
                missed_properties += 1
                report_warning(report, "A problem occurred trying to nest the following property.", element['data-propname'])
            elif value is None or isinstance(value, list) and None in value:
                missed_properties += 1
                report_warning(report, "A problem occured trying to get the value of the following property.", element['data-propname'])
        else:
            missed_properties += 1
            report_warning(report, "No property names found for element.", element.prettify())
    
    question_name = question["title"] if "title" in question else "Question"

    if not data_propname_elements:
        report_warning(report, "No properties found in question.")
        report_warning(report, "This is likely because the file has not been generated using templating toolset.")
    elif missed_properties:
        print(f"'{question_name}' converted successfully except for {missed_properties} properties.")
    else:
        print(f"'{question_name}' converted successfully.")
    
    add_input_symbols(question, html, report)
    merge_duplicate_statement_fragments(question, html, report)
    return question

"""
BeautifulSoup and String Formatting Methods
"""

def get_elements_with_data_propname_attribute(html):
    """
    Method to find all html elements with a data-propname attribute.
    ---
    Returns a list of the html elements as BeautifulSoup instances.
    """
    return html.find_all(attrs={"data-propname": True})


def get_duplicate_statement_propnames(html):
    duplicate_propnames = set()
    statement_counts = {}

    for element in get_elements_with_data_propname_attribute(html):
        propname = element.get("data-propname")
        if not isinstance(propname, str) or not propname.endswith(".statement"):
            continue
        statement_counts[propname] = statement_counts.get(propname, 0) + 1

    for propname, count in statement_counts.items():
        if count > 1:
            duplicate_propnames.add(propname)

    return duplicate_propnames


def should_skip_duplicate_statement_element(element, duplicate_statement_propnames):
    propname = element.get("data-propname")
    if propname not in duplicate_statement_propnames:
        return False

    parent_part = element.find_parent("div", class_="part")
    if parent_part is None:
        return False

    statement_nodes = parent_part.find_all("p", attrs={"data-propname": propname})
    return len(statement_nodes) > 1 and element is not statement_nodes[0]


def add_input_symbols(question, html, report=None):
    if "parts" not in question:
        return

    part_divs = html.find_all("div", class_="part")
    for index, part_div in enumerate(part_divs):
        if index >= len(question["parts"]):
            break

        table = part_div.find("table", class_="input-symbols-table")
        if table is None:
            continue

        code_row = table.find("tr", class_="code")
        symbol_row = table.find("tr", class_="symbols")

        if code_row is None or symbol_row is None:
            report_warning(report, "Input symbols table could not be parsed cleanly.", f"part {index + 1}")
            continue

        codes = [cell.get_text(strip=True) for cell in code_row.find_all("td")]
        symbols = [cell.get_text(strip=True) for cell in symbol_row.find_all("td")]

        if len(codes) != len(symbols):
            report_warning(report, "Input symbols table has mismatched symbol/code counts.", f"part {index + 1}")
            continue

        question["parts"][index]["input_symbols"] = [
            [symbol, code] for symbol, code in zip(symbols, codes)
        ]


def merge_duplicate_statement_fragments(question, html, report=None):
    parts = question.get("parts")
    if not isinstance(parts, list):
        return

    part_divs = html.find_all("div", class_="part")
    for index, part_div in enumerate(part_divs):
        if index >= len(parts) or not isinstance(parts[index], dict):
            continue

        statement_nodes = part_div.find_all("p", attrs={"data-propname": f"parts.{index + 1}.statement"})
        if len(statement_nodes) <= 1:
            continue

        part = parts[index]
        recovered_placeholder = False
        recovered_post_response_text = False
        for extra_node in statement_nodes[1:]:
            fragment_html = html_unescape_fragment(extra_node.decode_contents())

            placeholder_match = re.search(r"<(\d+)\s*\/?\s*>", fragment_html)
            if placeholder_match and part.get("response") is None:
                part["response"] = int(placeholder_match.group(1))
                recovered_placeholder = True

            fragment_without_placeholder = re.sub(r"<\d+\s*\/?\s*>", "", fragment_html)
            fragment_text = bs4.BeautifulSoup(fragment_without_placeholder, "html.parser").get_text(" ", strip=True)
            fragment_text = fragment_text.replace("\xa0", " ").strip()

            if fragment_text:
                existing_text = str(part.get("post_response_text", "")).strip()
                if existing_text:
                    part["post_response_text"] = existing_text + " " + fragment_text
                else:
                    part["post_response_text"] = fragment_text
                recovered_post_response_text = True

        if recovered_placeholder:
            report_info(report, "Recovered response placeholder from duplicate statement fragments.", f"parts.{index + 1}.response")
        if recovered_post_response_text:
            report_info(report, "Recovered post-response text from duplicate statement fragments.", f"parts.{index + 1}.post_response_text")


def html_unescape_fragment(text):
    return html.unescape(text) if text is not None else ""
 
def get_properties(propname):
    """
    Method to get a list of property names from the propname string.
    ---
    Returns a list of property names for objects and indices for arrays.
    
    As Mobius uses 1 as the starting index for arrays, the indices found in the propname
    are converted to integers and decremented to work in python.
    """
    return [int(x) - 1 if x.isdigit() else x for x in propname.split(".") if x != ""]

def get_element_value(properties, element, report=None):
    """
    Method to get the value of an html element to be nested into the question dictionary.
    ---
    Returns a String, Boolean or Integer.

    The value returned depends on what the property is. This is usually the text within
    the html element, however there are a few exceptions:
    
    - If it is a response area, an integer is returned indicating its index in the list
      of response areas, or None if the tag can't be found.

    - If it is an image or a video, a list of filenames are returned. Note this doesn't
      include their directories or Mobius' server domain name.

    - If it is a structured tutorial, a string containing the full link to the video is
      returned, or None if the iframe or its source can't be found.

    - If it is a difficulty level or a par time, an integer is returned, or None if it
      cannot be converted to an integer.

    - If it is a final answer label (for worked solutions), it will always return True.
    """
    if properties[-1] == "response":
        return get_response(element, report)
    elif properties[-1] == "custom_response":
        return get_custom_response(element, report)
    elif properties[-1] == "media":
        return get_media(element, report)
    elif properties[-1] == "h5p_link":
        return get_h5p_link(element, report)
    elif properties[-1] == "par_time":
        return get_par_time(element, report)
    elif properties[-1] == "difficulty":
        return int(element.text) if element.text.isdigit() else None
    elif properties[-1] == "is_final_answer":
        return True
    else:
        return element.text.strip()

def get_response(response_html, report=None):
    """
    Method to return the index of a response area in a list of response areas using its html tag and regex.
    ---
    Returns an integer or None if not found.
    """
    response_tag_match = re.search(r"<(\d+)\s*\/?\s*>", html.unescape(response_html.text))
    if response_tag_match:
        return int(response_tag_match.group(1))
    else:
        if response_tag_recovered_from_duplicate_statement(response_html):
            return RECOVERED_RESPONSE_PLACEHOLDER
        report_warning(report, "Response area tag couldn't be found in element.", response_html.prettify())
        return None


def response_tag_recovered_from_duplicate_statement(response_html):
    propname = response_html.get("data-propname")
    if not isinstance(propname, str) or not propname.endswith(".response"):
        return False

    statement_propname = propname[:-len(".response")] + ".statement"
    parent_part = response_html.find_parent("div", class_="part")
    if parent_part is None:
        return False

    statement_nodes = parent_part.find_all(attrs={"data-propname": statement_propname})
    if len(statement_nodes) <= 1:
        return False

    for statement_node in statement_nodes[1:]:
        fragment_html = html_unescape_fragment(statement_node.decode_contents())
        if re.search(r"<(\d+)\s*\/?\s*>", fragment_html):
            return True

    return False

def get_custom_response(custom_response_html, report=None):
    inner_html = custom_response_html.p.decode_contents()

    tag_matches = re.findall(r"<(\d+)\s*\/?\s*>", html.unescape(str(inner_html)))

    if not tag_matches:
        report_warning(report, "Custom response area tags couldn't be found in element.", str(inner_html))
        return None

    starting_value = int(min(tag_matches, key=lambda x: int(x))) - 1

    def indexrepl(match_obj):
        return f"<{int(match_obj.group(1)) - starting_value}>"

    return {
        "layout": re.sub(r"<(\d+)\s*\/?\s*>", indexrepl, html.unescape(str(inner_html))),
        "starting_value": starting_value,
        "numberof_tags": len(tag_matches)
    }    

def get_media(medias_html, report=None):
    """
    Method to return a list of filenames from img and video elements within some html.
    ---
    Returns a list of strings or None if a filename isn't found.

    Note only the filename is returned. The domain name and directory names found in the
    src attributed are discarded.
    """
    media_list = []
    
    for media in medias_html.find_all(["img", "video"]):
        if 'src' in media.attrs:
            media_list.append(get_filename(media['src']))
        else:
            report_warning(report, "'src' attribute couldn't be found for media element.", media.prettify())
            media_list.append(None)

    return media_list

def get_h5p_link(tutorial_html, report=None):
    """
    Method to return the full link to a structured tutorial embedded in an iframe.
    ---
    Returns a string or None if not found.
    """
    if tutorial_html.iframe and 'src' in tutorial_html.iframe.attrs:
        return tutorial_html.iframe['src']
    else:
        report_warning(report, "iframe element or its src attribute couldn't be found.", tutorial_html.prettify())
        return None

def get_par_time(par_time_html, report=None):
    try:
        par_time = json.loads(par_time_html.text)
    except json.JSONDecodeError as error:
        report_warning(report, "Par time data could not be loaded due to an error.", error.msg)
        return None

    return par_time

def get_filename(filepath_string):
    """
    Method to capture the name of a file in a url encoded full link, using regex.
    ---
    Returns decoded string. Able to handle backescaped whitespace and slashes.
    """
    filepath_match = re.match(r"^.*(?=\/)(?<!\\)\/(.+)$", urllib.parse.unquote(filepath_string))
    if filepath_match:
        return filepath_match.group(1)
    else:
        print(f"\nFilename couldn't be captured in: {filepath_string}\n")
        return None

"""
JSON Nesting Methods
"""

def nest_dictionary(data, props, value, report=None):
    """
    Method to recusively nest a variable in a dictionary using its property names.
    ---
    Returns the exit code from the next function called, indicating whether a property
    was successfully nested.

    If there is only one element in the list of property names, this becomes the variable
    name. The value is then set to this variable name and the recursion process stops.

    If the next property name does not exist in the dictionary, it is created and made
    into a dictionary if the following property is a string, or a list if the following
    property is an integer (like an array index).

    The process continues up the chain of property names by calling next_nest().
    """
    if len(props) == 1:
        return set_value(data, props[0], value, report)
    else:
        if props[0] not in data:
            add_nest(data, props)

        return next_nest(data, props, value, report)

def nest_list(data, props, value, report=None):
    """
    Method to recusively nest a variable in a list using its property names.
    ---
    Returns the exit code from the next function called, indicating whether a property
    was successfully nested.

    If there is only one element in the list of property names, this becomes the variable
    index. The value is then set to this index and the recursion process stops.
    
    Note calling nest_list() must ensure this last value is an integer.

    If the variable index is out of the range of the array, None elements are created to 
    increase its length.

    If the next property name does not exist in the dictionary, it is created and made
    into a dictionary if the following property is a string, or a list if the following
    property is an integer (like an array index).

    The process continues up the chain of property names by calling next_nest().
    """
    if len(props) == 1:
        if len(data) <= props[0]:
            fill_null_list(data, props[0] + 1)
        
        return set_value(data, props[0], value, report)
    else:
        if len(data) <= props[0]:
            fill_null_list(data, props[0] + 1)
            add_nest(data, props)

        return next_nest(data, props, value, report) 

def next_nest(data, props, value, report=None):
    """
    Method to handle the next nest type in the list of property names.
    ---
    Returns the exit code from the next nesting function in the chain.
    However, if the property names are inconsistent with data structure, the process is
    stopped and function returns a 1.

    If the next property name in props holds a dictionary in the data object,
    nest_dictionary() is called. Otherwise If the property holds a list, then nest_list()
    is called.

    If the property holds neither, the nesting process is aborted.

    When these functions are called, they target the dictionary or list in data that has
    the same name as the first elements in props, causing the function to go one nest
    deeper. Simulatenously this name is removed from the list of props.

    The process continues until there is only one name in props left, which becomes the
    variable name. When this happens, the nesting process stops and the value is set.
    """
    if isinstance(data[props[0]], dict) and isinstance(props[1], str):
        return nest_dictionary(data[props[0]], props[1:], value, report)
    elif isinstance(data[props[0]], list) and isinstance(props[1], int):
        return nest_list(data[props[0]], props[1:], value, report)
    else:
        expected_type = "list" if isinstance(props[1], int) else "dict"
        report_warning(report, f"Expected property '{props[0]}' to be {expected_type} but has type {type(data[props[0]]).__name__}")
        report_warning(report, "Nesting property aborted.")
        return 1

def set_value(data, prop, value, report=None):
    """
    Method to set the value of a property
    ---
    Returns a exit code depending on whether the property was successfully nested.

    If the property already exists, the process is stopped and returns a 1.
    Else the exit code returned is 0.
    """
    if prop in data:
        report_warning(report, f"Property '{prop}' already exists.")
        report_warning(report, "Nesting property aborted.")
        return 1
    else:
        data[prop] = value
        return 0

def add_nest(data, props):
    """
    Method to add a nest to data.
    ---
    Nothing is returned. Instead it adds an item to `data`.

    If the next property is an integer, this is interpreted as an index and a list is
    added. Otherwise a dictionary is added.
    """
    data[props[0]] = [] if isinstance(props[1], int) else {}

def fill_null_list(li, length):
    """
    Method to increase the length of a list by adding None elements.
    ---
    Nothing is returned.
    """
    for i in range(length):
        if i > len(li) - 1:
            li.append(None)
