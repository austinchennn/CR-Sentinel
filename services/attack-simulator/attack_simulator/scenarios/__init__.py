from . import chained_intrusion, idor_enumeration, obfuscated_sqli, slow_bruteforce

SCENARIOS = {
    obfuscated_sqli.NAME: obfuscated_sqli,
    slow_bruteforce.NAME: slow_bruteforce,
    idor_enumeration.NAME: idor_enumeration,
    chained_intrusion.NAME: chained_intrusion,
}
