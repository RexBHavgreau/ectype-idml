"""Ectype IDML: Word manuscript (.docx) to IDML book converter."""

__version__ = "1.0.0"
APP_NAME = "Ectype IDML"  # the program's name; also its settings folder's
EXE_BASE = "Ectype-IDML"  # the program's file name: "Ectype-IDML-1.0.0.exe"
# Before 1.0.0 the tool was "docx-to-idml": its settings folder is copied to the new one at the
# first start, older copies of the program are recognized (and offered for deletion), and
# releases also carry the program under the old name, which is all older copies look for.
OLD_APP_NAME = "docx-to-idml"
OLD_EXE_BASE = "docx-to-idml"
REPO = "RexBHavgreau/docx-to-idml"  # GitHub repository whose releases the updater checks
