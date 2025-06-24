import json

COOKIES_PATH = "assets/cookies.json"


def load_cookies() -> list[dict]:
    """Load and format cookies from JSON file for Playwright.

    Returns:
        List of cookies formatted for Playwright's add_cookies method.
        Each cookie must have sameSite as one of: "Strict", "Lax", or "None"
    """
    try:
        with open(COOKIES_PATH, "r") as f:
            cookies = json.load(f)

        # Format cookies for Playwright
        formatted_cookies = []
        for cookie in cookies:
            # Convert sameSite to proper format and case
            same_site = cookie.get("sameSite", "Lax")
            if same_site == "unspecified":
                same_site = "Lax"
            elif same_site == "no_restriction":
                same_site = "None"
            elif same_site == "lax":
                same_site = "Lax"
            elif same_site == "strict":
                same_site = "Strict"
            elif same_site == "none":
                same_site = "None"

            formatted_cookie = {
                "name": cookie["name"],
                "value": cookie["value"],
                "domain": cookie["domain"],
                "path": cookie["path"],
                "sameSite": same_site,
                "secure": cookie.get("secure", False),
                "httpOnly": cookie.get("httpOnly", False),
            }

            # Add expiration if present
            if "expirationDate" in cookie:
                formatted_cookie["expires"] = cookie["expirationDate"]

            formatted_cookies.append(formatted_cookie)

        return formatted_cookies
    except Exception as e:
        logger.error(f"Failed to load cookies: {e}")
        return []
