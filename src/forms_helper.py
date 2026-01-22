from __future__ import annotations

from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from . import paths
from . import config_read

# Forms + Drive scopes are required to copy a template and edit its body.
SCOPES = [
    "https://www.googleapis.com/auth/forms.body",
    "https://www.googleapis.com/auth/drive",
]


def _load_credentials():
    """Load the service account credentials used for Sheets/Calendar access."""
    try:
        return service_account.Credentials.from_service_account_file(
            str(paths.CREDS_DIR / "credentials.json"), scopes=SCOPES
        )
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            "credentials/credentials.json is missing. Share your form with the service account and "
            "download its key into credentials/credentials.json."
        ) from exc


def create_form_from_template(
    template_form_id: str,
    replacements: dict[str, str],
    *,
    new_title: str | None = None,
    parent_id: str | None = None,
) -> str:
    """
    Copy a Google Form template and replace placeholder text.

    Args:
        template_form_id: The form ID of the template to copy (the long ID in the form URL).
        replacements: Mapping of placeholder strings (e.g., '{{NAME}}') to replacement text.
        new_title: Optional title for the copied form file in Drive.
        parent_id: Optional Drive folder ID (My Drive folder or Shared Drive folder) to store the copy.

    Returns:
        The form ID of the new form.
    """
    creds = _load_credentials()
    drive = build("drive", "v3", credentials=creds)
    forms = build("forms", "v1", credentials=creds)

    copy_body = {"name": new_title} if new_title else {}
    if parent_id:
        copy_body["parents"] = [parent_id]
    try:
        new_form = drive.files().copy(
            fileId=template_form_id,
            body=copy_body,
            supportsAllDrives=True,
        ).execute()
    except HttpError as exc:
        raise RuntimeError(f"Could not copy template form {template_form_id}: {exc}") from exc

    new_form_id = new_form["id"]

    if replacements:
        requests = [
            {
                "replaceAllText": {
                    "containsText": {"text": placeholder, "matchCase": True},
                    "replaceText": value,
                }
            }
            for placeholder, value in replacements.items()
        ]
        try:
            forms.forms().batchUpdate(formId=new_form_id, body={"requests": requests}).execute()
        except HttpError as exc:
            raise RuntimeError(f"Copied form but failed to update text: {exc}") from exc

    return new_form_id


def build_replacements_from_config(config: dict, *, uppercase_class: bool = True) -> dict[str, str]:
    """Construct placeholder replacements from a scheduler config."""
    class_name = str(config.get("class", ""))
    semester = str(config.get("semester", ""))
    if uppercase_class:
        class_name = class_name.upper()
    return {
        "{{CLASS}}": class_name,
        "{{SEMESTER}}": semester,
    }


def create_form_from_template_with_config(
    template_form_id: str,
    config_path: str | Path = paths.CONFIG_DIR / "config.json",
    *,
    new_title: str | None = None,
    extra_replacements: dict[str, str] | None = None,
    uppercase_class: bool = True,
    parent_id: str | None = None,
) -> str:
    """
    Copy a Google Form template using placeholders populated from a scheduler config.

    Args:
        template_form_id: Template form ID.
        config_path: Path to the scheduler config JSON.
        new_title: Optional Drive title for the copied form (defaults to CS{CLASS} {SEMESTER} pattern).
        extra_replacements: Additional placeholder replacements to merge in.
        uppercase_class: If True, uppercases the class code when replacing {{CLASS}}.
        parent_id: Optional Drive folder ID (My Drive or Shared Drive) to store the copy and avoid quota issues.

    Returns:
        The new form ID.
    """
    config = config_read.read_config(str(config_path))
    replacements = build_replacements_from_config(config, uppercase_class=uppercase_class)
    if extra_replacements:
        replacements.update(extra_replacements)

    if not new_title:
        new_title = f"[CS{replacements['{{CLASS}}']} {replacements['{{SEMESTER}}']}] Staff Availabilities Form"

    return create_form_from_template(
        template_form_id,
        replacements,
        new_title=new_title,
        parent_id=parent_id,
    )


# --- Manual test harness (fill in TEMPLATE_FORM_ID before running this file directly) ---
TEMPLATE_FORM_ID = "10j0mbeNVvo8wtaGfFUjsDuanz2BqrGR_IVUqC36Vm6w"  # TODO: paste the template form ID here when testing locally.
DESTINATION_PARENT_ID = "1CwzzaWw4VuZ-PDGI-rIPlPa2mNelxNDc"  # Optional: Drive folder ID (My Drive folder or Shared Drive) to store the copy.


def _run_manual_test() -> None:
    """Copy the template form and print the edit/view URLs."""
    if not TEMPLATE_FORM_ID:
        raise SystemExit("Set TEMPLATE_FORM_ID in src/forms_helper.py before running the manual test.")

    new_form_id = create_form_from_template_with_config(
        template_form_id=TEMPLATE_FORM_ID,
        config_path=paths.CONFIG_DIR / "config.json",
        extra_replacements={"{{NAME}}": "Staff"},  # edit or remove if not used
        parent_id=DESTINATION_PARENT_ID or None,
    )
    print("Edit URL: https://docs.google.com/forms/d/{}/edit".format(new_form_id))
    print("Live URL: https://docs.google.com/forms/d/{}/viewform".format(new_form_id))


if __name__ == "__main__":
    _run_manual_test()
