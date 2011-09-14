"""Forms used by django-subscribers."""

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
            first_name, last_name = name.split(" ", 1)
            # Set these as defaults for the actual first and last name.
            cleaned_data["first_name"] = cleaned_data.get("first_name", "") or first_name
            cleaned_data["last_name"] = cleaned_data.get("last_name", "") or last_name
        # All cleaning is done!
        return cleaned_data