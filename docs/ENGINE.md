# Using the converter from another program

Other programs (Ectype OCR first) use Ectype IDML as a separate, installed tool: they run its
.exe with a command, wait for it to finish, and read the result from a JSON file. The converter
keeps updating itself, so callers always get the latest version without being rebuilt, and the
two programs share only files, so neither's license binds the other.

API version: **1** (the `api` number in the result and in `program.json`; raised only when a
change would break a caller).

## 1. Find the program

The .exe's name carries its version (`Ectype-IDML-1.0.0.exe`) and the updater deletes older
copies, so don't store its path. Read it from `program.json` in the settings folder:

- Windows: `%APPDATA%\Ectype IDML\program.json` (before 1.0.0 the tool was called
  docx-to-idml; the file is also written to `%APPDATA%\docx-to-idml` while that folder exists)

```json
{"exe": "C:\\Users\\Beaux\\Apps\\Ectype-IDML-1.0.0.exe", "version": "1.0.0", "api": 1}
```

Every start of the program (window or command) rewrites it with its own location. If the file
is missing, or `exe` no longer exists, Ectype IDML isn't installed (or hasn't been started
since it was installed or moved): ask the user to install it from
<https://github.com/RexBHavgreau/ectype-idml/releases> and open it once. If `api` is higher
than the version you were written for, the result may hold fields you don't know; ignore them.

## 2. Run the conversion

```
Ectype-IDML-1.0.0.exe convert --result C:\temp\result.json --out C:\Books\Out --name "My Book" C:\temp\book.docx
```

| Argument | Meaning |
|---|---|
| files | One or more .docx files or folders, in book order (several files are one book, each file usually a chapter or part). |
| `--result FILE` | Required. Where to write the result (JSON, UTF-8). |
| `--out FOLDER` | The folder to put the export folder in (default: the current folder). |
| `--name NAME` | The export folder's and IDML's name (default: the book's title). |
| `--profile NAME` | A saved layout profile (name or .json file); default: the defaults. Profiles are made and saved in the converter's window. |
| `--book FILE` | A book file saved from the window (file order, book details, running heads, style map). |

The program shows no window and returns when the export is written. Run it hidden and wait for
it (Python: `subprocess.run([...], creationflags=subprocess.CREATE_NO_WINDOW)`). Exit code 0 =
done, 2 = not done (the reason is in the result). If the result file wasn't written (exit code
2 without it), the arguments were wrong.

## 3. Read the result

```json
{
  "api": 1,
  "version": "1.0.0",
  "ok": true,
  "idml": "C:\\Books\\Out\\My Book\\My Book.idml",
  "folder": "C:\\Books\\Out\\My Book",
  "report": ["Contents: 1 page reserved for 12 entries ...", "..."],
  "alerts": ["Running heads with Hebrew: ..."],
  "error": null
}
```

- `idml`, `folder`: the export. The folder also holds `Links/` with the images; move or send the
  folder as a whole.
- `report`: the export report, one line each, plain sentences for the user (what was left out,
  placeholders such as [ISBN], pages to check). Show it.
- `alerts`: the report lines the converter's own window shows in a pop-up (something the export
  did on its own that the user must know about). Show them prominently.
- `error`: when `ok` is false, a plain message saying what to do. `traceback` may be present
  too, for a bug report.

## 4. Updates

The first `convert` of each day starts a silent update check in a separate copy of the
program, after the conversion, so the call isn't slowed down. A newer release is downloaded
beside the running copy (checked against its digest) and `program.json` is pointed at it, so
the next call uses it. Turning off "Check for updates at startup" (Help menu in the window)
turns this off too. To check yourself: `Ectype-IDML-X.Y.Z.exe update` (prints "current",
"installed <path>" or "error: ...").

## 5. Preparing the .docx

The converter reads what Word writes; the better the structure, the better the book.

- **Headings:** Word's Heading 1 for chapters (Heading 2 and 3 for sections), or a Title-style
  line at the top of each file. Without heading styles, headings are found by their look
  (bigger, bold, centered, capitals), but styles are surer.
- **Book title and author:** a Title-style line (and Subtitle, Author) at the top of the first
  file.
- **Emphasis:** italic, bold, small caps as run formatting; they become the book's character
  styles.
- **Your own marks:** any character style you apply in the .docx is kept under its own name in
  the IDML, in InDesign, Affinity and DesignCraft alike. Use one for words to check (e.g. a
  "Check OCR" character style) and one for page markers from the original (e.g. `{p. 172}` in a
  "Page Marker" style); the user can then find them, or hide them, by style.
- **Footnotes:** Word footnotes (endnotes are turned into footnotes).
- **Hebrew and Greek:** as Unicode text; the converter gives them their language, direction and
  fonts.
- **Images:** JPEG or PNG, inline.

## 6. Stability

The output for the same input and settings only changes on purpose: golden files in
`tests/golden/` catch any other change, and the changelog says when the output changes. The
command, its arguments and the result's fields keep working within an API version.
