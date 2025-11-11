from logging import getLogger
from subprocess import CalledProcessError

from xml2rfc import XmlRfcParser
from xml2rfc.parser import XmlRfcError
from lxml.etree import XMLSyntaxError

from at.utils.file import get_extension, get_filename, save_file
from at.utils.logs import get_errors, process_xml2rfc_log
from at.utils.runner import proc_run, RunnerError


# Exceptions
class ProcessingError(Exception):
    """Error class for document processing errors"""

    pass


def process_file(file, upload_dir, logger=getLogger()):
    """Returns XML version of the given file.
    NOTE: if file is an XML file, that file wouldn't go through conversion."""

    (dir_path, filename) = save_file(file, upload_dir)

    logger.info("file saved at {}".format(filename))

    file_ext = get_extension(filename)

    if file_ext.lower() in [".md", ".mkd"]:
        filename = md2xml(filename, logger)
    elif file_ext.lower() == ".txt":
        filename = txt2xml(filename, logger)
    elif file_ext.lower() == ".rst":
        filename = rst2xml(filename, logger)

    return (dir_path, filename)


def md2xml(filename, logger=getLogger()):
    """Calls correct markdown processor for markdown files"""
    with open(filename, "r") as file:
        first_line = file.readline().strip()

    if len(first_line) > 2 and first_line[:3] == "%%%":
        return mmark2xml(filename, logger)
    else:
        return kramdown2xml(filename, logger)


def kramdown2xml(filename, logger=getLogger()):
    """Convert kramdown-rfc markdown file to XML"""

    logger.debug("processing kramdown-rfc file")

    try:
        output = proc_run(args=["kramdown-rfc", "--v3", filename], capture_output=True)
        output.check_returncode()
    except RunnerError as e:  # pragma: no cover
        logger.info(f"process error: {str(e)}")
        raise ProcessingError(str(e))
    except CalledProcessError:
        logger.info("kramdown-rfc error: {}".format(output.stderr.decode("utf-8")))
        raise ProcessingError(output.stderr.decode("utf-8"))

    # write output to XML file
    xml_file = get_filename(filename, "xml")
    with open(xml_file, "wb") as file:
        file.write(output.stdout)

    logger.info("new file saved at {}".format(xml_file))
    return xml_file


def mmark2xml(filename, logger=getLogger()):
    """Convert mmark markdown file to XML"""

    logger.debug("processing mmark file")

    try:
        output = proc_run(args=["mmark", filename], capture_output=True)
        output.check_returncode()
    except RunnerError as e:  # pragma: no cover
        logger.info(f"process error: {str(e)}")
        raise ProcessingError(str(e))
    except CalledProcessError:
        if output.stderr:
            error = output.stderr.decode("utf-8")
            logger.info("mmark error: {}".format(error))
        else:
            error = "mmark error"
            logger.info("mmark error: no stderr output")
        raise ProcessingError(error)

    # write output to XML file
    xml_file = get_filename(filename, "xml")
    with open(xml_file, "wb") as file:
        file.write(output.stdout)

    logger.info("new file saved at {}".format(xml_file))
    return xml_file


def rst2xml(filename, logger=getLogger()):
    """Convert rst file to XML"""

    logger.debug("processing RST file")

    xml_file = get_filename(filename, "xml")

    try:
        output = proc_run(
            args=["rst2rfcxml", "-i", filename, "-o", xml_file], capture_output=True
        )
        output.check_returncode()
    except RunnerError as e:  # pragma: no cover
        logger.info(f"process error: {str(e)}")
        raise ProcessingError(str(e))
    except CalledProcessError:
        logger.info("rst2rfcxml error: {}".format(output.stderr.decode("utf-8")))
        raise ProcessingError(output.stderr.decode("utf-8"))

    logger.info("new file saved at {}".format(xml_file))
    return xml_file


def txt2xml(filename, logger=getLogger()):
    """Convert text RFC file to XML"""

    logger.debug("processing text RFC file")

    xml_file = get_filename(filename, "xml")

    try:
        output = proc_run(
            args=["id2xml", "--v2", "--out", xml_file, filename], capture_output=True
        )
        output.check_returncode()
    except RunnerError as e:  # pragma: no cover
        logger.info(f"process error: {str(e)}")
        raise ProcessingError(str(e))
    except CalledProcessError:
        logger.info("id2xml error: {}".format(output.stderr.decode("utf-8")))
        raise ProcessingError(output.stderr.decode("utf-8"))

    logger.info("new file saved at {}".format(xml_file))
    return xml_file


def convert_v2v3(filename, logger=getLogger()):
    """Convert XML2RFC v2 file to v3"""
    logger.debug("converting v2 XML to v3 XML")

    xml_file = get_filename(filename, "xml")

    try:
        output = proc_run(
            args=["xml2rfc", "--v2v3", "--out", xml_file, filename], capture_output=True
        )
        output.check_returncode()
    except RunnerError as e:  # pragma: no cover
        logger.info(f"process error: {str(e)}")
        raise ProcessingError(str(e))
    except CalledProcessError:
        errors = get_errors(output, filename)
        if errors:
            logger.info("xml2rfc v2v3 error: {}".format(errors))
        else:
            errors = "v2v3 conversion error"
            logger.info("xml2rfc v2v3 error: no error output")
        raise ProcessingError(errors)

    logs = process_xml2rfc_log(output, filename)

    logger.info("new file saved at {}".format(xml_file))
    return (xml_file, logs)


def get_xml(filename, logger=getLogger()):
    """Convert/parse XML to XML2RFC v3
    NOTE: if file is XML2RFC v2 that will get converted to v3"""

    logs = None

    try:
        logger.debug("invoking xml2rfc parser")

        parser = XmlRfcParser(filename)
        xmltree = parser.parse(remove_comments=False)
        xmlroot = xmltree.getroot()
        xml2rfc_version = xmlroot.get("version", "2")

        if xml2rfc_version == "2":
            filename, logs = convert_v2v3(filename, logger)
    except (XmlRfcError, XMLSyntaxError) as e:
        logger.info("xml2rfc error: {}".format(str(e)))
        raise ProcessingError(e)

    logger.info("new file saved at {}".format(filename))
    return (filename, logs)


def _run_xml2rfc_conversion(filename, output_format, logger=getLogger()):
    """Helper function to run xml2rfc conversion with common error handling.
    
    Args:
        filename: Input XML filename
        output_format: Output format (html, text, pdf)
        logger: Logger instance
        
    Returns:
        Tuple of (output_file, processed_logs)
    """
    format_extension_map = {
        "html": "html",
        "text": "txt",
        "pdf": "pdf"
    }
    
    format_flag_map = {
        "html": "--html",
        "text": "--text",
        "pdf": "--pdf"
    }
    
    ext = format_extension_map[output_format]
    flag = format_flag_map[output_format]
    output_file = get_filename(filename, ext)

    try:
        output = proc_run(
            args=["xml2rfc", flag, "--out", output_file, filename],
            capture_output=True,
        )
        output.check_returncode()
    except RunnerError as e:  # pragma: no cover
        logger.info(f"process error: {str(e)}")
        raise ProcessingError(str(e))
    except CalledProcessError:
        errors = get_errors(output, filename)
        if errors:
            logger.info("xml2rfc {} error: {}".format(output_format, errors))
        else:
            errors = "{} generation error".format(output_format)
            logger.info("xml2rfc {} error: no error output".format(output_format))
        raise ProcessingError(errors)

    logger.info("new file saved at {}".format(output_file))
    return (output_file, process_xml2rfc_log(output, filename))


def get_html(filename, logger=getLogger()):
    """Render HTML"""
    logger.debug("running xml2rfc html converter")
    return _run_xml2rfc_conversion(filename, "html", logger)


def get_text(filename, logger=getLogger()):
    """Render text"""
    return _run_xml2rfc_conversion(filename, "text", logger)


def get_pdf(filename, logger=getLogger()):
    """Render PDF"""
    logger.debug("running xml2rfc pdf converter")
    return _run_xml2rfc_conversion(filename, "pdf", logger)


def clean_svg_ids(filename, logger=getLogger()):
    """Clean SVGs with duplicates IDs in XML"""
    logger.debug("invoking kramdown-rfc-clean-svg-ids")

    output = None
    try:
        output = proc_run(
            args=["kramdown-rfc-clean-svg-ids", filename], capture_output=True
        )
    except RunnerError as e:  # pragma: no cover
        logger.info(f"process error: {str(e)}")

    # write output to XML file
    xml_file = get_filename(filename, "xml")
    if output:
        with open(xml_file, "wb") as file:
            file.write(output.stdout)

    logger.info("new file saved at {}".format(xml_file))
    return xml_file
