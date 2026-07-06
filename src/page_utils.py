def dismiss_cookie_banner(page) -> bool:
    """Dismiss the NYT Fides cookie consent overlay if present."""
    reject_button = page.get_by_role("button", name="Reject all")
    if not reject_button.count():
        return False

    reject_button.click()
    page.locator("#fides-overlay").wait_for(state="hidden", timeout=10000)
    return True
