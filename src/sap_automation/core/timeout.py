import time


def wait_until(condition, timeout=10, interval=0.5):
    start = time.time()

    while time.time() - start < timeout:
        if condition():
            return True
        time.sleep(interval)

    raise TimeoutError("Timeout excedido")
