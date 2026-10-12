import time


def log(msg):
    # flush : sans lui, la sortie est bufferisee des qu'elle n'est pas un
    # terminal, et `appctl logs` ne montre rien pendant des minutes.
    print(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {msg}", flush=True)
