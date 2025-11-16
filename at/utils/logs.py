from re import compile as re_compile, IGNORECASE

from at.utils.file import cleanup_output

XML2RFC_ERROR_REGEX = re_compile(r"^.*?Error: (?P<message>.*)$", IGNORECASE)
XML2RFC_WARN_REGEX = re_compile(r"^.*?Warning: (?P<message>.*)$", IGNORECASE)
XML2RFC_LINE_NUMBER_REGEX = re_compile(
    r"^.*?\((?P<line>.*?)\): (Error|Warning): ", IGNORECASE
)


def process_xml2rfc_log(output, filename):
    """Process xml2rfc output and return dictionary of errors and warnings"""
    log = []
    errors = []
    warnings = []
    unicode = []

    if output.stderr:
        log = cleanup_output(
            filename, output.stderr.decode("utf-8", errors="ignore")
        ).split("\n")

    for entry in log:
        # Extract line number once
        line_match = XML2RFC_LINE_NUMBER_REGEX.search(entry)
        line_num = line_match.group("line") if line_match else None
        
        # Check for error or warning
        error_match = XML2RFC_ERROR_REGEX.search(entry)
        if error_match:
            message = error_match.group("message")
            if line_num:
                errors.append(f"({line_num}) {message}")
            else:
                errors.append(message)
            continue
        
        warning_match = XML2RFC_WARN_REGEX.search(entry)
        if warning_match:
            message = warning_match.group("message")
            if "Found non-ascii characters" in message:
                if line_num:
                    unicode.append(f"({line_num}) {message}")
                else:
                    unicode.append(message)
            else:
                if line_num:
                    warnings.append(f"({line_num}) {message}")
                else:
                    warnings.append(message)

    return {"errors": errors, "warnings": warnings, "bare_unicode": unicode}


def get_errors(output, filename):
    """Returns errors as a string"""

    log = process_xml2rfc_log(output, filename)

    if len(log["errors"]) > 0:
        return "\n".join(log["errors"])
    else:
        return None


def update_logs(logs, new_entries):
    """Adds new entries to logs"""
    if new_entries:
        logs["errors"].extend(new_entries["errors"])
        logs["warnings"].extend(new_entries["warnings"])

    return logs
