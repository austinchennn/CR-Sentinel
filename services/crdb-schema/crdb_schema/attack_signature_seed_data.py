"""Seed descriptions for attack_signatures (PRD-01 functional requirement
4). Sourced from the concrete evasion techniques in rawmaterial.txt's
"traditional WAF vs AI" scenarios -- these are the exact obfuscation
tricks the demo attack scripts (PRD-08) will exercise, so a semantic
recall test against them is a real signal, not a softball match against
made-up text.

Each entry becomes one row once seed_attack_signatures.py embeds
`description` and upserts it, keyed on (category, description) -- see
migrations/001_core_tables.sql. Treat `description` text as append-only
once seeded: editing it creates a new row rather than updating in place.
"""

SEED_ATTACK_SIGNATURES = [
    # sqli -- five entries; several are the exact obfuscation patterns a
    # plaintext-keyword WAF regex misses (rawmaterial.txt sections 1, 6).
    {
        "category": "sqli",
        "severity": "high",
        "description": "Classic UNION-based SQL injection: appending UNION SELECT to a query "
        "parameter to exfiltrate data from other tables.",
    },
    {
        "category": "sqli",
        "severity": "high",
        "description": "Case-mixed obfuscated SQL injection such as UnIoN sElEcT, designed to "
        "bypass case-sensitive keyword regex filters.",
    },
    {
        "category": "sqli",
        "severity": "high",
        "description": "Comment-split SQL injection keywords like un/**/ion sel/**/ect, breaking "
        "up blacklisted tokens with inline comments to evade string matching.",
    },
    {
        "category": "sqli",
        "severity": "high",
        "description": "URL-encoded or Unicode-escaped SQL injection payload, for example "
        "%75%6E%69%6F%6E for the word union, evading plaintext keyword filters.",
    },
    {
        "category": "sqli",
        "severity": "high",
        "description": "Blind time-based SQL injection using sleep() or pg_sleep() delays such as "
        "admin' sleep(3)-- to probe the database without triggering a visible error.",
    },
    # xss
    {
        "category": "xss",
        "severity": "medium",
        "description": "Reflected cross-site scripting via an encoded <script> tag submitted in a "
        "comment or search field.",
    },
    {
        "category": "xss",
        "severity": "medium",
        "description": "Stored XSS using HTML event handler attributes such as onerror= or onload= "
        "to execute script without a <script> tag.",
    },
    {
        "category": "xss",
        "severity": "medium",
        "description": "Unicode or HTML-entity encoded XSS payload that only decodes into an "
        "executable script tag after the browser renders it, bypassing plaintext filters.",
    },
    # idor
    {
        "category": "idor",
        "severity": "high",
        "description": "Horizontal privilege escalation by incrementing or guessing a numeric "
        "user_id or order_id query parameter to read another user's private data.",
    },
    {
        "category": "idor",
        "severity": "high",
        "description": "Vertical privilege escalation: a normal user submits an admin-only "
        "parameter or role field that the endpoint fails to re-validate server-side.",
    },
    {
        "category": "idor",
        "severity": "medium",
        "description": "Sequential enumeration of a resource identifier across many requests to "
        "harvest other users' records in bulk, with no injection syntax involved.",
    },
    # bruteforce
    {
        "category": "bruteforce",
        "severity": "high",
        "description": "High-frequency credential stuffing: dozens of login attempts per minute "
        "from one IP cycling through a password list.",
    },
    {
        "category": "bruteforce",
        "severity": "medium",
        "description": "Low-and-slow brute force that stays under a fixed rate threshold, such as "
        "one attempt every few minutes, while still cycling through many passwords for one account.",
    },
    {
        "category": "bruteforce",
        "severity": "medium",
        "description": "Password spraying: the same one or two common passwords attempted against "
        "a large number of different usernames to avoid per-account lockouts.",
    },
    # phishing / social engineering
    {
        "category": "phishing",
        "severity": "medium",
        "description": "A comment or message body containing a shortened URL and text urging an "
        "administrator to click it to claim access or verify an account.",
    },
    {
        "category": "phishing",
        "severity": "medium",
        "description": "Social-engineering text embedded in a support ticket or profile field "
        "impersonating internal IT and requesting a password or one-time code.",
    },
    {
        "category": "phishing",
        "severity": "low",
        "description": "A grammatically normal message with no code or script tags that links to a "
        "look-alike login page to harvest credentials.",
    },
]
