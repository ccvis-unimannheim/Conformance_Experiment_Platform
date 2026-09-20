import re
# read full file in once, then look with a regex for the first occurrence of a 12-digit code. Then look for the next
# occurrence of a label field.
#
# lookup if this node_id is already known then skip this id.

def node_id_label_mapping(dot_file_path, remove_occurrence_tag=True):
    """
    Read a dot file as an input and returns a mapping between the 28 digit long node ids and their corresponding labels
    :param dot_file_path:
    :param remove_occurrence_tag:
    :return: Dict {Node_IDs, Label_Value}
    """

    re_remove_occurrence_tag = re.compile(r' \(\d*\)')
    with open(dot_file_path, "r") as dot_file:
        file_content = dot_file.read()
    # Regular expression to find 18-digit numbers (positive or negative), sometimes they are shorter
    number_pattern = r'(?<!\d)(-?\d{16,})(?!\d)'
    # Regular expression to find the next quoted value
    quoted_value_pattern = r'label=\"(.*?)\"'


    # Dictionary to store mappings of numbers to quoted values
    mappings = {}
    # Set to store encountered numbers
    encountered_numbers = set()

    # Finding all 12-digit numbers
    numbers = re.finditer(number_pattern, file_content)

    for number_match in numbers:
        number = number_match.group(0)

        # Check if number is already encountered
        if number in encountered_numbers:
            continue

        # Mark number as encountered
        encountered_numbers.add(number)

        # Get the position after the number to search for the next quoted value
        start_pos = number_match.end()

        # Search for the next quoted value after the number
        quoted_match = re.search(quoted_value_pattern, file_content[start_pos:])
        if quoted_match:
            quoted_value = quoted_match.group(1)
            if remove_occurrence_tag:
                quoted_value = re.sub(re_remove_occurrence_tag, "", quoted_value)
            quoted_value = re.sub(" ", "", quoted_value)
            mappings[number] = quoted_value

    return mappings

if __name__ == "__main__":
    mapping = node_id_label_mapping(r"C:\Users\frede\PycharmProjects\ProcessVisualizationSandbox\MiddleDot_COPY.dot")
    print(mapping)