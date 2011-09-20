"""Forms used by django-subscribers."""

import csv, re

from django import forms


class SubscribeForm(forms.Form):

    """
    A form that permits subscribing to the mailing list via a unified name field
    or separate first name and last name fields.
    """

    name = forms.CharField(
        max_length = 401,
        required = False,
    )
    
    first_name = forms.CharField(
        max_length = 200,
        required = False,
    )
    
    last_name = forms.CharField(
        max_length = 200,
        required = False,
    )
    
    email = forms.EmailField(
        required = True,
    )
    
    def clean(self):
        """Performs additional validation."""
        cleaned_data = self.cleaned_data
        # Parse the name to get the first name and last name.
        name = self.cleaned_data.get("name", "")
        if name:
            name_parts = name.split(" ", 1)
            first_name = len(name_parts) > 0 and name_parts[0] or ""
            last_name = len(name_parts) > 1 and name_parts[1] or ""
            # Set these as defaults for the actual first and last name.
            cleaned_data["first_name"] = cleaned_data.get("first_name", "") or first_name
            cleaned_data["last_name"] = cleaned_data.get("last_name", "") or last_name
        # All cleaning is done!
        return cleaned_data


RE_WHITESPACE = re.compile(u"\s+")
        
        
class ImportFromCsvForm(forms.Form):

    """A form that accepts a CSV file."""
    
    file = forms.FileField()
    
    def clean_file(self):
        """Parses the CSV file."""
        file = self.cleaned_data.get("file")
        if file:
            try:
                reader = csv.reader(file)
                # Parse the header row.
                try:
                    header_row = reader.next()
                except StopIteration:
                    raise forms.ValidationError("That CSV file is empty.")
                headers = [
                    RE_WHITESPACE.sub("_", cell.decode("utf-8", "ignore").lower().strip()).replace("firstname", "first_name").replace("lastname", "last_name")
                    for cell in header_row
                ]
                # Check the required fields.
                if len(headers) == 0:
                    raise forms.ValidationError("That CSV file did not contain a valid header line.")
                if not "email" in headers:
                    raise forms.ValidationError("Could not find a column labelled 'email' in that CSV file.")
                # Go through the rest of the CSV file.
                clean_rows = []
                invalid_rows = []
                for lineno, row in enumerate(reader, 1):
                    try:
                        row_data = dict(zip(headers, row))
                    except IndexError:
                        invalid_rows.append((lineno, row_data))
                    row_form = SubscribeForm(row_data)
                    if row_form.is_valid():
                        clean_rows.append(row_form.cleaned_data)
                    else:
                        invalid_rows.append((lineno, row_data))
            except csv.Error:
                raise forms.ValidationError("Please upload a valid CSV file.")
            # Check that some rows were parsed.
            if not clean_rows and not invalid_rows:
                raise forms.ValidationError("There are no subscribers in that CSV file.")
            if not clean_rows and invalid_rows:
                raise forms.ValidationError("No subscribers could be imported, due to errors in that CSV file.")
            # Store the parsed data.
            self.cleaned_data["rows"] = clean_rows
            self.cleaned_data["invalid_rows"] = invalid_rows
        return file